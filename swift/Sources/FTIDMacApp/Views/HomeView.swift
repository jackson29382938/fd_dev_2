import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var model: AppModel
    @Binding var selection: SidebarDestination?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("FTID Generator")
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                    Text("Generate labels, process imports, reuse MaxiCode entries, and manage the bundled Python workflow from one native macOS app.")
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if !model.startupIssues.isEmpty || !model.startupWarnings.isEmpty {
                    GroupBox {
                        VStack(alignment: .leading, spacing: 8) {
                            if !model.startupIssues.isEmpty {
                                ForEach(model.startupIssues, id: \.self) { issue in
                                    Label(issue, systemImage: "xmark.octagon.fill")
                                        .font(.caption)
                                        .foregroundStyle(.red)
                                }
                            }
                            if !model.startupWarnings.isEmpty {
                                ForEach(model.startupWarnings, id: \.self) { warning in
                                    Label(warning, systemImage: "exclamationmark.triangle.fill")
                                        .font(.caption)
                                        .foregroundStyle(.orange)
                                }
                            }
                        }
                        .padding(8)
                    } label: {
                        Text("Backend Health")
                    }
                }

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 170), spacing: 16)], spacing: 16) {
                    MetricCard(title: "Remaining Runs", value: "\(model.session?.remainingRuns ?? 0)", tint: .blue)
                    MetricCard(title: "History Entries", value: "\(model.history.count)", tint: .green)
                    MetricCard(title: "Previous MaxiCodes", value: "\(model.previousMaxicodeEntries.count)", tint: .orange)
                }

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 230), spacing: 16)], spacing: 16) {
                    QuickActionCard(
                        title: "UPS",
                        subtitle: "Generate a new UPS FTID label with bundled MaxiCode support.",
                        tint: Carrier.ups.accentColor
                    ) {
                        selection = .generator(.ups)
                    }
                    QuickActionCard(
                        title: "USPS",
                        subtitle: "Create a USPS FTID label with randomized addresses and updated tracking.",
                        tint: Carrier.usps.accentColor
                    ) {
                        selection = .generator(.usps)
                    }
                    QuickActionCard(
                        title: "FedEx",
                        subtitle: "Produce a FedEx FTID label and keep history synchronized locally.",
                        tint: Carrier.fedex.accentColor
                    ) {
                        selection = .generator(.fedex)
                    }
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            Text("Recent Activity")
                                .font(.title3.weight(.semibold))
                            Spacer()
                            Button("View All") {
                                selection = .history
                            }
                        }

                        if model.history.isEmpty {
                            Text("No labels generated yet.")
                                .foregroundStyle(.secondary)
                        } else {
                            ForEach(Array(model.history.prefix(5))) { entry in
                                VStack(alignment: .leading, spacing: 6) {
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
                                    Text("From \(entry.senderZip) to \(entry.receiverZip)")
                                        .font(.subheadline)
                                        .foregroundStyle(.secondary)
                                }
                                .padding(.vertical, 4)
                                if entry.id != model.history.prefix(5).last?.id {
                                    Divider()
                                }
                            }
                        }
                    }
                    .padding(8)
                }

                if let result = model.lastGenerated {
                    GroupBox {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Latest Label")
                                .font(.title3.weight(.semibold))
                            if let templateName = result.templateName {
                                Text(templateName)
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(.secondary)
                            }
                            Text(result.ftidInfo.originalTracking)
                                .font(.system(.body, design: .monospaced))
                            Text(result.labelPath)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            HStack {
                                Button("Open Label") {
                                    model.openPath(result.labelPath)
                                }
                                Button("Open Output Folder") {
                                    model.openOutputDirectory()
                                }
                            }
                        }
                        .padding(8)
                    }
                }
            }
            .padding(28)
        }
    }
}

private struct MetricCard: View {
    let title: String
    let value: String
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title.uppercased())
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.system(size: 28, weight: .bold, design: .rounded))
            RoundedRectangle(cornerRadius: 999)
                .fill(tint.gradient)
                .frame(width: 54, height: 6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(20)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
    }
}

private struct QuickActionCard: View {
    let title: String
    let subtitle: String
    let tint: Color
    let action: () -> Void

    @State private var isHovering = false

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Text(title)
                        .font(.title2.weight(.bold))
                    Spacer()
                    Image(systemName: "arrow.right.circle.fill")
                        .font(.title2)
                        .foregroundStyle(tint)
                        .opacity(isHovering ? 1 : 0.45)
                }
                Text(subtitle)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, minHeight: 170, alignment: .leading)
            .padding(24)
            .background(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .fill(tint.opacity(isHovering ? 0.22 : 0.14))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .strokeBorder(tint.opacity(isHovering ? 0.5 : 0.0), lineWidth: 1.5)
            )
            .scaleEffect(isHovering ? 1.015 : 1.0)
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            withAnimation(.spring(duration: 0.25)) {
                isHovering = hovering
            }
        }
        .accessibilityLabel("Open \(title) generator")
    }
}
