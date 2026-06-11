import Foundation

enum PythonBridgeServiceError: LocalizedError {
    case missingResource(String)
    case processFailure(String, errorReportPath: String?)
    case decodeFailure(String, errorReportPath: String?)
    case bridgeFailure(String, logs: String, errorReportPath: String?)

    var errorDescription: String? {
        switch self {
        case .missingResource(let message):
            return message
        case .processFailure(let message, let errorReportPath),
             .decodeFailure(let message, let errorReportPath):
            return Self.message(message, errorReportPath: errorReportPath)
        case .bridgeFailure(let message, let logs, let errorReportPath):
            if let errorReportPath, !errorReportPath.isEmpty {
                return Self.message(message, errorReportPath: errorReportPath)
            }
            if logs.isEmpty {
                return message
            }
            return "\(message)\n\n\(logs)"
        }
    }

    private static func message(_ message: String, errorReportPath: String?) -> String {
        guard let errorReportPath, !errorReportPath.isEmpty else {
            return message
        }
        return "\(message)\n\nFull error details were saved to:\n\(errorReportPath)"
    }
}

/// Runs bridge requests against a long-lived Python server process.
///
/// The backend interpreter (plus pandas/PIL imports) starts once per app
/// session instead of once per request, which turns multi-second bridge calls
/// into near-instant ones. Requests are serialized through the actor; if the
/// server process dies it is restarted transparently and the request retried.
actor PythonBridgeService {
    private struct Envelope<Result: Decodable>: Decodable {
        let id: Int?
        let ok: Bool
        let result: Result?
        let error: String?
        let logs: String
        let errorReportPath: String?

        enum CodingKeys: String, CodingKey {
            case id
            case ok
            case result
            case error
            case logs
            case errorReportPath = "error_report_path"
        }
    }

    private struct EnvelopeID: Decodable {
        let id: Int?
    }

    private final class StderrBuffer: @unchecked Sendable {
        private let lock = NSLock()
        private var data = Data()
        private let maxBytes = 64 * 1024

        func append(_ chunk: Data) {
            lock.lock()
            defer { lock.unlock() }
            data.append(chunk)
            if data.count > maxBytes {
                data.removeFirst(data.count - maxBytes)
            }
        }

        func snapshot() -> String {
            lock.lock()
            defer { lock.unlock() }
            return String(decoding: data, as: UTF8.self)
        }
    }

    private let fileManager = FileManager.default

    private var serverProcess: Process?
    private var serverStdin: FileHandle?
    private var serverLines: AsyncLineSequence<FileHandle.AsyncBytes>.AsyncIterator?
    private var serverStderr = StderrBuffer()
    private var nextRequestID = 1

    deinit {
        serverProcess?.terminationHandler = nil
        serverProcess?.terminate()
    }

    func execute<Result: Decodable>(_ action: String, payload: Any = [:], as _: Result.Type = Result.self) async throws -> Result {
        // Actors interleave at suspension points, so explicitly serialize
        // requests: exactly one request may talk to the server at a time.
        await acquireRequestSlot()
        defer { releaseRequestSlot() }

        do {
            return try await performRequest(action, payload: payload)
        } catch let error as PythonBridgeServiceError {
            if case .bridgeFailure = error {
                throw error
            }
            // Transport-level failure: the server may have died. Restart once.
            shutdownServer()
            return try await performRequest(action, payload: payload)
        }
    }

    // MARK: - Request serialization

    private var requestInFlight = false
    private var requestWaiters: [CheckedContinuation<Void, Never>] = []

    private func acquireRequestSlot() async {
        if !requestInFlight {
            requestInFlight = true
            return
        }
        await withCheckedContinuation { continuation in
            requestWaiters.append(continuation)
        }
    }

    private func releaseRequestSlot() {
        if requestWaiters.isEmpty {
            requestInFlight = false
        } else {
            requestWaiters.removeFirst().resume()
        }
    }

    // MARK: - Request plumbing

    private func performRequest<Result: Decodable>(_ action: String, payload: Any) async throws -> Result {
        let resources = try resolveResources()
        try ensureStateDirectories(at: resources.stateDirectory, outputDirectory: resources.outputDirectory)
        try await ensureServerRunning(resources: resources)

        guard let stdin = serverStdin else {
            throw PythonBridgeServiceError.processFailure("The Python bridge is not running.", errorReportPath: nil)
        }

        let requestID = nextRequestID
        nextRequestID += 1

        let body: [String: Any] = [
            "id": requestID,
            "action": action,
            "payload": JSONSerialization.isValidJSONObject(payload) ? payload : [:],
        ]
        var data = try JSONSerialization.data(withJSONObject: body)
        data.append(0x0A)

        do {
            try stdin.write(contentsOf: data)
        } catch {
            shutdownServer()
            throw PythonBridgeServiceError.processFailure(
                "Could not reach the Python bridge: \(error.localizedDescription)",
                errorReportPath: nil
            )
        }

        guard let line = try await readResponseLine(matching: requestID) else {
            let stderr = serverStderr.snapshot()
            shutdownServer()
            let reportPath = try? writeProcessErrorReport(
                action: action,
                payload: payload,
                resources: resources,
                stdout: "<no response>",
                stderr: stderr,
                reason: "The Python bridge exited before responding."
            )
            throw PythonBridgeServiceError.processFailure(
                "The Python bridge exited unexpectedly.",
                errorReportPath: reportPath
            )
        }

        let lineData = Data(line.utf8)
        let decoder = JSONDecoder()
        let envelope: Envelope<Result>
        do {
            envelope = try decoder.decode(Envelope<Result>.self, from: lineData)
        } catch {
            let reportPath = try? writeProcessErrorReport(
                action: action,
                payload: payload,
                resources: resources,
                stdout: line,
                stderr: serverStderr.snapshot(),
                reason: "The Python bridge returned malformed JSON: \(error.localizedDescription)"
            )
            throw PythonBridgeServiceError.decodeFailure(
                "The Python bridge returned malformed JSON.",
                errorReportPath: reportPath
            )
        }

        guard envelope.ok, let result = envelope.result else {
            throw PythonBridgeServiceError.bridgeFailure(
                envelope.error ?? "The Python bridge returned an unknown error.",
                logs: envelope.logs,
                errorReportPath: envelope.errorReportPath
            )
        }

        return result
    }

    /// Read response lines until one matches the request id (or EOF).
    private func readResponseLine(matching requestID: Int) async throws -> String? {
        while true {
            guard var iterator = serverLines else { return nil }
            let line: String?
            do {
                line = try await iterator.next()
            } catch {
                serverLines = iterator
                return nil
            }
            serverLines = iterator

            guard let line else { return nil }
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { continue }

            if let envelopeID = try? JSONDecoder().decode(EnvelopeID.self, from: Data(trimmed.utf8)),
               envelopeID.id == requestID {
                return trimmed
            }
            // Lines with a different/missing id (e.g. the readiness handshake
            // or responses to abandoned requests) are skipped.
        }
    }

    // MARK: - Server lifecycle

    private func ensureServerRunning(resources: ResourceLocations) async throws {
        if let process = serverProcess, process.isRunning {
            return
        }
        shutdownServer()

        let process = Process()
        process.executableURL = resources.pythonExecutable
        process.arguments = [resources.bridgeScript.path, "--serve"]
        process.currentDirectoryURL = resources.stateDirectory

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONHOME"] = resources.pythonHome.path
        environment["PYTHONPATH"] = "\(resources.sitePackages.path):\(resources.backendRoot.path)"
        environment["FTID_BASE_DIR"] = resources.backendRoot.path
        environment["FTID_OUTPUT_DIR"] = resources.outputDirectory.path
        environment["FTID_STATE_DIR"] = resources.stateDirectory.path
        environment["FTID_NONINTERACTIVE"] = "1"
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment

        let stdinPipe = Pipe()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardInput = stdinPipe
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        let stderrBuffer = StderrBuffer()
        stderrPipe.fileHandleForReading.readabilityHandler = { handle in
            let chunk = handle.availableData
            if chunk.isEmpty {
                handle.readabilityHandler = nil
            } else {
                stderrBuffer.append(chunk)
            }
        }

        try process.run()

        serverProcess = process
        serverStdin = stdinPipe.fileHandleForWriting
        serverLines = stdoutPipe.fileHandleForReading.bytes.lines.makeAsyncIterator()
        serverStderr = stderrBuffer

        // Wait for the readiness handshake (id == nil) so the first real
        // request is not interleaved with interpreter startup.
        while true {
            guard var iterator = serverLines else {
                throw PythonBridgeServiceError.processFailure(
                    "The Python bridge terminated during startup.\n\(stderrBuffer.snapshot())",
                    errorReportPath: nil
                )
            }
            let line = try await iterator.next()
            serverLines = iterator
            guard let line else {
                shutdownServer()
                throw PythonBridgeServiceError.processFailure(
                    "The Python bridge terminated during startup.\n\(stderrBuffer.snapshot())",
                    errorReportPath: nil
                )
            }
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { continue }
            if let envelopeID = try? JSONDecoder().decode(EnvelopeID.self, from: Data(trimmed.utf8)),
               envelopeID.id == nil {
                return
            }
        }
    }

    private func shutdownServer() {
        if let process = serverProcess, process.isRunning {
            process.terminate()
        }
        try? serverStdin?.close()
        serverProcess = nil
        serverStdin = nil
        serverLines = nil
    }

    // MARK: - Resources

    private func ensureStateDirectories(at stateDirectory: URL, outputDirectory: URL) throws {
        try fileManager.createDirectory(at: stateDirectory, withIntermediateDirectories: true)
        try fileManager.createDirectory(at: outputDirectory, withIntermediateDirectories: true)
    }

    private func resolveResources() throws -> ResourceLocations {
        guard let resourceRoot = Bundle.main.resourceURL else {
            throw PythonBridgeServiceError.missingResource("The app bundle is missing its resource directory.")
        }
        guard let frameworksRoot = Bundle.main.privateFrameworksURL else {
            throw PythonBridgeServiceError.missingResource("The app bundle is missing its private Frameworks directory.")
        }

        let pythonHome = frameworksRoot.appendingPathComponent("Python.framework/Versions/3.13")
        let pythonExecutable = pythonHome.appendingPathComponent("bin/python3.13")
        let sitePackages = resourceRoot.appendingPathComponent("python-site-packages")
        let backendRoot = resourceRoot.appendingPathComponent("backend")
        let bridgeScript = backendRoot.appendingPathComponent("bridge/ftid_bridge.py")
        let importerScript = backendRoot.appendingPathComponent("ftid_gen/excel_importer.py")

        guard fileManager.fileExists(atPath: pythonExecutable.path) else {
            throw PythonBridgeServiceError.missingResource("The bundled Python runtime is missing at \(pythonExecutable.path).")
        }
        guard fileManager.fileExists(atPath: sitePackages.path) else {
            throw PythonBridgeServiceError.missingResource("The bundled Python site-packages directory is missing at \(sitePackages.path).")
        }
        guard fileManager.fileExists(atPath: bridgeScript.path) else {
            throw PythonBridgeServiceError.missingResource("The bundled bridge script is missing at \(bridgeScript.path).")
        }
        guard fileManager.fileExists(atPath: importerScript.path) else {
            throw PythonBridgeServiceError.missingResource("The bundled import reader is missing at \(importerScript.path).")
        }

        let appSupport = try fileManager.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        ).appendingPathComponent("FTIDMacApp", isDirectory: true)

        return ResourceLocations(
            pythonHome: pythonHome,
            pythonExecutable: pythonExecutable,
            sitePackages: sitePackages,
            backendRoot: backendRoot,
            bridgeScript: bridgeScript,
            importerScript: importerScript,
            stateDirectory: appSupport,
            outputDirectory: appSupport.appendingPathComponent("Output", isDirectory: true)
        )
    }

    private func writeProcessErrorReport(
        action: String,
        payload: Any,
        resources: ResourceLocations,
        stdout: String,
        stderr: String,
        reason: String
    ) throws -> String {
        let reportsDirectory = resources.stateDirectory.appendingPathComponent("ErrorReports", isDirectory: true)
        try fileManager.createDirectory(at: reportsDirectory, withIntermediateDirectories: true)

        let timestamp = DateFormatter.errorReportTimestamp.string(from: Date())
        let url = reportsDirectory.appendingPathComponent("process_error_\(timestamp)_\(action).txt")

        let payloadText: String
        if JSONSerialization.isValidJSONObject(payload),
           let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys]),
           let string = String(data: data, encoding: .utf8) {
            payloadText = string
        } else {
            payloadText = "<unserializable payload>"
        }

        let report = """
        FTID Process Error Report
        Timestamp: \(ISO8601DateFormatter().string(from: Date()))
        Action: \(action)
        Working directory: \(resources.stateDirectory.path)
        Backend root: \(resources.backendRoot.path)
        Reason: \(reason)

        Payload:
        \(payloadText)

        stdout:
        \(stdout.isEmpty ? "<empty>" : stdout)

        stderr:
        \(stderr.isEmpty ? "<empty>" : stderr)
        """

        try report.write(to: url, atomically: true, encoding: .utf8)
        return url.path
    }
}

private struct ResourceLocations {
    let pythonHome: URL
    let pythonExecutable: URL
    let sitePackages: URL
    let backendRoot: URL
    let bridgeScript: URL
    let importerScript: URL
    let stateDirectory: URL
    let outputDirectory: URL
}

private extension DateFormatter {
    static let errorReportTimestamp: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd_HHmmss_SSS"
        return formatter
    }()
}
