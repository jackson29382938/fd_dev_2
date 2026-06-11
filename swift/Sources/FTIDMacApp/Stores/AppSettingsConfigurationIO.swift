import Foundation

private struct SettingsConfigurationEnvelope: Codable {
    let schemaVersion: Int
    let exportedAt: Date
    let appName: String
    let settings: AppSettings

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case exportedAt = "exported_at"
        case appName = "app_name"
        case settings
    }
}

private enum SettingsConfigurationError: LocalizedError {
    case busy
    case invalidConfiguration(String)

    var errorDescription: String? {
        switch self {
        case .busy:
            return "Finish the current operation before importing or exporting settings."
        case .invalidConfiguration(let message):
            return message
        }
    }
}

@MainActor
extension AppModel {
    func exportSettingsConfiguration(to url: URL) async {
        guard !isWorking else {
            errorMessage = SettingsConfigurationError.busy.localizedDescription
            return
        }

        isWorking = true
        activityMessage = "Exporting settings configuration…"
        defer {
            isWorking = false
            activityMessage = ""
        }

        do {
            let envelope = SettingsConfigurationEnvelope(
                schemaVersion: 1,
                exportedAt: Date(),
                appName: "FTIDMacApp",
                settings: settings
            )
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let data = try encoder.encode(envelope)
            try data.write(to: url, options: [.atomic])
        } catch {
            errorMessage = "Could not export settings configuration: \(error.localizedDescription)"
        }
    }

    func importSettingsConfiguration(from url: URL) async -> AppSettings? {
        guard !isWorking else {
            errorMessage = SettingsConfigurationError.busy.localizedDescription
            return nil
        }

        isWorking = true
        activityMessage = "Importing settings configuration…"
        let decodedSettings: AppSettings?
        do {
            let data = try Data(contentsOf: url)
            decodedSettings = try Self.decodeSettingsConfiguration(from: data)
        } catch {
            errorMessage = "Could not import settings configuration: \(error.localizedDescription)"
            decodedSettings = nil
        }
        isWorking = false
        activityMessage = ""

        guard let decodedSettings else { return nil }
        await saveSettings(decodedSettings)
        return settings
    }

    private static func decodeSettingsConfiguration(from data: Data) throws -> AppSettings {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        if let envelope = try? decoder.decode(SettingsConfigurationEnvelope.self, from: data) {
            try validateSettingsConfiguration(envelope.settings)
            return envelope.settings
        }

        let rawSettings = try decoder.decode(AppSettings.self, from: data)
        try validateSettingsConfiguration(rawSettings)
        return rawSettings
    }

    private static func validateSettingsConfiguration(_ settings: AppSettings) throws {
        guard ["default", "dark", "light"].contains(settings.ui.theme.lowercased()) else {
            throw SettingsConfigurationError.invalidConfiguration("The settings file contains an unsupported appearance theme.")
        }
        guard ["excel", "csv"].contains(settings.fileImport.defaultFormat.lowercased()) else {
            throw SettingsConfigurationError.invalidConfiguration("The settings file contains an unsupported import format.")
        }
        guard (1...10).contains(settings.previousMaxicode.maxEntries) else {
            throw SettingsConfigurationError.invalidConfiguration("The settings file contains an invalid history size.")
        }

        try validate(layout: settings.labelLayout.ups, name: "UPS")
        try validate(layout: settings.labelLayout.usps, name: "USPS")
        try validate(layout: settings.labelLayout.fedex, name: "FedEx")
    }

    private static func validate(layout: LabelLayout.CarrierLayout, name: String) throws {
        func require(_ condition: Bool, _ message: String) throws {
            if !condition { throw SettingsConfigurationError.invalidConfiguration(message) }
        }

        try require((50...2_000).contains(layout.barcode.width), "The \(name) barcode width is outside the supported range.")
        try require((10...1_000).contains(layout.barcode.height), "The \(name) barcode height is outside the supported range.")
        try require((0...100).contains(layout.barcode.whitespace), "The \(name) barcode whitespace is outside the supported range.")
        try require((1...200).contains(layout.barcode.moduleHeight), "The \(name) barcode module height is outside the supported range.")

        try require((50...2_000).contains(layout.zipBarcode.width), "The \(name) ZIP barcode width is outside the supported range.")
        try require((10...1_000).contains(layout.zipBarcode.height), "The \(name) ZIP barcode height is outside the supported range.")
        try require((0...100).contains(layout.zipBarcode.whitespace), "The \(name) ZIP barcode whitespace is outside the supported range.")
        try require((1...200).contains(layout.zipBarcode.moduleHeight), "The \(name) ZIP barcode module height is outside the supported range.")

        try require((50...1_000).contains(layout.maxicode.width), "The \(name) MaxiCode width is outside the supported range.")
        try require((50...1_000).contains(layout.maxicode.height), "The \(name) MaxiCode height is outside the supported range.")
        try require((0...100).contains(layout.maxicode.whitespace), "The \(name) MaxiCode whitespace is outside the supported range.")
        try require((0.1...10).contains(layout.maxicode.scale), "The \(name) MaxiCode scale is outside the supported range.")
    }
}
