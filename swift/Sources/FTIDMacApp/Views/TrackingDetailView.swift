import AppKit
import SwiftUI

struct TrackingDetailView: View {
    let entryId: String
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var showingDeleteConfirmation = false

    private var entry: TrackingEntry? {
        model.trackingEntries.first { $0.id == entryId }
    }

    var body: some View {
        NavigationStack {
            Group {
                if let entry {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 20) {
                            headerSection(entry)
                            statusSection(entry)
                            detailsSection(entry)
                            timelineSection(entry)
                        }
                        .padding()
                    }
                } else {
                    ContentUnavailableView("Entry Not Found", systemImage: "questionmark.folder")
                }
            }
            .navigationTitle("Tracking Details")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
                ToolbarItemGroup(placement: .primaryAction) {
                    if let entry, let url = entry.trackingURL {
                        Link(destination: url) {
                            Label("Track on \(entry.carrier)", systemImage: "arrow.up.right.square")
                        }
                    }
                    if let entry {
                        Button { copy(entry.trackingNumber) } label: {
                            Label("Copy", systemImage: "doc.on.doc")
                        }
                        Button { Task { await model.refreshCarrierStatusForEntry(id: entry.id) } } label: {
                            Label("Refresh", systemImage: "arrow.clockwise")
                        }
                        Button(role: .destructive) {
                            showingDeleteConfirmation = true
                        } label: {
                            Label("Delete", systemImage: "trash")
                        }
                    }
                }
            }
            .alert("Delete Entry", isPresented: $showingDeleteConfirmation) {
                Button("Delete", role: .destructive) {
                    Task {
                        await model.deleteTrackingEntry(id: entryId)
                        dismiss()
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                if let entry {
                    Text("Remove tracking for \(entry.trackingNumber.prefix(20))?")
                }
            }
        }
        .frame(minWidth: 520, minHeight: 480)
    }

    private func headerSection(_ entry: TrackingEntry) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: entry.carrierSystemImage)
                    .font(.largeTitle)
                    .foregroundStyle(carrierColor(for: entry))
                VStack(alignment: .leading) {
                    Text(entry.carrier)
                        .font(.title2.bold())
                    Text(entry.trackingNumber)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
                Spacer()
                HStack(spacing: 8) {
                    Button { copy(entry.trackingNumber) } label: {
                        Label("Copy", systemImage: "doc.on.doc")
                    }
                    .buttonStyle(.bordered)

                    if let url = entry.trackingURL {
                        Button { NSWorkspace.shared.open(url) } label: {
                            Label("Open", systemImage: "arrow.up.right.square")
                        }
                        .buttonStyle(.bordered)
                    }
                }
                .controlSize(.small)
            }

            if !entry.label.isEmpty || !entry.store.isEmpty {
                Text([entry.label, entry.store].filter { !$0.isEmpty }.joined(separator: " - "))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .contextMenu {
            Button("Copy Tracking Number") { copy(entry.trackingNumber) }
            if let url = entry.trackingURL {
                Button("Copy Carrier Tracking URL") { copy(url.absoluteString) }
                Button("Open on \(entry.carrier)") { NSWorkspace.shared.open(url) }
            }
            Divider()
            Button("Refresh Carrier Status") {
                Task { await model.refreshCarrierStatusForEntry(id: entry.id) }
            }
        }
    }

    private func statusSection(_ entry: TrackingEntry) -> some View {
        HStack {
            Image(systemName: entry.statusEnum.systemImage)
                .font(.title)
                .foregroundStyle(statusColor(for: entry))
            VStack(alignment: .leading) {
                Text(entry.statusEnum.title)
                    .font(.headline)
                    .foregroundStyle(statusColor(for: entry))
                if !entry.statusDetails.isEmpty {
                    Text(entry.statusDetails)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            if !entry.estimatedDelivery.isEmpty {
                VStack(alignment: .trailing) {
                    Text("Est. Delivery")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(entry.estimatedDelivery.prefix(10).description)
                        .font(.subheadline.bold())
                }
            }
        }
        .padding()
        .background(statusColor(for: entry).opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
    }

    private func detailsSection(_ entry: TrackingEntry) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            DetailRow(label: "Carrier", value: entry.carrier)
            DetailRow(label: "Tracking", value: entry.trackingNumber)
            if !entry.originZip.isEmpty {
                DetailRow(label: "From ZIP", value: entry.originZip)
            }
            if !entry.destinationZip.isEmpty {
                DetailRow(label: "To ZIP", value: entry.destinationZip)
            }
            DetailRow(label: "Source", value: entry.source)
            DetailRow(label: "Added", value: entry.createdAt.prefix(16).description)
            if !entry.lastUpdated.isEmpty {
                DetailRow(label: "Last Updated", value: entry.lastUpdated.prefix(16).description)
            }
        }
        .padding()
        .background(.fill, in: RoundedRectangle(cornerRadius: 12))
    }

    private func timelineSection(_ entry: TrackingEntry) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Status Timeline")
                .font(.headline)
                .padding(.bottom, 12)

            if entry.history.isEmpty {
                Text("No status history yet.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 20)
            } else {
                ForEach(Array(entry.history.enumerated()), id: \.element.id) { index, item in
                    TimelineRow(item: item, isLast: index == entry.history.count - 1)
                }
            }
        }
        .padding()
        .background(.fill, in: RoundedRectangle(cornerRadius: 12))
    }

    private func statusColor(for entry: TrackingEntry) -> Color {
        switch entry.statusEnum {
        case .pending: return .gray
        case .inTransit: return .blue
        case .outForDelivery: return .orange
        case .delivered: return .green
        case .exception: return .red
        case .unknown: return .gray
        }
    }

    private func carrierColor(for entry: TrackingEntry) -> Color {
        switch entry.carrier.uppercased() {
        case "UPS": return Color(red: 0.65, green: 0.38, blue: 0.14)
        case "USPS": return Color(red: 0.0, green: 0.29, blue: 0.53)
        case "FEDEX": return Color(red: 0.30, green: 0.08, blue: 0.55)
        default: return .gray
        }
    }

    private func copy(_ value: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(value, forType: .string)
    }
}

struct DetailRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .frame(width: 100, alignment: .leading)
            Text(value)
                .font(.subheadline)
            Spacer()
        }
    }
}

struct TimelineRow: View {
    let item: TrackingTimelineEntry
    let isLast: Bool

    private var statusColor: Color {
        let status = TrackingStatus(rawValue: item.status) ?? .unknown
        switch status {
        case .pending: return .gray
        case .inTransit: return .blue
        case .outForDelivery: return .orange
        case .delivered: return .green
        case .exception: return .red
        case .unknown: return .gray
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(spacing: 0) {
                Circle()
                    .fill(statusColor)
                    .frame(width: 10, height: 10)
                if !isLast {
                    Rectangle()
                        .fill(.quaternary)
                        .frame(width: 2, height: 40)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(item.status.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.subheadline.bold())
                    .foregroundStyle(statusColor)

                if !item.details.isEmpty {
                    Text(item.details)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                HStack(spacing: 8) {
                    if !item.location.isEmpty {
                        Label(item.location, systemImage: "mappin")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    if !item.timestamp.isEmpty {
                        Text(item.timestamp.prefix(16).description)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(.bottom, isLast ? 0 : 8)
        }
    }
}
