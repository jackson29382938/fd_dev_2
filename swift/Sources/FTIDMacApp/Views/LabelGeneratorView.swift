import AppKit
import SwiftUI

struct LabelGeneratorView: View {
    @EnvironmentObject private var model: AppModel
    let carrier: Carrier
    @Binding var form: LabelFormState

    private var validationMessages: [String] {
        var messages: [String] = []
        let sender = form.senderZIP.trimmingCharacters(in: .whitespacesAndNewlines)
        let receiver = form.receiverZIP.trimmingCharacters(in: .whitespacesAndNewlines)
        let tracking = normalizedTracking

        if sender.count != 5 || !sender.allSatisfy(\.isNumber) {
            messages.append("Sender ZIP must be exactly 5 digits.")
        }
        if receiver.count != 5 || !receiver.allSatisfy(\.isNumber) {
            messages.append("Receiver ZIP must be exactly 5 digits.")
        }
        if let trackingError = carrier.validateTracking(tracking) {
            messages.append(trackingError)
        }
        return messages
    }

    private var canGenerate: Bool {
        validationMessages.isEmpty && !model.isWorking
    }

    private var normalizedTracking: String {
        form.tracking
            .uppercased()
            .replacingOccurrences(of: " ", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                header
                inputSection
                validationSection
                actionsSection
                latestOutputSection
            }
            .padding(28)
        }
        .onChange(of: form.senderZIP) { _, newValue in
            let filtered = newValue.filter(\.isNumber).prefix(5)
            let normalized = String(filtered)
            if normalized != newValue { form.senderZIP = normalized }
        }
        .onChange(of: form.receiverZIP) { _, newValue in
            let filtered = newValue.filter(\.isNumber).prefix(5)
            let normalized = String(filtered)
            if normalized != newValue { form.receiverZIP = normalized }
        }
        .onChange(of: form.tracking) { _, newValue in
            let normalized = newValue
                .uppercased()
                .filter { $0.isNumber || $0.isLetter }
            if normalized != newValue { form.tracking = String(normalized) }
        }
    }

    private var lastGeneratedForCarrier: LabelGenerationResult? {
        guard let result = model.lastGenerated, result.method == carrier.methodName else {
            return nil
        }
        return result
    }

    private var recentForCarrier: [LabelGenerationResult] {
        Array(model.recentGenerations.filter { $0.method == carrier.methodName }.prefix(3))
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(carrier.title, systemImage: carrier.systemImage)
                .font(.system(size: 30, weight: .bold, design: .rounded))
                .foregroundStyle(carrier.accentColor)
            Text("Create a \(carrier.rawValue) label using the Python backend, current settings, and your active subscription session.")
                .foregroundStyle(.secondary)
        }
    }

    private var inputSection: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 16) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Sender ZIP")
                            .font(.headline)
                        TextField("5-digit ZIP", text: $form.senderZIP)
                            .textFieldStyle(.roundedBorder)
                            .font(.system(.body, design: .monospaced))
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Receiver ZIP")
                            .font(.headline)
                        TextField("5-digit ZIP", text: $form.receiverZIP)
                            .textFieldStyle(.roundedBorder)
                            .font(.system(.body, design: .monospaced))
                    }
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("Tracking Number")
                        .font(.headline)
                    TextField(carrier.trackingPlaceholder, text: $form.tracking)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(.body, design: .monospaced))
                        .onSubmit {
                            guard canGenerate else { return }
                            form.tracking = normalizedTracking
                            Task { await model.generateLabel(for: carrier) }
                        }
                    HStack(spacing: 8) {
                        Text("Normalized:")
                            .foregroundStyle(.secondary)
                        Text(normalizedTracking.isEmpty ? carrier.trackingPlaceholder : normalizedTracking)
                            .font(.caption.monospaced())
                            .foregroundStyle(normalizedTracking.isEmpty ? .tertiary : .secondary)
                    }
                    .font(.caption)
                }

                Picker("Address Type", selection: $form.addressType) {
                    ForEach(AddressType.allCases) { addressType in
                        Text(addressType.title).tag(addressType)
                    }
                }
                .pickerStyle(.segmented)
            }
            .padding(8)
        } label: {
            Text("Generation Inputs")
        }
    }

    @ViewBuilder
    private var validationSection: some View {
        if !validationMessages.isEmpty {
            GroupBox {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(validationMessages, id: \.self) { message in
                        Label(message, systemImage: "exclamationmark.triangle.fill")
                            .font(.caption)
                            .foregroundStyle(.orange)
                    }
                }
                .padding(8)
            } label: {
                Text("Input Checks")
            }
        }
    }

    private var actionsSection: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) { actionButtons }
            VStack(alignment: .leading, spacing: 10) { actionButtons }
        }
    }

    @ViewBuilder
    private var actionButtons: some View {
        Button {
            form.tracking = normalizedTracking
            Task { await model.generateLabel(for: carrier) }
        } label: {
            Label("Generate Label", systemImage: "sparkles.rectangle.stack.fill")
        }
        .buttonStyle(.borderedProminent)
        .tint(carrier.accentColor)
        .disabled(!canGenerate)
        .help(canGenerate ? "Generate the label with the current inputs." : "Fix the input checks before generating.")

        Button {
            model.openOutputDirectory()
        } label: {
            Label("Output Folder", systemImage: "folder")
        }
        .disabled(model.outputDirectoryPath.isEmpty)

        if let lastGenerated = lastGeneratedForCarrier {
            Button {
                model.openPath(lastGenerated.labelPath)
            } label: {
                Label("Open Latest", systemImage: "photo")
            }
        }
    }

    @ViewBuilder
    private var latestOutputSection: some View {
        let recent = recentForCarrier
        if !recent.isEmpty {
            GroupBox {
                VStack(alignment: .leading, spacing: 14) {
                    ForEach(Array(recent.enumerated()), id: \.offset) { index, result in
                        if index > 0 {
                            Divider()
                        }
                        outputRow(result, isLatest: index == 0)
                    }
                }
                .padding(8)
            } label: {
                Text(recent.count > 1 ? "Recent Outputs" : "Most Recent Output")
            }
        }
    }

    @ViewBuilder
    private func outputRow(_ result: LabelGenerationResult, isLatest: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(result.method.replacingOccurrences(of: "FTID_", with: ""))
                    .font(isLatest ? .headline : .subheadline.weight(.semibold))
                if isLatest {
                    Text("Latest")
                        .font(.caption2.weight(.semibold))
                        .padding(.horizontal, 7)
                        .padding(.vertical, 2)
                        .background(carrier.accentColor.opacity(0.18), in: Capsule())
                        .foregroundStyle(carrier.accentColor)
                }
                Spacer()
                Text(result.templateName ?? carrier.finalTemplateFilename)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(carrier.accentColor)
            }

            Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 4) {
                GridRow {
                    Text("Original").font(.caption).foregroundStyle(.secondary)
                    Text(result.ftidInfo.originalTracking)
                        .font(.system(.body, design: .monospaced))
                        .textSelection(.enabled)
                }
                if result.ftidInfo.trackingNumber != result.ftidInfo.originalTracking {
                    GridRow {
                        Text("Generated").font(.caption).foregroundStyle(.secondary)
                        Text(result.ftidInfo.trackingNumber)
                            .font(.system(.body, design: .monospaced))
                            .textSelection(.enabled)
                    }
                }
            }

            if isLatest {
                Text(result.labelPath)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
                Text("Remaining runs: \(result.remainingRuns)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            ViewThatFits(in: .horizontal) {
                HStack(spacing: 10) { outputRowButtons(result) }
                VStack(alignment: .leading, spacing: 8) { outputRowButtons(result) }
            }
            .controlSize(isLatest ? .regular : .small)
        }
    }

    @ViewBuilder
    private func outputRowButtons(_ result: LabelGenerationResult) -> some View {
        Button {
            model.openPath(result.labelPath)
        } label: {
            Label("Open Label", systemImage: "photo")
        }
        .buttonStyle(.bordered)

        Button {
            model.revealPath(result.labelPath)
        } label: {
            Label("Show in Finder", systemImage: "folder")
        }
        .buttonStyle(.bordered)

        Button {
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(result.labelPath, forType: .string)
        } label: {
            Label("Copy Path", systemImage: "doc.on.doc")
        }
        .buttonStyle(.bordered)
    }
}
