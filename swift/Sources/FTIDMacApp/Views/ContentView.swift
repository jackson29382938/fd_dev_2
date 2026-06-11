import AppKit
import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var model: AppModel
    @State private var selection: SidebarDestination? = .home

    var body: some View {
        ZStack(alignment: .bottom) {
            Group {
                if model.session == nil {
                    LoginView()
                } else {
                    workspace
                }
            }

            if model.isWorking {
                ActivityCapsule(message: model.activityMessage)
                    .padding(.bottom, 18)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .allowsHitTesting(false)
            }
        }
        .animation(.spring(duration: 0.3), value: model.isWorking)
        .task {
            await model.bootstrapIfNeeded()
        }
        .alert(
            "Something Went Wrong",
            isPresented: Binding(
                get: { model.errorMessage != nil },
                set: { if !$0 { model.errorMessage = nil } }
            )
        ) {
            if let path = errorReportPath, FileManager.default.fileExists(atPath: path) {
                Button("Open Error File") {
                    NSWorkspace.shared.open(URL(fileURLWithPath: path))
                }
                Button("Show in Finder") {
                    NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
                }
            }

            if model.errorMessage?.isEmpty == false {
                Button("Copy Details") {
                    copyErrorDetailsToClipboard()
                }
            }

            Button("OK", role: .cancel) {}
        } message: {
            Text(model.errorMessage ?? "")
        }
    }

    private var errorReportPath: String? {
        guard let message = model.errorMessage else { return nil }
        let lines = message.components(separatedBy: .newlines)

        if let markerIndex = lines.firstIndex(where: { $0.localizedCaseInsensitiveContains("full error details were saved to") }) {
            let followingLines = lines.dropFirst(markerIndex + 1)
            if let path = followingLines.map({ $0.trimmingCharacters(in: .whitespacesAndNewlines) }).first(where: { !$0.isEmpty }) {
                return normalizedExistingErrorReportPath(path)
            }
        }

        return lines
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .compactMap(normalizedExistingErrorReportPath)
            .first
    }

    private func normalizedExistingErrorReportPath(_ rawPath: String) -> String? {
        let trimmed = rawPath.trimmingCharacters(in: CharacterSet(charactersIn: " \t\"'`"))
        guard trimmed.contains("ErrorReports"), trimmed.hasPrefix("/"), trimmed.lowercased().hasSuffix(".txt") else {
            return nil
        }
        return FileManager.default.fileExists(atPath: trimmed) ? trimmed : nil
    }

    private func copyErrorDetailsToClipboard() {
        guard let message = model.errorMessage else { return }
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(message, forType: .string)
    }

    private var workspace: some View {
        NavigationSplitView {
            SidebarView(selection: $selection)
        } detail: {
            detailView
        }
        .navigationSplitViewStyle(.balanced)
        .toolbar {
            ToolbarItemGroup {
                Button {
                    Task { await model.refreshAll() }
                } label: {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                .keyboardShortcut("r", modifiers: .command)
                .disabled(model.isWorking)

                if let lastGenerated = model.lastGenerated {
                    Button {
                        model.openPath(lastGenerated.labelPath)
                    } label: {
                        Label("Open Label", systemImage: "photo")
                    }
                }

                Button {
                    model.openOutputDirectory()
                } label: {
                    Label("Output Folder", systemImage: "folder")
                }
            }
        }
    }

    @ViewBuilder
    private var detailView: some View {
        switch selection ?? .home {
        case .home:
            HomeView(selection: $selection)
        case .generator(let carrier):
            switch carrier {
            case .ups:
                LabelGeneratorView(carrier: carrier, form: $model.upsForm)
            case .usps:
                LabelGeneratorView(carrier: carrier, form: $model.uspsForm)
            case .fedex:
                LabelGeneratorView(carrier: carrier, form: $model.fedexForm)
            }
        case .history:
            HistoryView()
        case .importer:
            ImportView()
        case .maxicode:
            MaxiCodeView()
        case .tracking:
            TrackingDashboardView()
        }
    }
}

private struct ActivityCapsule: View {
    let message: String

    var body: some View {
        HStack(spacing: 10) {
            ProgressView()
                .controlSize(.small)
            Text(message.isEmpty ? "Working…" : message)
                .font(.callout.weight(.medium))
                .lineLimit(1)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 10)
        .background(.regularMaterial, in: Capsule())
        .overlay(Capsule().strokeBorder(.quaternary, lineWidth: 1))
        .shadow(color: .black.opacity(0.18), radius: 12, y: 4)
    }
}

private struct SidebarView: View {
    @EnvironmentObject private var model: AppModel
    @Binding var selection: SidebarDestination?

    var body: some View {
        VStack(spacing: 0) {
            List(selection: $selection) {
                Section("Workspace") {
                    Label("Home", systemImage: "rectangle.grid.2x2.fill")
                        .tag(SidebarDestination.home)
                }

                Section("Generate") {
                    ForEach(Carrier.allCases) { carrier in
                        Label(carrier.title, systemImage: carrier.systemImage)
                            .tag(SidebarDestination.generator(carrier))
                    }
                }

                Section("Tools") {
                    Label("History", systemImage: "clock.arrow.circlepath")
                        .tag(SidebarDestination.history)
                    Label("Import", systemImage: "square.and.arrow.down.on.square")
                        .tag(SidebarDestination.importer)
                    Label("MaxiCode", systemImage: "barcode.viewfinder")
                        .tag(SidebarDestination.maxicode)
                }

                Section("Tracking") {
                    Label("Package Tracker", systemImage: "mappin.and.ellipse")
                        .tag(SidebarDestination.tracking)
                }
            }
            .listStyle(.sidebar)

            VStack(alignment: .leading, spacing: 10) {
                if let session = model.session {
                    Text("User \(session.userID)")
                        .font(.headline)
                    Text("\(session.remainingRuns) runs remaining")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                HStack {
                    SettingsLink {
                        Label("Settings", systemImage: "gearshape.fill")
                    }

                    if model.session != nil {
                        Spacer()
                        Button(role: .destructive) {
                            model.signOut()
                        } label: {
                            Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                        }
                        .buttonStyle(.borderless)
                        .disabled(model.isWorking)
                        .help("Sign out and return to the login screen")
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
            .background(.thinMaterial)
        }
    }
}
