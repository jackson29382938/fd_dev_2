import SwiftUI

struct ImportView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                header
                controls

                if let preview = model.importPreview {
                    previewSection(preview)
                    mappingSection(preview)
                }

                if let summary = model.importSummary {
                    summarySection(summary)
                }
            }
            .padding(28)
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Import Excel / CSV")
                .font(.system(size: 30, weight: .bold, design: .rounded))
            Text("Preview files, map columns, batch-generate labels, and get a combined PDF in your Downloads folder.")
                .foregroundStyle(.secondary)
        }
    }

    private var controls: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) { controlButtons }
            VStack(alignment: .leading, spacing: 10) { controlButtons }
        }
    }

    @ViewBuilder
    private var controlButtons: some View {
        Button("Choose File…") {
            guard let url = FilePanelService.chooseImportFile() else { return }
            Task { await model.loadImportPreview(from: url) }
        }
        .buttonStyle(.borderedProminent)

        Button("Create Template…") {
            let defaultName = "ftid_import_template_\(Date.now.formatted(date: .numeric, time: .omitted).replacingOccurrences(of: "/", with: "-")).xlsx"
            guard let url = FilePanelService.chooseTemplateDestination(defaultName: defaultName) else { return }
            Task { await model.createImportTemplate(at: url) }
        }

        if model.importPreview != nil {
            Button("Process Batch") {
                Task { await model.processImport() }
            }
            .buttonStyle(.borderedProminent)
            .disabled(missingRequiredMappings || model.isWorking)
            .help(missingRequiredMappings ? "Map all required columns before processing." : "Generate labels for every row in the file.")
        }
    }

    private func previewSection(_ preview: ImportPreview) -> some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 12) {
                Text(preview.filePath)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("\(preview.rowCount) rows detected")
                    .font(.headline)

                ForEach(Array(preview.previewRows.prefix(5).enumerated()), id: \.offset) { index, row in
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Preview Row \(index + 1)")
                            .font(.headline)
                        ForEach(preview.columns, id: \.self) { column in
                            let value = row[column] ?? ""
                            if !value.isEmpty {
                                HStack(alignment: .top) {
                                    Text(column)
                                        .fontWeight(.semibold)
                                        .frame(minWidth: 100, maxWidth: 160, alignment: .leading)
                                    Text(value)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    .padding(.vertical, 6)
                    if index < min(preview.previewRows.count, 5) - 1 {
                        Divider()
                    }
                }
            }
            .padding(8)
        } label: {
            Text("File Preview")
        }
    }

    private func mappingSection(_ preview: ImportPreview) -> some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 14) {
                Text("Column Mapping")
                    .font(.headline)

                ForEach(ImportField.allCases) { field in
                    HStack(spacing: 8) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(field.title)
                            if field.isRequired {
                                Text("Required")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(.orange)
                            }
                        }
                        .frame(minWidth: 110, maxWidth: 180, alignment: .leading)
                        Spacer(minLength: 8)
                        Picker(field.title, selection: binding(for: field.rawValue, defaultValue: preview.autoMappings[field.rawValue] ?? "")) {
                            Text("Not mapped").tag("")
                            ForEach(preview.columns, id: \.self) { column in
                                Text(column).tag(column)
                            }
                        }
                        .labelsHidden()
                        .frame(maxWidth: 320)
                    }
                }
            }
            .padding(8)
        } label: {
            Text("Mapping")
        }
    }

    private func summarySection(_ summary: ImportProcessResult) -> some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    resultBadge(value: summary.processedCount, label: "Generated", color: .green)
                    if summary.skippedCount > 0 {
                        resultBadge(value: summary.skippedCount, label: "Skipped", color: .orange)
                    }
                    if summary.totalRows > 0 {
                        resultBadge(value: summary.totalRows, label: "Total Rows", color: .secondary)
                    }
                }

                ForEach(summary.summary.keys.sorted(), id: \.self) { key in
                    Text("\(key.replacingOccurrences(of: "FTID_", with: "")): \(summary.summary[key] ?? 0)")
                        .font(.subheadline)
                }

                if let pdfPath = summary.pdfPath {
                    Button("Open Combined PDF") {
                        model.openPath(pdfPath)
                    }
                }

                if !summary.skippedRows.isEmpty {
                    Divider()
                    Text("Skipped Rows")
                        .font(.headline)
                        .foregroundStyle(.orange)
                    ForEach(summary.skippedRows) { row in
                        Label("Row \(row.rowNumber): \(row.reason)", systemImage: "exclamationmark.triangle")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                if !summary.processedRows.isEmpty {
                    Divider()
                    ForEach(summary.processedRows) { row in
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Row \(row.rowNumber) • \(row.method.replacingOccurrences(of: "FTID_", with: ""))")
                                .font(.headline)
                            Text(row.originalTracking)
                                .font(.system(.body, design: .monospaced))
                            HStack(spacing: 8) {
                                Button("Open Label") {
                                    model.openPath(row.labelPath)
                                }
                                Button("Show in Finder") {
                                    model.revealPath(row.labelPath)
                                }
                            }
                            .controlSize(.small)
                        }
                    }
                }
            }
            .padding(8)
        } label: {
            Text("Results")
        }
    }

    private func resultBadge(value: Int, label: String, color: Color) -> some View {
        VStack(spacing: 2) {
            Text("\(value)")
                .font(.title3.bold().monospacedDigit())
                .foregroundStyle(color)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(minWidth: 70)
        .padding(.vertical, 8)
        .padding(.horizontal, 12)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private var missingRequiredMappings: Bool {
        ImportField.allCases.filter(\.isRequired).contains { field in
            (model.importMappings[field.rawValue] ?? "").isEmpty
        }
    }

    private func binding(for key: String, defaultValue: String) -> Binding<String> {
        Binding(
            get: { model.importMappings[key] ?? defaultValue },
            set: { model.importMappings[key] = $0 }
        )
    }
}
