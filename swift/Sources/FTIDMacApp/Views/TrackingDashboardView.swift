import AppKit
import SwiftUI

struct TrackingDashboardView: View {
    @EnvironmentObject private var model: AppModel
    @State private var searchText = ""
    @State private var selectedCarrier = "ALL"
    @State private var selectedStatus = "ALL"
    @State private var showingAddSheet = false
    @State private var showingImportSheet = false
    @State private var selectedEntryForDetail: TrackingEntry?
    @State private var entryToDelete: TrackingEntry?
    @State private var showingDeleteConfirmation = false

    private var filteredEntries: [TrackingEntry] {
        var entries = model.trackingEntries

        if selectedCarrier != "ALL" {
            entries = entries.filter { $0.carrier == selectedCarrier }
        }

        switch selectedStatus {
        case "Active":
            entries = entries.filter { $0.statusEnum.isActive }
        case "Delivered":
            entries = entries.filter { $0.status == "delivered" }
        case "Exception":
            entries = entries.filter { $0.status == "exception" }
        default:
            break
        }

        if !searchText.isEmpty {
            let query = searchText.lowercased()
            entries = entries.filter { entry in
                let haystack = [
                    entry.trackingNumber,
                    entry.carrier,
                    entry.status,
                    entry.statusDetails,
                    entry.label,
                    entry.store,
                    entry.originZip,
                    entry.destinationZip,
                    entry.estimatedDelivery,
                    entry.source,
                ]
                .joined(separator: " ")
                .lowercased()
                return haystack.contains(query)
            }
        }

        return entries
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            filters
            Divider()
            entryList
        }
        .navigationTitle("Package Tracker")
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                Button { showingAddSheet = true } label: {
                    Label("Add", systemImage: "plus")
                }
                Button { showingImportSheet = true } label: {
                    Label("Import Sheet", systemImage: "square.and.arrow.down")
                }
                Button { Task { await model.refreshCarrierStatuses() } } label: {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
            }
        }
        .sheet(isPresented: $showingAddSheet) {
            TrackingAddSheet()
        }
        .sheet(isPresented: $showingImportSheet) {
            TrackingImportSheet()
        }
        .sheet(item: $selectedEntryForDetail) { entry in
            TrackingDetailView(entryId: entry.id)
        }
        .alert("Delete Entry", isPresented: $showingDeleteConfirmation) {
            Button("Delete", role: .destructive) {
                if let entry = entryToDelete {
                    Task { await model.deleteTrackingEntry(id: entry.id) }
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            if let entry = entryToDelete {
                Text("Remove tracking for \(entry.trackingNumber.prefix(20))?")
            }
        }
    }

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Track your packages")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                HStack(spacing: 12) {
                    StatBadge(label: "Total", value: model.trackingStats.total, color: .primary)
                    StatBadge(label: "Active", value: model.trackingStats.active, color: .blue)
                    StatBadge(label: "Delivered", value: model.trackingStats.delivered, color: .green)
                    StatBadge(label: "Exception", value: model.trackingStats.exception, color: .red)
                }
            }
            Spacer()
        }
        .padding()
    }

    private var filters: some View {
        HStack(spacing: 12) {
            Picker("Carrier", selection: $selectedCarrier) {
                ForEach(["ALL", "UPS", "USPS", "FEDEX"], id: \.self) { carrier in
                    Text(carrier).tag(carrier)
                }
            }
            .pickerStyle(.menu)
            .frame(width: 100)

            Picker("Status", selection: $selectedStatus) {
                ForEach(["ALL", "Active", "Delivered", "Exception"], id: \.self) { status in
                    Text(status).tag(status)
                }
            }
            .pickerStyle(.menu)
            .frame(width: 110)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }

    private var entryList: some View {
        List {
            if filteredEntries.isEmpty {
                ContentUnavailableView(
                    "No Tracking Entries",
                    systemImage: "shippingbox",
                    description: Text("Add a tracking number or import from Google Sheet.")
                )
            } else {
                ForEach(filteredEntries) { entry in
                    TrackingRowView(entry: entry)
                        .contentShape(Rectangle())
                        .onTapGesture {
                            if let idx = model.trackingEntries.firstIndex(where: { $0.id == entry.id }) {
                                selectedEntryForDetail = model.trackingEntries[idx]
                            }
                        }
                        .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                            Button(role: .destructive) {
                                entryToDelete = entry
                                showingDeleteConfirmation = true
                            } label: {
                                Label("Delete", systemImage: "trash")
                            }
                        }
                }
            }
        }
        .listStyle(.plain)
        .searchable(text: $searchText, prompt: "Search packages")
    }
}

struct StatBadge: View {
    let label: String
    let value: Int
    let color: Color

    var body: some View {
        VStack(spacing: 2) {
            Text("\(value)")
                .font(.headline)
                .foregroundStyle(color)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }
}

struct TrackingRowView: View {
    @EnvironmentObject private var model: AppModel
    let entry: TrackingEntry

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: entry.carrierSystemImage)
                .font(.title2)
                .foregroundStyle(carrierColor)
                .frame(width: 32)

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(entry.carrier)
                        .font(.headline)
                    Text(entry.trackingNumber.prefix(18).description + (entry.trackingNumber.count > 18 ? "..." : ""))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if !entry.label.isEmpty || !entry.store.isEmpty {
                    Text([entry.label, entry.store].filter { !$0.isEmpty }.joined(separator: " - "))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                if !entry.statusDetails.isEmpty {
                    Text(entry.statusDetails)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                Text(entry.statusEnum.title)
                    .font(.caption)
                    .fontWeight(.medium)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(statusColor.opacity(0.15), in: Capsule())
                    .foregroundStyle(statusColor)

                if !entry.lastUpdated.isEmpty {
                    Text(entry.lastUpdated.prefix(10).description)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            HStack(spacing: 4) {
                Button { copyTrackingNumber() } label: {
                    Label("Copy Tracking", systemImage: "doc.on.doc")
                        .labelStyle(.iconOnly)
                }
                .help("Copy tracking number")

                if entry.trackingURL != nil {
                    Button { openTrackingPage() } label: {
                        Label("Open Carrier Page", systemImage: "arrow.up.right.square")
                            .labelStyle(.iconOnly)
                    }
                    .help("Open on \(entry.carrier)")
                }

                Button { refreshStatus() } label: {
                    Label("Refresh Status", systemImage: "arrow.clockwise")
                        .labelStyle(.iconOnly)
                }
                .help("Refresh carrier status")
            }
            .buttonStyle(.borderless)
            .controlSize(.small)
        }
        .padding(.vertical, 4)
        .contextMenu {
            Button("Copy Tracking Number") { copyTrackingNumber() }
            if let url = entry.trackingURL {
                Button("Copy Carrier Tracking URL") { copy(url.absoluteString) }
                Button("Open on \(entry.carrier)") { NSWorkspace.shared.open(url) }
            }
            Divider()
            Button("Refresh Carrier Status") { refreshStatus() }
        }
    }

    private var statusColor: Color {
        switch entry.statusEnum {
        case .pending: return .gray
        case .inTransit: return .blue
        case .outForDelivery: return .orange
        case .delivered: return .green
        case .exception: return .red
        case .unknown: return .gray
        }
    }

    private var carrierColor: Color {
        switch entry.carrier.uppercased() {
        case "UPS": return Color(red: 0.65, green: 0.38, blue: 0.14)
        case "USPS": return Color(red: 0.0, green: 0.29, blue: 0.53)
        case "FEDEX": return Color(red: 0.30, green: 0.08, blue: 0.55)
        default: return .gray
        }
    }

    private func copyTrackingNumber() {
        copy(entry.trackingNumber)
    }

    private func openTrackingPage() {
        if let url = entry.trackingURL {
            NSWorkspace.shared.open(url)
        }
    }

    private func refreshStatus() {
        Task { await model.refreshCarrierStatusForEntry(id: entry.id) }
    }

    private func copy(_ value: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(value, forType: .string)
    }
}

// MARK: - Add Sheet

struct TrackingAddSheet: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var trackingNumber = ""
    @State private var carrier = "Auto-detect"
    @State private var label = ""
    @State private var store = ""
    @State private var originZip = ""
    @State private var destinationZip = ""
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Tracking Info") {
                    TextField("Tracking Number", text: $trackingNumber)
                    Picker("Carrier", selection: $carrier) {
                        ForEach(["Auto-detect", "UPS", "USPS", "FEDEX"], id: \.self) { c in
                            Text(c).tag(c)
                        }
                    }
                    if let errorMessage {
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }
                }
                Section("Details") {
                    TextField("Label (e.g. ali - dolphin rc)", text: $label)
                    TextField("Store / Seller", text: $store)
                    TextField("Origin ZIP", text: $originZip)
                    TextField("Destination ZIP", text: $destinationZip)
                }
            }
            .navigationTitle("Add Tracking")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        let trimmed = trackingNumber.trimmingCharacters(in: .whitespaces)
                        if let error = validateTrackingNumber(trimmed) {
                            errorMessage = error
                            return
                        }
                        errorMessage = nil
                        let resolved = carrier == "Auto-detect" ? "UNKNOWN" : carrier
                        Task {
                            await model.addTrackingEntry(
                                trackingNumber: trimmed,
                                carrier: resolved,
                                label: label.trimmingCharacters(in: .whitespaces),
                                store: store.trimmingCharacters(in: .whitespaces),
                                originZip: originZip.trimmingCharacters(in: .whitespaces),
                                destinationZip: destinationZip.trimmingCharacters(in: .whitespaces)
                            )
                            dismiss()
                        }
                    }
                    .disabled(trackingNumber.trimmingCharacters(in: .whitespaces).isEmpty || model.isWorking)
                }
            }
        }
        .frame(minWidth: 420, minHeight: 360)
    }

    private func validateTrackingNumber(_ number: String) -> String? {
        let cleaned = number.uppercased().replacingOccurrences(of: " ", with: "")
        guard !cleaned.isEmpty else { return "Tracking number is required." }
        if cleaned.count < 8 { return "Tracking number too short (min 8 characters)." }
        if cleaned.count > 40 { return "Tracking number too long (max 40 characters)." }
        return nil
    }
}

// MARK: - Import Sheet

struct TrackingImportSheet: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var pastedData = ""
    @State private var importStatus = ""

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                Text("Paste tab-separated data from Google Sheets.\nFirst row should be column headers.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                TextEditor(text: $pastedData)
                    .font(.caption)
                    .frame(minHeight: 200)
                    .border(.quaternary)

                if !importStatus.isEmpty {
                    Text(importStatus)
                        .font(.caption)
                        .foregroundStyle(importStatus.contains("Error") ? .red : .green)
                }
            }
            .padding()
            .navigationTitle("Import from Sheet")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Import") {
                        importData()
                    }
                    .disabled(pastedData.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || model.isWorking)
                }
            }
        }
        .frame(minWidth: 460, minHeight: 360)
    }

    private func importData() {
        let lines = pastedData.trimmingCharacters(in: .whitespacesAndNewlines).components(separatedBy: "\n")
        guard lines.count >= 2 else {
            importStatus = "Error: Need header row and at least one data row."
            return
        }

        let headers = lines[0].components(separatedBy: "\t").map { $0.trimmingCharacters(in: .whitespaces) }
        var rows: [[String: String]] = []

        for line in lines.dropFirst() {
            let values = line.components(separatedBy: "\t")
            var row: [String: String] = [:]
            for (index, header) in headers.enumerated() {
                if index < values.count {
                    row[header] = values[index].trimmingCharacters(in: .whitespaces)
                }
            }
            rows.append(row)
        }

        Task {
            let count = await model.importTrackingFromSheet(rows: rows)
            if count > 0 {
                importStatus = "Imported \(count) tracking entries!"
                try? await Task.sleep(for: .seconds(1))
                dismiss()
            } else {
                importStatus = "Error: No valid tracking entries found."
            }
        }
    }
}
