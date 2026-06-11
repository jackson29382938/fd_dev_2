import AppKit
import SwiftUI

struct HistoryView: View {
    @EnvironmentObject private var model: AppModel
    @State private var searchText = ""
    @State private var selectedCarrier = "ALL"
    @State private var selectedStatus = "ALL"
    @State private var showingAddSheet = false
    @State private var showingImportSheet = false
    @State private var selectedEntryForDetail: TrackingEntry?
    @State private var entryToDelete: TrackingEntry?
    @State private var showingDeleteConfirmation = false

    var filteredEntries: [HistoryEntry] {
        guard !searchText.isEmpty else { return model.history }
        return model.history.filter { entry in
            let haystack = [
                entry.method,
                entry.trackingNumber,
                entry.originalTracking,
                entry.senderZip,
                entry.receiverZip,
                entry.senderName,
                entry.receiverName,
                entry.senderAddress,
                entry.receiverAddress,
            ].joined(separator: " ").lowercased()
            return haystack.contains(searchText.lowercased())
        }
    }

    var filteredTrackingEntries: [TrackingEntry] {
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
                ].joined(separator: " ").lowercased()
                return haystack.contains(query)
            }
        }

        return entries
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                headerSection
                trackingStatsSection
                trackingFiltersSection
                Divider()
                labelHistorySection
                Divider()
                packageTrackingSection
            }
            .padding(28)
        }
        .searchable(text: $searchText, placement: .toolbar, prompt: "Search tracking, ZIPs, or names")
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                Button { showingAddSheet = true } label: {
                    Label("Add", systemImage: "plus")
                }
                Button { showingImportSheet = true } label: {
                    Label("Import Sheet", systemImage: "square.and.arrow.down")
                }
                Button {
                    Task {
                        await model.refreshAll()
                        await model.refreshCarrierStatuses()
                    }
                } label: {
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

    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 6) {
                Text("History")
                    .font(.system(size: 30, weight: .bold, design: .rounded))
                Text("Regenerate previous labels and track packages.")
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
    }

    private var trackingStatsSection: some View {
        HStack(spacing: 12) {
            StatBadge(label: "Total", value: model.trackingStats.total, color: .primary)
            StatBadge(label: "Active", value: model.trackingStats.active, color: .blue)
            StatBadge(label: "Delivered", value: model.trackingStats.delivered, color: .green)
            StatBadge(label: "Exception", value: model.trackingStats.exception, color: .red)
        }
    }

    private var trackingFiltersSection: some View {
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
    }

    private var labelHistorySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Label History")
                .font(.title2.bold())

            if filteredEntries.isEmpty {
                ContentUnavailableView("No Label History Found", systemImage: "clock.badge.xmark")
            } else {
                ForEach(filteredEntries) { entry in
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text(entry.method.replacingOccurrences(of: "FTID_", with: ""))
                                .font(.headline)
                            Spacer()
                            Text(entry.timestamp)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        Text(entry.originalTracking)
                            .font(.system(.body, design: .monospaced))

                        HStack {
                            Label("Sender \(entry.senderZip)", systemImage: "location")
                            Label("Receiver \(entry.receiverZip)", systemImage: "mappin.and.ellipse")
                        }
                        .foregroundStyle(.secondary)

                        HStack {
                            Button("Regenerate") {
                                Task { await model.regenerate(historyEntry: entry) }
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(model.isWorking)

                            Button {
                                copy(entry.originalTracking)
                            } label: {
                                Label("Copy Tracking", systemImage: "doc.on.doc")
                            }
                            .buttonStyle(.bordered)

                            Spacer()
                        }
                    }
                    .padding(18)
                    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .contextMenu {
                        Button("Regenerate Label") {
                            Task { await model.regenerate(historyEntry: entry) }
                        }
                        Button("Copy Original Tracking") {
                            copy(entry.originalTracking)
                        }
                        if !entry.trackingNumber.isEmpty, entry.trackingNumber != entry.originalTracking {
                            Button("Copy Generated Tracking") {
                                copy(entry.trackingNumber)
                            }
                        }
                        Divider()
                        Button("Copy Sender ZIP") { copy(entry.senderZip) }
                        Button("Copy Receiver ZIP") { copy(entry.receiverZip) }
                    }
                }
            }
        }
    }

    private var packageTrackingSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Package Tracking")
                .font(.title2.bold())

            if filteredTrackingEntries.isEmpty {
                ContentUnavailableView("No Tracking Entries", systemImage: "shippingbox")
            } else {
                ForEach(filteredTrackingEntries) { entry in
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
    }

    private func copy(_ value: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(value, forType: .string)
    }
}
