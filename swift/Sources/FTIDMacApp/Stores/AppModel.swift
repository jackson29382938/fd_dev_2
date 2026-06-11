import AppKit
import Foundation

enum AppModelError: LocalizedError {
    case unexpectedLabelTemplate(carrier: Carrier, expected: String, actual: String)

    var errorDescription: String? {
        switch self {
        case .unexpectedLabelTemplate(let carrier, let expected, let actual):
            return "\(carrier.rawValue) label generation returned \(actual), but the Swift app expected the final blank template \(expected)."
        }
    }
}

@MainActor
final class AppModel: ObservableObject {
    @Published var session: UserSession?
    @Published var settings: AppSettings = .defaultValue
    @Published var upsForm = LabelFormState()
    @Published var uspsForm = LabelFormState()
    @Published var fedexForm = LabelFormState()
    @Published var history: [HistoryEntry] = []
    @Published var previousMaxicodeEntries: [PreviousMaxicodeEntry] = []
    @Published var lastGenerated: LabelGenerationResult?
    @Published var recentGenerations: [LabelGenerationResult] = []
    @Published var importPreview: ImportPreview?
    @Published var importMappings: [String: String] = [:]
    @Published var importSummary: ImportProcessResult?
    @Published var selectedImportFilePath: String?
    @Published var generatedMaxicode: GeneratedMaxicode?
    @Published var modifiedMaxicode: GeneratedMaxicode?
    @Published var isWorking = false
    @Published var activityMessage = ""
    @Published var errorMessage: String?
    @Published var hasBootstrapped = false
    @Published var outputDirectoryPath = ""
    @Published var previewFTIDInfo: FTIDInfo?
    @Published var trackingEntries: [TrackingEntry] = []
    @Published var trackingStats = TrackingStats(total: 0, active: 0, delivered: 0, exception: 0, byCarrier: [:], byStatus: [:])
    @Published var startupIssues: [String] = []
    @Published var startupWarnings: [String] = []

    let bridge = PythonBridgeService()

    func bootstrapIfNeeded() async {
        guard !hasBootstrapped else { return }
        await runActivity("Loading backend…") { [self] in
            let snapshot: HealthSnapshot = try await self.bridge.execute("health")
            self.settings = snapshot.settings
            self.outputDirectoryPath = snapshot.outputDir
            self.applyPreviousInputs(snapshot.previousInputs, overwrite: true)
            self.history = snapshot.historyEntries
            self.previousMaxicodeEntries = snapshot.previousMaxicodeEntries
            self.syncDefaultSenderZip()
            self.startupIssues = snapshot.diagnostics?.issues ?? []
            self.startupWarnings = snapshot.diagnostics?.warnings ?? []
            if snapshot.resourcesOK == false, self.startupIssues.isEmpty {
                self.startupIssues = ["One or more bundled backend resources are missing. Check Settings or reinstall the app."]
            }
            self.hasBootstrapped = true
        }
        await refreshTracking()
    }

    func login(userID: String, passcode: String) async {
        await runActivity("Authenticating…") { [self] in
            let snapshot: LoginSnapshot = try await self.bridge.execute(
                "login",
                payload: ["user_id": userID, "passcode": passcode]
            )
            self.session = UserSession(userID: snapshot.userID, passcode: passcode, remainingRuns: snapshot.remainingRuns)
            self.settings = snapshot.settings
            self.applyPreviousInputs(snapshot.previousInputs, overwrite: true)
            self.history = snapshot.historyEntries
            self.previousMaxicodeEntries = snapshot.previousMaxicodeEntries
            self.syncDefaultSenderZip()
        }
    }

    func signOut() {
        session = nil
        lastGenerated = nil
        recentGenerations = []
        importPreview = nil
        importSummary = nil
        importMappings = [:]
        selectedImportFilePath = nil
        generatedMaxicode = nil
        modifiedMaxicode = nil
        history = []
        previousMaxicodeEntries = []
        upsForm = LabelFormState()
        uspsForm = LabelFormState()
        fedexForm = LabelFormState()
        syncDefaultSenderZip()
    }

    func refreshAll() async {
        await runActivity("Refreshing data…") { [self] in
            let refreshedSettings: AppSettings = try await self.bridge.execute("settings_get")
            self.settings = refreshedSettings
            try await self.refreshCollections()
        }
    }

    func generateLabel(for carrier: Carrier) async {
        guard let session else {
            errorMessage = "Please sign in before generating a label."
            return
        }

        let form = formState(for: carrier)
        if let validationError = validate(form: form, carrier: carrier) {
            errorMessage = validationError
            return
        }

        await runActivity("Generating \(carrier.rawValue) label…") { [self] in
            let result: LabelGenerationResult = try await self.bridge.execute(
                "generate_label",
                payload: [
                    "user_id": session.userID,
                    "passcode": session.passcode,
                    "carrier": carrier.rawValue,
                    "sender_zip": form.senderZIP.trimmingCharacters(in: .whitespacesAndNewlines),
                    "receiver_zip": form.receiverZIP.trimmingCharacters(in: .whitespacesAndNewlines),
                    "tracking": form.tracking.uppercased().replacingOccurrences(of: " ", with: ""),
                    "address_type": form.addressType.rawValue,
                ]
            )
            try self.validateGeneratedLabel(result, for: carrier)
            self.recordGeneration(result)
            self.session?.remainingRuns = result.remainingRuns
            try await self.refreshCollections()
        }
    }

    private func recordGeneration(_ result: LabelGenerationResult) {
        lastGenerated = result
        recentGenerations.insert(result, at: 0)
        if recentGenerations.count > 12 {
            recentGenerations.removeLast(recentGenerations.count - 12)
        }
    }

    func regenerate(historyEntry: HistoryEntry) async {
        guard let session else {
            errorMessage = "Please sign in before regenerating a label."
            return
        }

        await runActivity("Regenerating label…") { [self] in
            let result: LabelGenerationResult = try await self.bridge.execute(
                "regenerate_history",
                payload: [
                    "user_id": session.userID,
                    "passcode": session.passcode,
                    "method": historyEntry.method,
                    "sender_zip": historyEntry.senderZip,
                    "receiver_zip": historyEntry.receiverZip,
                    "original_tracking": historyEntry.originalTracking,
                ]
            )
            if let carrier = Carrier(methodName: result.method) {
                try self.validateGeneratedLabel(result, for: carrier)
            }
            self.recordGeneration(result)
            self.session?.remainingRuns = result.remainingRuns
            try await self.refreshCollections()
        }
    }

    func regenerate(previousEntry: PreviousMaxicodeEntry) async {
        guard let session else {
            errorMessage = "Please sign in before regenerating a MaxiCode entry."
            return
        }

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let entryData = try? encoder.encode(previousEntry)
        let entryJSONObject = (entryData.flatMap { try? JSONSerialization.jsonObject(with: $0) }) as? [String: Any] ?? [:]

        await runActivity("Reusing previous MaxiCode entry…") { [self] in
            let result: LabelGenerationResult = try await self.bridge.execute(
                "regenerate_previous_maxicode",
                payload: [
                    "user_id": session.userID,
                    "passcode": session.passcode,
                    "entry": entryJSONObject,
                ]
            )
            if let carrier = Carrier(methodName: result.method) {
                try self.validateGeneratedLabel(result, for: carrier)
            }
            self.recordGeneration(result)
            self.session?.remainingRuns = result.remainingRuns
            try await self.refreshCollections()
        }
    }

    func loadImportPreview(from url: URL) async {
        await runActivity("Inspecting import file…") { [self] in
            let preview: ImportPreview = try await self.bridge.execute(
                "import_preview",
                payload: ["file_path": url.path]
            )
            self.selectedImportFilePath = preview.filePath
            self.importPreview = preview
            self.importMappings = preview.autoMappings
            self.importSummary = nil
        }
    }

    func createImportTemplate(at url: URL) async {
        await runActivity("Creating template…") { [self] in
            struct TemplateResult: Decodable {
                let targetPath: String

                enum CodingKeys: String, CodingKey {
                    case targetPath = "target_path"
                }
            }

            _ = try await self.bridge.execute(
                "create_import_template",
                payload: ["target_path": url.path],
                as: TemplateResult.self
            )
        }
    }

    func processImport() async {
        guard let session else {
            errorMessage = "Please sign in before processing an import."
            return
        }
        guard let filePath = selectedImportFilePath else {
            errorMessage = "Choose an import file first."
            return
        }

        let filteredMappings = importMappings.filter { !$0.value.isEmpty }
        await runActivity("Processing import…") { [self] in
            let result: ImportProcessResult = try await self.bridge.execute(
                "import_process",
                payload: [
                    "user_id": session.userID,
                    "passcode": session.passcode,
                    "file_path": filePath,
                    "mappings": filteredMappings,
                ]
            )
            try self.validateImportedLabels(result)
            self.importSummary = result
            self.session?.remainingRuns = result.remainingRuns
            try await self.refreshCollections()
        }
    }

    func generateMaxicode() async {
        await runActivity("Generating MaxiCode data…") { [self] in
            self.generatedMaxicode = try await self.bridge.execute("maxicode_generate")
        }
    }

    func modifyMaxicode(from source: String) async {
        guard !source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            errorMessage = "Paste MaxiCode data before trying to modify it."
            return
        }

        await runActivity("Modifying MaxiCode data…") { [self] in
            self.modifiedMaxicode = try await self.bridge.execute(
                "maxicode_modify",
                payload: ["data": source]
            )
        }
    }

    func saveSettings(_ updated: AppSettings) async {
        await runActivity("Saving settings…") { [self] in
            let refreshed: AppSettings = try await self.bridge.execute(
                "settings_update",
                payload: ["values": updated.bridgeValues]
            )
            self.settings = refreshed
            self.syncDefaultSenderZip()
        }
    }

    func resetSettings() async -> AppSettings? {
        await runActivity("Resetting settings…") { [self] in
            self.settings = try await self.bridge.execute("settings_reset")
            self.syncDefaultSenderZip()
        }
        return settings
    }

    func exportSettings(to url: URL) async {
        await runActivity("Exporting settings…") { [self] in
            struct ExportResult: Decodable {
                let targetPath: String
                enum CodingKeys: String, CodingKey { case targetPath = "target_path" }
            }

            _ = try await self.bridge.execute(
                "settings_export",
                payload: ["target_path": url.path],
                as: ExportResult.self
            )
        }
    }

    func importSettings(from url: URL) async -> AppSettings? {
        await runActivity("Importing settings…") { [self] in
            let imported: AppSettings = try await self.bridge.execute(
                "settings_import",
                payload: ["source_path": url.path]
            )
            self.settings = imported
            self.syncDefaultSenderZip()
        }
        return settings
    }

    func lookup(zip: String) async -> ZipLookupResult? {
        guard zip.count == 5 else {
            errorMessage = "ZIP codes must be 5 digits."
            return nil
        }

        return await runActivity("Looking up ZIP code…") { [self] in
            try await self.bridge.execute("lookup_zip", payload: ["zip_code": zip])
        }
    }

    func formBinding(for carrier: Carrier) -> LabelFormState {
        switch carrier {
        case .ups:
            return upsForm
        case .usps:
            return uspsForm
        case .fedex:
            return fedexForm
        }
    }

    func setForm(_ form: LabelFormState, for carrier: Carrier) {
        switch carrier {
        case .ups:
            upsForm = form
        case .usps:
            uspsForm = form
        case .fedex:
            fedexForm = form
        }
    }

    func openPath(_ path: String) {
        guard !path.isEmpty else {
            errorMessage = "There is no file to open yet."
            return
        }
        guard FileManager.default.fileExists(atPath: path) else {
            errorMessage = "The file could not be found:\n\(path)\n\nIt may have been moved or deleted."
            return
        }
        if !NSWorkspace.shared.open(URL(fileURLWithPath: path)) {
            errorMessage = "macOS could not open this file:\n\(path)"
        }
    }

    @discardableResult
    func exportText(_ content: String, to url: URL) -> Bool {
        do {
            try content.write(to: url, atomically: true, encoding: .utf8)
            return true
        } catch {
            errorMessage = "Could not save the file:\n\(error.localizedDescription)"
            return false
        }
    }

    func revealPath(_ path: String) {
        guard !path.isEmpty, FileManager.default.fileExists(atPath: path) else {
            errorMessage = "The item could not be found:\n\(path)"
            return
        }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
    }

    func openOutputDirectory() {
        guard !outputDirectoryPath.isEmpty else {
            errorMessage = "No output directory is configured yet."
            return
        }
        openPath(outputDirectoryPath)
    }

    private func refreshCollections() async throws {
        let snapshot: CollectionsSnapshot = try await bridge.execute("collections")
        history = snapshot.historyEntries
        previousMaxicodeEntries = snapshot.previousMaxicodeEntries
        applyPreviousInputs(snapshot.previousInputs, overwrite: false)
        syncDefaultSenderZip()
    }

    private func applyPreviousInputs(_ inputs: PreviousInputState, overwrite: Bool) {
        let addressType: AddressType = inputs.addressType.uppercased() == "R" ? .real : .fake

        updateForm(&upsForm, senderZIP: inputs.senderZip, receiverZIP: inputs.receiverZip, tracking: inputs.upsTracking, addressType: addressType, overwrite: overwrite)
        updateForm(&uspsForm, senderZIP: inputs.senderZip, receiverZIP: inputs.receiverZip, tracking: inputs.uspsTracking, addressType: addressType, overwrite: overwrite)
        updateForm(&fedexForm, senderZIP: inputs.senderZip, receiverZIP: inputs.receiverZip, tracking: inputs.fedexTracking, addressType: addressType, overwrite: overwrite)
    }

    private func updateForm(
        _ form: inout LabelFormState,
        senderZIP: String,
        receiverZIP: String,
        tracking: String,
        addressType: AddressType,
        overwrite: Bool
    ) {
        if overwrite || form.senderZIP.isEmpty {
            form.senderZIP = senderZIP
        }
        if overwrite || form.receiverZIP.isEmpty {
            form.receiverZIP = receiverZIP
        }
        if overwrite || form.tracking.isEmpty {
            form.tracking = tracking
        }
        if overwrite || form.addressType == .fake {
            form.addressType = addressType
        }
    }

    private func syncDefaultSenderZip() {
        let defaultZIP = settings.fromAddress.zipCode
        guard !defaultZIP.isEmpty else { return }

        if upsForm.senderZIP.isEmpty { upsForm.senderZIP = defaultZIP }
        if uspsForm.senderZIP.isEmpty { uspsForm.senderZIP = defaultZIP }
        if fedexForm.senderZIP.isEmpty { fedexForm.senderZIP = defaultZIP }
    }

    private func formState(for carrier: Carrier) -> LabelFormState {
        switch carrier {
        case .ups:
            return upsForm
        case .usps:
            return uspsForm
        case .fedex:
            return fedexForm
        }
    }

    private func validate(form: LabelFormState, carrier: Carrier) -> String? {
        let sender = form.senderZIP.trimmingCharacters(in: .whitespacesAndNewlines)
        let receiver = form.receiverZIP.trimmingCharacters(in: .whitespacesAndNewlines)

        guard sender.count == 5, CharacterSet.decimalDigits.isSuperset(of: CharacterSet(charactersIn: sender)) else {
            return "Sender ZIP must be exactly 5 digits."
        }
        guard receiver.count == 5, CharacterSet.decimalDigits.isSuperset(of: CharacterSet(charactersIn: receiver)) else {
            return "Receiver ZIP must be exactly 5 digits."
        }
        return carrier.validateTracking(form.tracking)
    }

    private func validateGeneratedLabel(_ result: LabelGenerationResult, for carrier: Carrier) throws {
        guard result.matchesExpectedBlankTemplate(for: carrier) else {
            let actual = URL(fileURLWithPath: result.labelPath).lastPathComponent
            throw AppModelError.unexpectedLabelTemplate(
                carrier: carrier,
                expected: carrier.finalTemplateFilename,
                actual: actual.isEmpty ? result.labelPath : actual
            )
        }
    }

    private func validateImportedLabels(_ result: ImportProcessResult) throws {
        for row in result.processedRows {
            guard let carrier = Carrier(methodName: row.method) else {
                continue
            }

            let filename = URL(fileURLWithPath: row.labelPath).lastPathComponent.lowercased()
            guard filename.hasPrefix(carrier.finalTemplateStem), filename.hasSuffix(".png"), !filename.contains("_full") else {
                throw AppModelError.unexpectedLabelTemplate(
                    carrier: carrier,
                    expected: carrier.finalTemplateFilename,
                    actual: filename.isEmpty ? row.labelPath : filename
                )
            }
        }
    }

    private var activityCount = 0

    @discardableResult
    func runActivity<Result>(
        _ message: String,
        operation: @escaping () async throws -> Result
    ) async -> Result? {
        activityCount += 1
        isWorking = true
        activityMessage = message
        defer {
            activityCount -= 1
            if activityCount <= 0 {
                activityCount = 0
                isWorking = false
                activityMessage = ""
            }
        }

        do {
            return try await operation()
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    func fetchPreviewElements(for carrier: Carrier, ftidInfo: FTIDInfo? = nil, layoutOverrides: [String: Any]? = nil) async -> PreviewElements? {
        var payload: [String: Any] = ["carrier": carrier.rawValue]
        if let info = ftidInfo ?? lastGenerated?.ftidInfo {
            self.previewFTIDInfo = info
            let enc = JSONEncoder()
            if let data = try? enc.encode(info),
               let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                payload["ftid_info"] = dict
            }
        }
        if let layoutOverrides = layoutOverrides {
            let carrierKey = carrier.rawValue.lowercased()
            if layoutOverrides["barcode"] == nil,
               layoutOverrides["maxicode"] == nil,
               let selectedCarrierLayout = layoutOverrides[carrierKey] as? [String: Any] {
                payload["layout_overrides"] = selectedCarrierLayout
            } else {
                payload["layout_overrides"] = layoutOverrides
            }
        }
        struct PreviewResponse: Decodable {
            let composite: String?
            let baseTemplate: String?
            let barcode: String?
            let maxicode: String?
            let zipBarcode: String?
            let ftidInfo: FTIDInfo?
            let templateWidth: Int?
            let templateHeight: Int?

            enum CodingKeys: String, CodingKey {
                case composite
                case baseTemplate = "base_template"
                case barcode, maxicode
                case zipBarcode = "zip_barcode"
                case ftidInfo = "ftid_info"
                case templateWidth = "template_width"
                case templateHeight = "template_height"
            }
        }

        let result: PreviewResponse? = try? await bridge.execute("render_preview_elements", payload: payload)
        guard let result else { return nil }

        func loadImage(_ path: String?) -> NSImage? {
            guard let path, !path.isEmpty,
                  FileManager.default.fileExists(atPath: path) else { return nil }
            return NSImage(contentsOfFile: path)
        }

        if let info = result.ftidInfo {
            self.previewFTIDInfo = info
        }

        let pixelSize: CGSize?
        if let width = result.templateWidth, let height = result.templateHeight, width > 0, height > 0 {
            pixelSize = CGSize(width: width, height: height)
        } else {
            pixelSize = nil
        }

        return PreviewElements(
            composite: loadImage(result.composite) ?? loadImage(result.baseTemplate),
            template: loadImage(result.baseTemplate),
            barcode: loadImage(result.barcode),
            maxicode: loadImage(result.maxicode),
            zipBarcode: loadImage(result.zipBarcode),
            pixelSize: pixelSize
        )
    }

    // MARK: - Package Tracking

    func refreshTracking() async {
        await runActivity("Refreshing tracking data…") { [self] in
            let response: TrackingListResponse = try await self.bridge.execute("tracking_list")
            self.trackingEntries = response.entries
            self.trackingStats = response.stats
        }
    }

    func addTrackingEntry(
        trackingNumber: String,
        carrier: String,
        label: String,
        store: String,
        originZip: String,
        destinationZip: String
    ) async {
        await runActivity("Adding tracking entry…") { [self] in
            let entry: TrackingEntry = try await self.bridge.execute(
                "tracking_add",
                payload: [
                    "tracking_number": trackingNumber,
                    "carrier": carrier,
                    "label": label,
                    "store": store,
                    "origin_zip": originZip,
                    "destination_zip": destinationZip,
                ]
            )
            self.trackingEntries.insert(entry, at: 0)
            try await self.refreshTrackingStats()
        }
    }

    func deleteTrackingEntry(id: String) async {
        await runActivity("Deleting tracking entry…") { [self] in
            let _: [String: Bool] = try await self.bridge.execute(
                "tracking_delete",
                payload: ["entry_id": id]
            )
            self.trackingEntries.removeAll { $0.id == id }
            try await self.refreshTrackingStats()
        }
    }

    func refreshTrackingEntry(id: String) async {
        await runActivity("Refreshing tracking status…") { [self] in
            let entry: TrackingEntry = try await self.bridge.execute(
                "tracking_detail",
                payload: ["entry_id": id]
            )
            if let index = self.trackingEntries.firstIndex(where: { $0.id == id }) {
                self.trackingEntries[index] = entry
            }
        }
    }

    func refreshTrackingStats() async throws {
        let stats: TrackingStats = try await bridge.execute("tracking_stats")
        self.trackingStats = stats
    }

    func importTrackingFromSheet(rows: [[String: String]]) async -> Int {
        await runActivity("Importing from sheet…") { [self] in
            struct ImportResponse: Codable {
                let addedCount: Int
                enum CodingKeys: String, CodingKey {
                    case addedCount = "added_count"
                }
            }
            let result: ImportResponse = try await self.bridge.execute(
                "tracking_import_sheet",
                payload: ["rows": rows]
            )
            await self.refreshTracking()
            return result.addedCount
        }
        return 0
    }
}

struct PreviewElements {
    let composite: NSImage?
    let template: NSImage?
    let barcode: NSImage?
    let maxicode: NSImage?
    let zipBarcode: NSImage?
    let pixelSize: CGSize?
}
