import AppKit
import SwiftUI

struct MaxiCodeView: View {
    @EnvironmentObject private var model: AppModel
    @State private var sourceText = ""

    private func copy(_ value: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(value, forType: .string)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("MaxiCode")
                        .font(.system(size: 30, weight: .bold, design: .rounded))
                    Text("Generate enhanced MaxiCode payloads, modify existing data, and reuse previous entries as new labels.")
                        .foregroundStyle(.secondary)
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 14) {
                        Text("Automatic Generation")
                            .font(.headline)
                        Button("Generate Using Previous Data") {
                            Task { await model.generateMaxicode() }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(model.isWorking)

                        if let generated = model.generatedMaxicode {
                            TextEditor(text: .constant(generated.data))
                                .font(.system(.body, design: .monospaced))
                                .frame(minHeight: 160)
                            HStack(spacing: 8) {
                                Button("Export Generated Text…") {
                                    guard let url = FilePanelService.chooseTextExportDestination(defaultName: generated.suggestedFilename) else { return }
                                    model.exportText(generated.data, to: url)
                                }
                                Button {
                                    copy(generated.data)
                                } label: {
                                    Label("Copy", systemImage: "doc.on.doc")
                                }
                            }
                        }
                    }
                    .padding(8)
                } label: {
                    Text("Generate")
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 14) {
                        Text("Modify Existing Data")
                            .font(.headline)
                        TextEditor(text: $sourceText)
                            .font(.system(.body, design: .monospaced))
                            .frame(minHeight: 140)
                        Button("Modify MaxiCode") {
                            Task { await model.modifyMaxicode(from: sourceText) }
                        }
                        .disabled(model.isWorking || sourceText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        if let modified = model.modifiedMaxicode {
                            TextEditor(text: .constant(modified.data))
                                .font(.system(.body, design: .monospaced))
                                .frame(minHeight: 160)
                            HStack(spacing: 8) {
                                Button("Export Modified Text…") {
                                    guard let url = FilePanelService.chooseTextExportDestination(defaultName: modified.suggestedFilename) else { return }
                                    model.exportText(modified.data, to: url)
                                }
                                Button {
                                    copy(modified.data)
                                } label: {
                                    Label("Copy", systemImage: "doc.on.doc")
                                }
                            }
                        }
                    }
                    .padding(8)
                } label: {
                    Text("Modify")
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            Text("Previous Entries")
                                .font(.headline)
                            Spacer()
                            Button("Refresh") {
                                Task { await model.refreshAll() }
                            }
                        }

                        if model.previousMaxicodeEntries.isEmpty {
                            Text("No previous MaxiCode entries are stored yet.")
                                .foregroundStyle(.secondary)
                        } else {
                            ForEach(model.previousMaxicodeEntries) { entry in
                                VStack(alignment: .leading, spacing: 8) {
                                    Text(entry.preview)
                                        .font(.headline)
                                    Text(entry.timestamp)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    HStack {
                                        Text("Sender ZIP: \(entry.senderInfo.zipCode)")
                                        Text("Receiver ZIP: \(entry.receiverInfo.zipCode)")
                                    }
                                    .foregroundStyle(.secondary)
                                    Button("Generate Label From Entry") {
                                        Task { await model.regenerate(previousEntry: entry) }
                                    }
                                    .disabled(model.isWorking)
                                }
                                .padding(.vertical, 6)
                                if entry.id != model.previousMaxicodeEntries.last?.id {
                                    Divider()
                                }
                            }
                        }
                    }
                    .padding(8)
                } label: {
                    Text("Reuse")
                }
            }
            .padding(28)
        }
    }
}
