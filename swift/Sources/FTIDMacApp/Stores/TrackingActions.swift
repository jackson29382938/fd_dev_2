import Foundation

private struct TrackingRefreshResult: Decodable {
    let updatedCount: Int
    let updatedIds: [String]

    enum CodingKeys: String, CodingKey {
        case updatedCount = "updated_count"
        case updatedIds = "updated_ids"
    }
}

extension AppModel {
    @MainActor
    func refreshCarrierStatuses() async {
        await runTrackingActivity("Checking carrier tracking…") { [self] in
            let _: TrackingRefreshResult = try await bridge.execute("tracking_refresh")
            let response: TrackingListResponse = try await bridge.execute("tracking_list")
            trackingEntries = response.entries
            trackingStats = response.stats
        }
    }

    @MainActor
    func refreshCarrierStatusForEntry(id: String) async {
        await runTrackingActivity("Checking package status…") { [self] in
            let _: TrackingRefreshResult = try await bridge.execute(
                "tracking_refresh",
                payload: ["entry_id": id]
            )
            let refreshed: TrackingEntry = try await bridge.execute(
                "tracking_detail",
                payload: ["entry_id": id]
            )
            if let index = trackingEntries.firstIndex(where: { $0.id == id }) {
                trackingEntries[index] = refreshed
            } else {
                trackingEntries.insert(refreshed, at: 0)
            }
            let stats: TrackingStats = try await bridge.execute("tracking_stats")
            trackingStats = stats
        }
    }

    @MainActor
    private func runTrackingActivity(
        _ message: String,
        operation: @escaping () async throws -> Void
    ) async {
        await runActivity(message, operation: operation)
    }
}
