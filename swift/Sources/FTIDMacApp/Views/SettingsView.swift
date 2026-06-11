import AppKit
import SwiftUI

private struct LabeledSlider: View {
    let label: String
    @Binding var value: Double
    var range: ClosedRange<Double>
    var step: Double

    var body: some View {
        HStack(spacing: 6) {
            Text(label).font(.caption).foregroundStyle(.secondary).frame(width: 76, alignment: .trailing)
            Slider(value: $value, in: range, step: step).labelsHidden()
            Text(formatValue(value)).font(.caption.monospacedDigit()).frame(width: 54, alignment: .trailing)
        }
    }

    private func formatValue(_ v: Double) -> String {
        if step >= 1 { return "\(Int(v))" }
        if step < 0.1 { return String(format: "%.2f", v) }
        return String(format: "%.1f", v)
    }
}

private struct IntSlider: View {
    let label: String
    @Binding var value: Int
    var range: ClosedRange<Int>
    var step: Int = 1

    var body: some View {
        LabeledSlider(label: label, value: Binding(get: { Double(value) }, set: { value = Int($0) }), range: Double(range.lowerBound)...Double(range.upperBound), step: Double(step))
    }
}

struct SettingsView: View {
    @EnvironmentObject private var model: AppModel
    @State private var draft = AppSettings.defaultValue
    @State private var selectedLayoutCarrier: Carrier = .ups
    @State private var previewComposite: NSImage?
    @State private var previewTemplate: NSImage?
    @State private var previewBarcode: NSImage?
    @State private var previewMaxicode: NSImage?
    @State private var previewZipBarcode: NSImage?
    @State private var previewPixelSize: CGSize?
    @State private var isSaving = false
    @State private var isPreviewLoading = false
    @State private var previewReloadTask: Task<Void, Never>?
    @State private var showPreviewGuides = true

    private var currentLayout: Binding<LabelLayout.CarrierLayout> { carrierLayoutBinding(for: selectedLayoutCarrier) }
    private var hasUnsavedChanges: Bool { draft != model.settings }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                headerSection
                Divider().padding(.bottom, 20)
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 320, maximum: 500), spacing: 20)], spacing: 20) {
                    fromAddressSection
                    maxicodeSection
                    fileImportSection
                    previousMaxicodeSection
                    zipLookupSection
                    uiSection
                }
                .padding(.bottom, 24)
                Divider().padding(.bottom, 20)
                labelLayoutSection
                Divider().padding(.vertical, 20)
                actionBar
            }
            .padding(28)
        }
        .task {
            await model.bootstrapIfNeeded()
            draft = model.settings
            await loadPreviewElements()
        }
        .onChange(of: model.settings) { _, newValue in draft = newValue; schedulePreviewReload() }
        .onChange(of: selectedLayoutCarrier) { _, _ in clearPreviewElements(); schedulePreviewReload(immediate: true) }
        .onChange(of: draft.labelLayout) { _, _ in schedulePreviewReload() }
        .onDisappear { previewReloadTask?.cancel() }
    }

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Settings").font(.system(size: 28, weight: .bold, design: .rounded))
            Text("Configure generation, import, and layout preferences. Layout changes apply per-carrier.")
                .font(.subheadline).foregroundStyle(.secondary)
        }
        .padding(.bottom, 20)
    }

    private var actionBar: some View {
        HStack(spacing: 12) {
            Button { Task { await saveSettings() } } label: { Label(isSaving ? "Saving…" : "Save Settings", systemImage: "checkmark.circle.fill") }
                .buttonStyle(.borderedProminent).disabled(isSaving || model.isWorking || !hasUnsavedChanges)
            if hasUnsavedChanges { Text("Unsaved changes").font(.caption).foregroundStyle(.secondary) }
            Divider().frame(height: 24)
            Button {
                guard let url = FilePanelService.chooseSettingsExportDestination(defaultName: "settings_configuration.json") else { return }
                Task { await model.exportSettingsConfiguration(to: url) }
            } label: { Label("Export", systemImage: "square.and.arrow.up") }.buttonStyle(.bordered).disabled(model.isWorking || isSaving)
            Button {
                guard let url = FilePanelService.chooseSettingsImportFile() else { return }
                Task { if let imported = await model.importSettingsConfiguration(from: url) { draft = imported } }
            } label: { Label("Import", systemImage: "square.and.arrow.down") }.buttonStyle(.bordered).disabled(model.isWorking || isSaving)
            Spacer()
            Button(role: .destructive) { Task { if let reset = await model.resetSettings() { draft = reset } } } label: { Label("Reset All", systemImage: "arrow.counterclockwise") }
                .buttonStyle(.bordered).disabled(model.isWorking || isSaving)
        }
    }

    private var fromAddressSection: some View {
        SettingsCard(icon: "mappin.circle.fill", title: "From Address", subtitle: "Default sender info") {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    TextField("ZIP", text: $draft.fromAddress.zipCode).textFieldStyle(.roundedBorder).frame(width: 70)
                    TextField("City", text: $draft.fromAddress.city).textFieldStyle(.roundedBorder)
                    TextField("State", text: $draft.fromAddress.state).textFieldStyle(.roundedBorder).frame(width: 50)
                }
                Button { Task { if let lookup = await model.lookup(zip: draft.fromAddress.zipCode) { draft.fromAddress.city = lookup.city; draft.fromAddress.state = lookup.state } } } label: { Label("Auto-fill from ZIP", systemImage: "arrow.triangle.2.circlepath") }
                    .buttonStyle(.bordered).controlSize(.small)
            }
        }
    }

    private var maxicodeSection: some View { SettingsCard(icon: "qrcode", title: "MaxiCode", subtitle: "Generation options") { VStack(alignment: .leading, spacing: 8) { Toggle("Auto-generate", isOn: $draft.maxicode.autoGenerate); Toggle("No character limit", isOn: $draft.maxicode.noCharacterLimit); Toggle("Manual mode", isOn: $draft.maxicode.manualMode); Toggle("Prompt input method", isOn: $draft.maxicode.promptInputMethod) }.toggleStyle(.checkbox) } }
    private var fileImportSection: some View { SettingsCard(icon: "doc.text.fill", title: "File Import", subtitle: "Import preferences") { VStack(alignment: .leading, spacing: 8) { Picker("Default Format", selection: $draft.fileImport.defaultFormat) { Text("Excel").tag("excel"); Text("CSV").tag("csv") }.pickerStyle(.segmented); Toggle("Auto-detect columns", isOn: $draft.fileImport.autoDetectColumns); Toggle("Batch processing", isOn: $draft.fileImport.batchProcessing) }.toggleStyle(.checkbox) } }
    private var previousMaxicodeSection: some View { SettingsCard(icon: "clock.arrow.circlepath", title: "Previous MaxiCode", subtitle: "History") { VStack(alignment: .leading, spacing: 8) { Toggle("Enable history", isOn: $draft.previousMaxicode.enabled); Stepper("Max entries: \(draft.previousMaxicode.maxEntries)", value: $draft.previousMaxicode.maxEntries, in: 1...10); Toggle("Show preview", isOn: $draft.previousMaxicode.showPreview) }.toggleStyle(.checkbox) } }
    private var zipLookupSection: some View { SettingsCard(icon: "location.fill", title: "ZIP Lookup", subtitle: "Address resolution") { VStack(alignment: .leading, spacing: 8) { Toggle("Auto-identify ZIP data", isOn: $draft.zipLookup.autoIdentify); Toggle("Use API fallback", isOn: $draft.zipLookup.useAPIFallback); Toggle("Cache lookups", isOn: $draft.zipLookup.cacheResults) }.toggleStyle(.checkbox) } }
    private var uiSection: some View { SettingsCard(icon: "paintbrush.fill", title: "Interface", subtitle: "Appearance") { VStack(alignment: .leading, spacing: 8) { Picker("Theme", selection: $draft.ui.theme) { Text("System").tag("default"); Text("Dark").tag("dark"); Text("Light").tag("light") }.pickerStyle(.segmented); Toggle("Show tooltips", isOn: $draft.ui.showTooltips); Toggle("Compact mode", isOn: $draft.ui.compactMode) }.toggleStyle(.checkbox) } }

    private var labelLayoutSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Label Layout").font(.title2.weight(.bold))
                    Text("Every label element exposes position, size, scale, and content controls. Drag elements in the preview to move them.").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
            }
            HStack(alignment: .top, spacing: 20) {
                VStack(alignment: .leading, spacing: 12) {
                    carrierPicker
                    HStack {
                        Button("Choose Template") { chooseCustomTemplate() }.buttonStyle(.bordered).controlSize(.small)
                        Button("Clear Template") { currentLayout.customTemplatePath.wrappedValue = nil; schedulePreviewReload(immediate: true) }.buttonStyle(.bordered).controlSize(.small)
                        Spacer()
                        Button("Reset") { resetCarrierDefaults(); schedulePreviewReload(immediate: true) }.buttonStyle(.bordered).controlSize(.small)
                    }
                    if let customPath = currentLayout.customTemplatePath.wrappedValue, !customPath.isEmpty {
                        Text("Custom template: \(URL(fileURLWithPath: customPath).lastPathComponent). Used for preview and generation.")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    ScrollView(.vertical, showsIndicators: true) {
                        VStack(alignment: .leading, spacing: 12) { carrierLayoutControls(for: selectedLayoutCarrier) }.padding(.trailing, 4)
                    }
                    .frame(maxHeight: 560)
                }
                .frame(minWidth: 380, maxWidth: 460)
                Divider().frame(height: 320)
                previewPanel
            }
        }
    }

    private var carrierPicker: some View {
        HStack(spacing: 0) {
            ForEach(Carrier.allCases) { carrier in
                Button { selectedLayoutCarrier = carrier } label: {
                    VStack(spacing: 3) { Image(systemName: carrier.systemImage).font(.title3); Text(carrier.rawValue).font(.caption2.weight(.medium)) }
                        .frame(maxWidth: .infinity).padding(.vertical, 8)
                        .background(RoundedRectangle(cornerRadius: 8).fill(selectedLayoutCarrier == carrier ? carrier.accentColor.opacity(0.15) : Color.clear))
                        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(selectedLayoutCarrier == carrier ? carrier.accentColor : Color.clear, lineWidth: 1.5))
                        .foregroundColor(selectedLayoutCarrier == carrier ? carrier.accentColor : .secondary)
                }.buttonStyle(.plain)
            }
        }.padding(4).background(Color(nsColor: .controlBackgroundColor)).cornerRadius(10)
    }

    private var previewPanel: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Label("Preview", systemImage: "eye.fill").font(.subheadline.weight(.semibold))
                if isPreviewLoading {
                    ProgressView().controlSize(.small)
                    Text("Updating…").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Toggle("Guides", isOn: $showPreviewGuides).font(.caption).toggleStyle(.checkbox)
                Button { schedulePreviewReload(immediate: true) } label: { Image(systemName: "arrow.clockwise") }.buttonStyle(.bordered).controlSize(.mini)
            }
            ZStack {
                Color(nsColor: .textBackgroundColor)
                if let composite = previewComposite {
                    LabelPreviewView(
                        layout: currentLayout,
                        ftidInfo: model.previewFTIDInfo,
                        compositeImage: composite,
                        templateImage: previewTemplate,
                        barcodeImage: previewBarcode,
                        maxicodeImage: previewMaxicode,
                        zipBarcodeImage: previewZipBarcode,
                        templatePixelSize: previewPixelSize,
                        showElementFrames: showPreviewGuides
                    )
                } else if isPreviewLoading {
                    VStack(spacing: 8) { ProgressView().controlSize(.small); Text("Loading preview…").font(.caption).foregroundStyle(.secondary) }
                } else {
                    VStack(spacing: 8) { Image(systemName: "photo").foregroundStyle(.secondary); Text("Preview unavailable").font(.caption).foregroundStyle(.secondary) }
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5))
            HStack(spacing: 8) {
                Text(showPreviewGuides ? "Preview matches generated output. Drag guide frames to reposition layout elements." : "Preview uses the same Python renderer as label generation.")
                    .font(.caption2).foregroundStyle(.tertiary)
                Spacer()
                if let size = previewPixelSize { Text("\(Int(size.width)) × \(Int(size.height)) px").font(.caption2.monospacedDigit()).foregroundStyle(.tertiary) }
            }
        }.frame(minWidth: 420)
    }

    @ViewBuilder private func carrierLayoutControls(for carrier: Carrier) -> some View {
        let layout = carrierLayoutBinding(for: carrier)
        templateMaskSection(layout: layout)
        rasterSection("MaxiCode", icon: "qrcode", color: .purple, whitespace: Binding(get: { Double(layout.maxicode.wrappedValue.whitespace) }, set: { layout.maxicode.wrappedValue.whitespace = Int($0) }), width: layout.maxicode.width, height: layout.maxicode.height, x: layout.maxicode.xOffset, y: layout.maxicode.yOffset, scale: layout.maxicode.scale)
        rasterSection("Main Barcode", icon: "barcode", color: .blue, whitespace: layout.barcode.whitespace, width: layout.barcode.width, height: layout.barcode.height, x: layout.barcode.xPosition, y: layout.barcode.yPosition, scale: optionalDouble(layout.barcode.scale, defaultValue: 1.0))
        if carrier == .ups { rasterSection("ZIP Barcode", icon: "barcode.viewfinder", color: .orange, whitespace: layout.zipBarcode.whitespace, width: layout.zipBarcode.width, height: layout.zipBarcode.height, x: layout.zipBarcode.xPosition, y: layout.zipBarcode.yPosition, scale: optionalDouble(layout.zipBarcode.scale, defaultValue: 1.0)) }
        elementDisclosure("Text Blocks", icon: "textformat", color: .green) {
            textBlockSection("Sender", block: layout.text.sender, allowOverride: false)
            Divider().padding(.vertical, 2)
            textBlockSection("Receiver", block: layout.text.receiver, allowOverride: false)
            if layout.text.receiver2nd.wrappedValue != nil { Divider().padding(.vertical, 2); textBlockSection("Receiver 2nd", block: Binding(get: { layout.text.receiver2nd.wrappedValue ?? .defaultFedExText }, set: { layout.text.receiver2nd.wrappedValue = $0 }), allowOverride: false) }
            Divider().padding(.vertical, 2)
            textBlockSection("Tracking", block: layout.text.tracking, allowOverride: false)
            if carrier == .ups {
                Divider().padding(.vertical, 2)
                centerTextSection(layout: layout)
                Divider().padding(.vertical, 2)
                topNumberSection(layout: layout)
            }
            if carrier == .fedex { fedExOptionalTextBlocks(layout: layout) }
        }
    }

    private func rasterSection(_ title: String, icon: String, color: Color, whitespace: Binding<Double>, width: Binding<Int>, height: Binding<Int>, x: Binding<Int>, y: Binding<Int>, scale: Binding<Double>) -> some View {
        elementDisclosure(title, icon: icon, color: color) {
            LabeledSlider(label: "Whitespace", value: whitespace, range: 0...80, step: 0.5)
            IntSlider(label: "Width", value: width, range: 1...2000)
            IntSlider(label: "Height", value: height, range: 1...2000)
            IntSlider(label: "X", value: x, range: -2500...2500)
            IntSlider(label: "Y", value: y, range: -2500...2500)
            LabeledSlider(label: "Scale", value: scale, range: 0.05...8.0, step: 0.05)
        }
    }

    private func templateMaskSection(layout: Binding<LabelLayout.CarrierLayout>) -> some View {
        let mask = Binding(get: { layout.templateMask.wrappedValue ?? .init(enabled: true, xPosition: 0, yPosition: 585, width: 405, height: 375, opacity: 0.9, scale: 1.0, whitespace: 0) }, set: { layout.templateMask.wrappedValue = $0 })
        return elementDisclosure("White Square / Template Mask", icon: "square.fill", color: .gray) {
            Toggle("Enabled", isOn: mask.enabled).toggleStyle(.checkbox)
            IntSlider(label: "X", value: mask.xPosition, range: -2500...2500)
            IntSlider(label: "Y", value: mask.yPosition, range: -2500...2500)
            IntSlider(label: "Width", value: mask.width, range: 1...2000)
            IntSlider(label: "Height", value: mask.height, range: 1...2000)
            LabeledSlider(label: "Opacity", value: mask.opacity, range: 0...1, step: 0.05)
            LabeledSlider(label: "Scale", value: optionalDouble(mask.scale, defaultValue: 1.0), range: 0.05...8, step: 0.05)
        }
    }

    @ViewBuilder private func fedExOptionalTextBlocks(layout: Binding<LabelLayout.CarrierLayout>) -> some View {
        if layout.text.fromLabel.wrappedValue != nil { Divider().padding(.vertical, 2); textBlockSection("FROM Label", block: Binding(get: { layout.text.fromLabel.wrappedValue ?? .defaultFedExText }, set: { layout.text.fromLabel.wrappedValue = $0 }), allowOverride: true) }
        if layout.text.shipToLabel.wrappedValue != nil { Divider().padding(.vertical, 2); textBlockSection("SHIP TO Label", block: Binding(get: { layout.text.shipToLabel.wrappedValue ?? .defaultFedExText }, set: { layout.text.shipToLabel.wrappedValue = $0 }), allowOverride: true) }
        if layout.text.trackingPrefix.wrappedValue != nil { Divider().padding(.vertical, 2); textBlockSection("Tracking Prefix", block: Binding(get: { layout.text.trackingPrefix.wrappedValue ?? .defaultFedExText }, set: { layout.text.trackingPrefix.wrappedValue = $0 }), allowOverride: true) }
        if layout.text.receiverZip.wrappedValue != nil { Divider().padding(.vertical, 2); textBlockSection("Receiver ZIP", block: Binding(get: { layout.text.receiverZip.wrappedValue ?? .defaultFedExText }, set: { layout.text.receiverZip.wrappedValue = $0 }), allowOverride: true) }
    }

    private func elementDisclosure<Content: View>(_ title: String, icon: String, color: Color, @ViewBuilder content: @escaping () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            DisclosureGroup {
                VStack(alignment: .leading, spacing: 6) { content() }.padding(.top, 8).padding(.leading, 4)
            } label: { Label { Text(title).font(.subheadline.weight(.medium)) } icon: { Image(systemName: icon).font(.caption).foregroundColor(color) } }
        }.padding(.vertical, 2)
    }

    private func textBlockSection(_ label: String, block: Binding<LabelLayout.CarrierLayout.TextBlock>, allowOverride: Bool) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.caption.weight(.semibold)).padding(.bottom, 2)
            if allowOverride { TextField("Text override", text: optionalString(block.text, defaultValue: "")).textFieldStyle(.roundedBorder) }
            LabeledSlider(label: "Whitespace", value: optionalDouble(block.whitespace, defaultValue: 0), range: 0...80, step: 0.5)
            IntSlider(label: "Width", value: optionalInt(block.width, defaultValue: 0), range: 0...2000)
            IntSlider(label: "Height", value: optionalInt(block.height, defaultValue: 0), range: 0...2000)
            IntSlider(label: "X", value: block.startX, range: -2500...2500)
            IntSlider(label: "Y", value: block.startY, range: -2500...2500)
            IntSlider(label: "X Offset", value: optionalInt(block.xOffset, defaultValue: 0), range: -1000...1000)
            IntSlider(label: "Y Offset", value: optionalInt(block.yOffset, defaultValue: 0), range: -1000...1000)
            IntSlider(label: "Font Size", value: block.fontSize, range: 1...200)
            LabeledSlider(label: "Scale", value: block.scale, range: 0.05...8.0, step: 0.05)
            IntSlider(label: "Line Spc", value: block.lineSpacing, range: -100...200)
            LabeledSlider(label: "Char Spc", value: block.charSpacing, range: -50...50, step: 0.1)
            LabeledSlider(label: "H Squish", value: optionalDouble(block.horizontalSquish, defaultValue: 1.0), range: 0.1...2.0, step: 0.02)
        }
    }

    private func centerTextSection(layout: Binding<LabelLayout.CarrierLayout>) -> some View {
        let ct = Binding(get: { layout.text.centerText.wrappedValue ?? .init(scale: 2.5, yPosition: 600, xPosition: 115, width: nil, height: nil, fontSize: 50, lineSpacing: 0, charSpacing: -10, horizontalSquish: nil, text: nil, whitespace: 0, xOffset: 0, yOffset: 0) }, set: { layout.text.centerText.wrappedValue = $0 })
        let block = Binding(get: { ct.wrappedValue.asTextBlock }, set: { newValue in ct.wrappedValue = .init(scale: newValue.scale, yPosition: newValue.startY, xPosition: newValue.startX, width: newValue.width, height: newValue.height, fontSize: newValue.fontSize, lineSpacing: newValue.lineSpacing, charSpacing: newValue.charSpacing, horizontalSquish: newValue.horizontalSquish, text: newValue.text, whitespace: newValue.whitespace, xOffset: newValue.xOffset, yOffset: newValue.yOffset) })
        return textBlockSection("Center Text", block: block, allowOverride: true)
    }

    private func topNumberSection(layout: Binding<LabelLayout.CarrierLayout>) -> some View {
        let tn = Binding(get: { layout.text.topNumber.wrappedValue ?? .init(yPosition: -5, xPosition: 617, width: nil, height: nil, fontSize: 52, scale: 1.0, lineSpacing: 0, charSpacing: 0, horizontalSquish: nil, text: "1", whitespace: 0, xOffset: 0, yOffset: 0) }, set: { layout.text.topNumber.wrappedValue = $0 })
        let block = Binding(get: { tn.wrappedValue.asTextBlock }, set: { newValue in tn.wrappedValue = .init(yPosition: newValue.startY, xPosition: newValue.startX, width: newValue.width, height: newValue.height, fontSize: newValue.fontSize, scale: newValue.scale, lineSpacing: newValue.lineSpacing, charSpacing: newValue.charSpacing, horizontalSquish: newValue.horizontalSquish, text: newValue.text, whitespace: newValue.whitespace, xOffset: newValue.xOffset, yOffset: newValue.yOffset) })
        return textBlockSection("Top Number", block: block, allowOverride: true)
    }

    private func carrierLayoutBinding(for carrier: Carrier) -> Binding<LabelLayout.CarrierLayout> {
        switch carrier { case .ups: return Binding(get: { draft.labelLayout.ups }, set: { draft.labelLayout.ups = $0 }); case .usps: return Binding(get: { draft.labelLayout.usps }, set: { draft.labelLayout.usps = $0 }); case .fedex: return Binding(get: { draft.labelLayout.fedex }, set: { draft.labelLayout.fedex = $0 }) }
    }

    private func optionalDouble(_ binding: Binding<Double?>, defaultValue: Double) -> Binding<Double> { Binding(get: { binding.wrappedValue ?? defaultValue }, set: { binding.wrappedValue = $0 }) }
    private func optionalInt(_ binding: Binding<Int?>, defaultValue: Int) -> Binding<Int> { Binding(get: { binding.wrappedValue ?? defaultValue }, set: { binding.wrappedValue = $0 }) }
    private func optionalString(_ binding: Binding<String?>, defaultValue: String) -> Binding<String> { Binding(get: { binding.wrappedValue ?? defaultValue }, set: { binding.wrappedValue = $0.isEmpty ? nil : $0 }) }

    private func resetCarrierDefaults() { switch selectedLayoutCarrier { case .ups: draft.labelLayout.ups = .defaultUPS; case .usps: draft.labelLayout.usps = .defaultUSPS; case .fedex: draft.labelLayout.fedex = .defaultFedEx } }
    private func saveSettings() async { isSaving = true; await model.saveSettings(draft); isSaving = false }
    private func schedulePreviewReload(immediate: Bool = false) { previewReloadTask?.cancel(); previewReloadTask = Task { if !immediate { try? await Task.sleep(for: .milliseconds(250)) }; guard !Task.isCancelled else { return }; await loadPreviewElements() } }
    private func clearPreviewElements() {
        previewComposite = nil
        previewTemplate = nil
        previewBarcode = nil
        previewMaxicode = nil
        previewZipBarcode = nil
        previewPixelSize = nil
    }

    private func chooseCustomTemplate() {
        guard let url = FilePanelService.chooseTemplateImageFile(), let image = NSImage(contentsOf: url) else { return }
        currentLayout.customTemplatePath.wrappedValue = url.path
        previewTemplate = image
        schedulePreviewReload(immediate: true)
    }

    private func loadPreviewElements() async {
        isPreviewLoading = true
        defer { isPreviewLoading = false }

        let enc = JSONEncoder(); enc.outputFormatting = .sortedKeys
        var layoutOverrides: [String: Any]?
        if let data = try? enc.encode(draft.labelLayout), let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] { layoutOverrides = dict }
        let result: PreviewElementsResult?
        if let info = model.lastGenerated?.ftidInfo {
            result = await model.fetchPreviewElements(for: selectedLayoutCarrier, ftidInfo: info, layoutOverrides: layoutOverrides)
        } else {
            result = await model.fetchPreviewElements(for: selectedLayoutCarrier, layoutOverrides: layoutOverrides)
        }
        guard let result else { return }
        previewComposite = result.composite
        previewTemplate = result.template
        previewBarcode = result.barcode
        previewMaxicode = result.maxicode
        previewZipBarcode = result.zipBarcode
        previewPixelSize = result.pixelSize
    }
}

private struct SettingsCard<Content: View>: View {
    let icon: String
    let title: String
    var subtitle: String?
    @ViewBuilder let content:  () -> Content
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: icon).font(.title3).foregroundColor(.accentColor)
                VStack(alignment: .leading, spacing: 1) { Text(title).font(.headline); if let subtitle { Text(subtitle).font(.caption).foregroundStyle(.secondary) } }
                Spacer()
            }
            content()
        }
        .padding(16)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}
