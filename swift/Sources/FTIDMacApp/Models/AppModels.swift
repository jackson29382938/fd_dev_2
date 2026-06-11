import Foundation
import SwiftUI

enum Carrier: String, CaseIterable, Identifiable, Codable {
    case ups = "UPS"
    case usps = "USPS"
    case fedex = "FEDEX"

    var id: String { rawValue }

    init?(methodName: String) {
        switch methodName {
        case "FTID_UPS": self = .ups
        case "FTID_USPS": self = .usps
        case "FTID_FEDEX": self = .fedex
        default: return nil
        }
    }

    var methodName: String {
        switch self {
        case .ups: return "FTID_UPS"
        case .usps: return "FTID_USPS"
        case .fedex: return "FTID_FEDEX"
        }
    }

    var finalTemplateFilename: String {
        switch self {
        case .ups: return "ups_temp_blank.png"
        case .usps: return "usps_temp_blank.png"
        case .fedex: return "fedex_temp_blank.png"
        }
    }

    var finalTemplateStem: String {
        finalTemplateFilename.split(separator: ".").first.map(String.init) ?? ""
    }

    var title: String {
        switch self {
        case .ups: return "UPS Label"
        case .usps: return "USPS Label"
        case .fedex: return "FedEx Label"
        }
    }

    var systemImage: String {
        switch self {
        case .ups: return "shippingbox.fill"
        case .usps: return "mail.stack.fill"
        case .fedex: return "truck.box.fill"
        }
    }

    var accentColor: Color {
        switch self {
        case .ups: return Color(red: 0.23, green: 0.43, blue: 0.79)
        case .usps: return Color(red: 0.20, green: 0.48, blue: 0.28)
        case .fedex: return Color(red: 0.48, green: 0.22, blue: 0.67)
        }
    }

    var trackingPlaceholder: String {
        switch self {
        case .ups: return "1Z9999999999999999"
        case .usps: return "4201234567890123456789"
        case .fedex: return "123456789012"
        }
    }

    func validateTracking(_ value: String) -> String? {
        let cleaned = value.uppercased().replacingOccurrences(of: " ", with: "")
        switch self {
        case .ups:
            guard cleaned.count == 18, cleaned.hasPrefix("1Z") else { return "UPS tracking must be 18 characters and start with 1Z." }
        case .usps:
            guard cleaned.count == 22, CharacterSet.decimalDigits.isSuperset(of: CharacterSet(charactersIn: cleaned)) else { return "USPS tracking must be 22 digits." }
        case .fedex:
            guard cleaned.count >= 12, CharacterSet.decimalDigits.isSuperset(of: CharacterSet(charactersIn: cleaned)) else { return "FedEx tracking must be at least 12 digits." }
        }
        return nil
    }
}

enum AddressType: String, CaseIterable, Identifiable, Codable {
    case fake
    case real
    var id: String { rawValue }
    var title: String { self == .fake ? "Generated Address" : "Yelp Address" }
}

enum SidebarDestination: Hashable {
    case home
    case generator(Carrier)
    case history
    case importer
    case maxicode
    case tracking
}

struct UserSession {
    let userID: String
    let passcode: String
    var remainingRuns: Int
}

struct LabelFormState: Equatable {
    var senderZIP = ""
    var receiverZIP = ""
    var tracking = ""
    var addressType: AddressType = .fake
}

struct FTIDInfo: Codable, Equatable {
    let sender: String
    let senderAddress: String
    let sender2ndLine: String
    let receiver: String
    let receiverAddress: String
    let receiver2ndLine: String
    let trackingNumber: String
    let trackingBar: String
    let receiverZip: String
    let senderZip: String
    let originalTracking: String

    enum CodingKeys: String, CodingKey {
        case sender
        case senderAddress = "sender_address"
        case sender2ndLine = "sender_2nd_line"
        case receiver
        case receiverAddress = "receiver_address"
        case receiver2ndLine = "receiver_2nd_line"
        case trackingNumber = "tracking_number"
        case trackingBar = "tracking_bar"
        case receiverZip = "receiver_zip"
        case senderZip = "sender_zip"
        case originalTracking = "original_tracking"
    }
}

struct LabelGenerationResult: Codable, Equatable {
    let labelPath: String
    let fullLabelPath: String?
    let templateName: String?
    let templatePath: String?
    let carrier: Carrier?
    let method: String
    let ftidInfo: FTIDInfo
    let remainingRuns: Int

    func matchesExpectedBlankTemplate(for carrier: Carrier) -> Bool {
        guard method == carrier.methodName else { return false }
        if let templateName, templateName.lowercased() != carrier.finalTemplateFilename { return false }
        let filename = URL(fileURLWithPath: labelPath).lastPathComponent.lowercased()
        return filename.hasPrefix(carrier.finalTemplateStem) && filename.hasSuffix(".png") && !filename.contains("_full")
    }

    enum CodingKeys: String, CodingKey {
        case labelPath = "label_path"
        case fullLabelPath = "full_label_path"
        case templateName = "template_name"
        case templatePath = "template_path"
        case carrier
        case method
        case ftidInfo = "ftid_info"
        case remainingRuns = "remaining_runs"
    }
}

struct PreviousInputState: Codable, Equatable {
    let senderZip: String
    let receiverZip: String
    let upsTracking: String
    let uspsTracking: String
    let fedexTracking: String
    let addressType: String

    enum CodingKeys: String, CodingKey {
        case senderZip = "sender_zip"
        case receiverZip = "receiver_zip"
        case upsTracking = "ups_tracking"
        case uspsTracking = "usps_tracking"
        case fedexTracking = "fedex_tracking"
        case addressType = "address_type"
    }
}

struct LoginSnapshot: Codable {
    let userID: String
    let remainingRuns: Int
    let settings: AppSettings
    let previousInputs: PreviousInputState
    let historyEntries: [HistoryEntry]
    let previousMaxicodeEntries: [PreviousMaxicodeEntry]

    enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case remainingRuns = "remaining_runs"
        case settings
        case previousInputs = "previous_inputs"
        case historyEntries = "history_entries"
        case previousMaxicodeEntries = "previous_maxicode_entries"
    }
}

struct HealthDiagnostics: Codable {
    let ok: Bool
    let issues: [String]
    let warnings: [String]
}

struct HealthSnapshot: Codable {
    let projectRoot: String
    let baseDir: String
    let outputDir: String
    let stateDir: String
    let settings: AppSettings
    let previousInputs: PreviousInputState
    let historyEntries: [HistoryEntry]
    let previousMaxicodeEntries: [PreviousMaxicodeEntry]
    let historyCount: Int
    let previousMaxicodeCount: Int
    let diagnostics: HealthDiagnostics?
    let resourcesOK: Bool?

    enum CodingKeys: String, CodingKey {
        case projectRoot = "project_root"
        case baseDir = "base_dir"
        case outputDir = "output_dir"
        case stateDir = "state_dir"
        case settings
        case previousInputs = "previous_inputs"
        case historyEntries = "history_entries"
        case previousMaxicodeEntries = "previous_maxicode_entries"
        case historyCount = "history_count"
        case previousMaxicodeCount = "previous_maxicode_count"
        case diagnostics
        case resourcesOK = "resources_ok"
    }
}

struct CollectionsSnapshot: Codable {
    let previousInputs: PreviousInputState
    let historyEntries: [HistoryEntry]
    let previousMaxicodeEntries: [PreviousMaxicodeEntry]

    enum CodingKeys: String, CodingKey {
        case previousInputs = "previous_inputs"
        case historyEntries = "history_entries"
        case previousMaxicodeEntries = "previous_maxicode_entries"
    }
}

struct HistoryResponse: Codable { let entries: [HistoryEntry] }

struct HistoryEntry: Codable, Hashable, Identifiable {
    let timestamp: String
    let method: String
    let trackingNumber: String
    let originalTracking: String
    let senderName: String
    let senderAddress: String
    let senderCityStateZip: String
    let receiverName: String
    let receiverAddress: String
    let receiverCityStateZip: String
    let senderZip: String
    let receiverZip: String

    var id: String { "\(timestamp)-\(method)-\(originalTracking)" }

    enum CodingKeys: String, CodingKey {
        case timestamp, method
        case trackingNumber = "tracking_number"
        case originalTracking = "original_tracking"
        case senderName = "sender_name"
        case senderAddress = "sender_address"
        case senderCityStateZip = "sender_city_state_zip"
        case receiverName = "receiver_name"
        case receiverAddress = "receiver_address"
        case receiverCityStateZip = "receiver_city_state_zip"
        case senderZip = "sender_zip"
        case receiverZip = "receiver_zip"
    }
}

struct PreviousMaxicodeAddress: Codable, Hashable {
    let name: String?
    let address: String?
    let city: String?
    let state: String?
    let zipCode: String
    enum CodingKeys: String, CodingKey { case name, address, city, state; case zipCode = "zip_code" }
}

struct PreviousMaxicodeEntry: Codable, Hashable, Identifiable {
    let timestamp: String
    let maxicodeData: String?
    let method: String
    let trackingNumber: String
    let senderInfo: PreviousMaxicodeAddress
    let receiverInfo: PreviousMaxicodeAddress
    let preview: String
    var id: String { "\(timestamp)-\(trackingNumber)-\(method)" }
    enum CodingKeys: String, CodingKey {
        case timestamp
        case maxicodeData = "maxicode_data"
        case method
        case trackingNumber = "tracking_number"
        case senderInfo = "sender_info"
        case receiverInfo = "receiver_info"
        case preview
    }
}

struct PreviousMaxicodeResponse: Codable { let entries: [PreviousMaxicodeEntry] }

struct ImportPreview: Codable, Equatable {
    let filePath: String
    let rowCount: Int
    let columns: [String]
    let autoMappings: [String: String]
    let previewRows: [[String: String]]
    enum CodingKeys: String, CodingKey { case filePath = "file_path"; case rowCount = "row_count"; case columns; case autoMappings = "auto_mappings"; case previewRows = "preview_rows" }
}

struct ImportedRowResult: Codable, Hashable, Identifiable {
    let rowNumber: Int
    let method: String
    let originalTracking: String
    let modifiedTracking: String
    let labelPath: String
    var id: Int { rowNumber }
    enum CodingKeys: String, CodingKey { case rowNumber = "row_number"; case method; case originalTracking = "original_tracking"; case modifiedTracking = "modified_tracking"; case labelPath = "label_path" }
}

struct SkippedRowResult: Codable, Hashable, Identifiable {
    let rowNumber: Int
    let reason: String
    var id: Int { rowNumber }
    enum CodingKeys: String, CodingKey { case rowNumber = "row_number"; case reason }
}

struct ImportProcessResult: Codable, Equatable {
    let summary: [String: Int]
    let processedRows: [ImportedRowResult]
    var skippedRows: [SkippedRowResult] = []
    var totalRows: Int = 0
    var processedCount: Int = 0
    var skippedCount: Int = 0
    let labelPaths: [String]
    let pdfPath: String?
    let remainingRuns: Int
    enum CodingKeys: String, CodingKey {
        case summary
        case processedRows = "processed_rows"
        case skippedRows = "skipped_rows"
        case totalRows = "total_rows"
        case processedCount = "processed_count"
        case skippedCount = "skipped_count"
        case labelPaths = "label_paths"
        case pdfPath = "pdf_path"
        case remainingRuns = "remaining_runs"
    }
}

struct GeneratedMaxicode: Codable, Equatable {
    let data: String
    let length: Int
    let suggestedFilename: String
    enum CodingKeys: String, CodingKey { case data, length; case suggestedFilename = "suggested_filename" }
}

struct ZipLookupResult: Codable, Equatable {
    let zipCode: String
    let city: String
    let state: String
    let zip: String
    enum CodingKeys: String, CodingKey { case zipCode = "zip_code"; case city, state, zip }
}

struct AppSettings: Codable, Equatable {
    struct FromAddress: Codable, Equatable { var zipCode: String; var city: String; var state: String; enum CodingKeys: String, CodingKey { case zipCode = "zip_code"; case city, state } }
    struct Maxicode: Codable, Equatable { var autoGenerate: Bool; var noCharacterLimit: Bool; var manualMode: Bool; var promptInputMethod: Bool; enum CodingKeys: String, CodingKey { case autoGenerate = "auto_generate"; case noCharacterLimit = "no_character_limit"; case manualMode = "manual_mode"; case promptInputMethod = "prompt_input_method" } }
    struct InputFields: Codable, Equatable { var showSenderName: Bool; var showSenderAddress: Bool; var showReceiverName: Bool; var showReceiverAddress: Bool; var showReceiverZip: Bool; var showTrackingNumber: Bool; enum CodingKeys: String, CodingKey { case showSenderName = "show_sender_name"; case showSenderAddress = "show_sender_address"; case showReceiverName = "show_receiver_name"; case showReceiverAddress = "show_receiver_address"; case showReceiverZip = "show_receiver_zip"; case showTrackingNumber = "show_tracking_number" } }
    struct FileImport: Codable, Equatable { var defaultFormat: String; var autoDetectColumns: Bool; var batchProcessing: Bool; enum CodingKeys: String, CodingKey { case defaultFormat = "default_format"; case autoDetectColumns = "auto_detect_columns"; case batchProcessing = "batch_processing" } }
    struct PreviousMaxicode: Codable, Equatable { var enabled: Bool; var maxEntries: Int; var showPreview: Bool; enum CodingKeys: String, CodingKey { case enabled; case maxEntries = "max_entries"; case showPreview = "show_preview" } }
    struct ZipLookup: Codable, Equatable { var autoIdentify: Bool; var useAPIFallback: Bool; var cacheResults: Bool; enum CodingKeys: String, CodingKey { case autoIdentify = "auto_identify"; case useAPIFallback = "use_api_fallback"; case cacheResults = "cache_results" } }
    struct UI: Codable, Equatable { var showTooltips: Bool; var compactMode: Bool; var theme: String; enum CodingKeys: String, CodingKey { case showTooltips = "show_tooltips"; case compactMode = "compact_mode"; case theme } }

    var fromAddress: FromAddress
    var maxicode: Maxicode
    var inputFields: InputFields
    var fileImport: FileImport
    var previousMaxicode: PreviousMaxicode
    var zipLookup: ZipLookup
    var ui: UI
    var labelLayout: LabelLayout

    enum CodingKeys: String, CodingKey { case fromAddress = "from_address"; case maxicode; case inputFields = "input_fields"; case fileImport = "file_import"; case previousMaxicode = "previous_maxicode"; case zipLookup = "zip_lookup"; case ui; case labelLayout = "label_layout" }

    static let defaultValue = AppSettings(
        fromAddress: .init(zipCode: "", city: "", state: ""),
        maxicode: .init(autoGenerate: true, noCharacterLimit: true, manualMode: false, promptInputMethod: false),
        inputFields: .init(showSenderName: true, showSenderAddress: true, showReceiverName: true, showReceiverAddress: true, showReceiverZip: true, showTrackingNumber: true),
        fileImport: .init(defaultFormat: "excel", autoDetectColumns: true, batchProcessing: true),
        previousMaxicode: .init(enabled: true, maxEntries: 3, showPreview: true),
        zipLookup: .init(autoIdentify: true, useAPIFallback: true, cacheResults: true),
        ui: .init(showTooltips: true, compactMode: false, theme: "default"),
        labelLayout: .defaultValue
    )

    var bridgeValues: [String: Any] {
        var values: [String: Any] = [
            "from_address.zip_code": fromAddress.zipCode,
            "from_address.city": fromAddress.city,
            "from_address.state": fromAddress.state,
            "maxicode.auto_generate": maxicode.autoGenerate,
            "maxicode.no_character_limit": maxicode.noCharacterLimit,
            "maxicode.manual_mode": maxicode.manualMode,
            "maxicode.prompt_input_method": maxicode.promptInputMethod,
            "input_fields.show_sender_name": inputFields.showSenderName,
            "input_fields.show_sender_address": inputFields.showSenderAddress,
            "input_fields.show_receiver_name": inputFields.showReceiverName,
            "input_fields.show_receiver_address": inputFields.showReceiverAddress,
            "input_fields.show_receiver_zip": inputFields.showReceiverZip,
            "input_fields.show_tracking_number": inputFields.showTrackingNumber,
            "file_import.default_format": fileImport.defaultFormat,
            "file_import.auto_detect_columns": fileImport.autoDetectColumns,
            "file_import.batch_processing": fileImport.batchProcessing,
            "previous_maxicode.enabled": previousMaxicode.enabled,
            "previous_maxicode.max_entries": previousMaxicode.maxEntries,
            "previous_maxicode.show_preview": previousMaxicode.showPreview,
            "zip_lookup.auto_identify": zipLookup.autoIdentify,
            "zip_lookup.use_api_fallback": zipLookup.useAPIFallback,
            "zip_lookup.cache_results": zipLookup.cacheResults,
            "ui.show_tooltips": ui.showTooltips,
            "ui.compact_mode": ui.compactMode,
            "ui.theme": ui.theme,
        ]
        values.merge(labelLayout.bridgeValues) { $1 }
        return values
    }

    var preferredColorScheme: ColorScheme? {
        switch ui.theme.lowercased() { case "dark": return .dark; case "light": return .light; default: return nil }
    }
}

// MARK: - Label Layout

struct LabelLayout: Codable, Equatable {
    struct CarrierLayout: Codable, Equatable {
        struct RasterElement: Codable, Equatable {
            var whitespace: Double
            var width: Int
            var height: Int
            var xPosition: Int
            var yPosition: Int
            var xOffset: Int?
            var yOffset: Int?
            var scale: Double?
            var moduleHeight: Double?

            enum CodingKeys: String, CodingKey {
                case whitespace, width, height, scale
                case xPosition = "x_position"
                case yPosition = "y_position"
                case xOffset = "x_offset"
                case yOffset = "y_offset"
                case moduleHeight = "module_height"
            }
        }

        struct Maxicode: Codable, Equatable {
            var whitespace: Int
            var width: Int
            var height: Int
            var xOffset: Int
            var yOffset: Int
            var scale: Double
            var xPosition: Int?
            var yPosition: Int?

            enum CodingKeys: String, CodingKey { case whitespace, width, height, scale; case xOffset = "x_offset"; case yOffset = "y_offset"; case xPosition = "x_position"; case yPosition = "y_position" }
        }

        struct Barcode: Codable, Equatable {
            var whitespace: Double
            var moduleHeight: Double
            var width: Int
            var height: Int
            var xPosition: Int
            var yPosition: Int
            var scale: Double?
            var xOffset: Int?
            var yOffset: Int?

            enum CodingKeys: String, CodingKey { case whitespace, width, height, scale; case moduleHeight = "module_height"; case xPosition = "x_position"; case yPosition = "y_position"; case xOffset = "x_offset"; case yOffset = "y_offset" }
        }

        struct ZipBarcode: Codable, Equatable {
            var whitespace: Double
            var moduleHeight: Double
            var width: Int
            var height: Int
            var xPosition: Int
            var yPosition: Int
            var scale: Double?
            var xOffset: Int?
            var yOffset: Int?

            enum CodingKeys: String, CodingKey { case whitespace, width, height, scale; case moduleHeight = "module_height"; case xPosition = "x_position"; case yPosition = "y_position"; case xOffset = "x_offset"; case yOffset = "y_offset" }
        }

        struct TemplateMask: Codable, Equatable {
            var enabled: Bool
            var xPosition: Int
            var yPosition: Int
            var width: Int
            var height: Int
            var opacity: Double
            var scale: Double?
            var whitespace: Double?

            enum CodingKeys: String, CodingKey { case enabled, width, height, opacity, scale, whitespace; case xPosition = "x_position"; case yPosition = "y_position" }
        }

        struct TextBlock: Codable, Equatable {
            var startX: Int
            var startY: Int
            var fontSize: Int
            var scale: Double
            var lineSpacing: Int
            var charSpacing: Double
            var horizontalSquish: Double?
            var text: String?
            var whitespace: Double?
            var width: Int?
            var height: Int?
            var xOffset: Int?
            var yOffset: Int?

            enum CodingKeys: String, CodingKey {
                case scale, text, whitespace, width, height
                case startX = "start_x"
                case startY = "start_y"
                case fontSize = "font_size"
                case lineSpacing = "line_spacing"
                case charSpacing = "char_spacing"
                case horizontalSquish = "horizontal_squish"
                case xOffset = "x_offset"
                case yOffset = "y_offset"
            }

            static let defaultFedExText = TextBlock(startX: 70, startY: 0, fontSize: 34, scale: 1.0, lineSpacing: 20, charSpacing: 1, horizontalSquish: 0.9, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0)
            static let defaultCenterText = TextBlock(startX: 115, startY: 600, fontSize: 50, scale: 2.5, lineSpacing: 0, charSpacing: -10, horizontalSquish: nil, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0)
            static let defaultTopNumber = TextBlock(startX: 617, startY: -5, fontSize: 52, scale: 1.0, lineSpacing: 0, charSpacing: 0, horizontalSquish: nil, text: "1", whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0)
        }

        struct CenterText: Codable, Equatable {
            var scale: Double
            var yPosition: Int
            var xPosition: Int?
            var width: Int?
            var height: Int?
            var fontSize: Int?
            var lineSpacing: Int?
            var charSpacing: Double?
            var horizontalSquish: Double?
            var text: String?
            var whitespace: Double?
            var xOffset: Int?
            var yOffset: Int?

            enum CodingKeys: String, CodingKey { case scale, width, height, text, whitespace; case yPosition = "y_position"; case xPosition = "x_position"; case fontSize = "font_size"; case lineSpacing = "line_spacing"; case charSpacing = "char_spacing"; case horizontalSquish = "horizontal_squish"; case xOffset = "x_offset"; case yOffset = "y_offset" }

            var asTextBlock: TextBlock {
                TextBlock(startX: xPosition ?? 115, startY: yPosition, fontSize: fontSize ?? 50, scale: scale, lineSpacing: lineSpacing ?? 0, charSpacing: charSpacing ?? -10, horizontalSquish: horizontalSquish, text: text, whitespace: whitespace ?? 0, width: width, height: height, xOffset: xOffset ?? 0, yOffset: yOffset ?? 0)
            }
        }

        struct ZipBarcodePos: Codable, Equatable {
            var xPosition: Int
            var yPosition: Int
            enum CodingKeys: String, CodingKey { case xPosition = "x_position"; case yPosition = "y_position" }
        }

        struct TopNumber: Codable, Equatable {
            var yPosition: Int
            var xPosition: Int?
            var width: Int?
            var height: Int?
            var fontSize: Int?
            var scale: Double?
            var lineSpacing: Int?
            var charSpacing: Double?
            var horizontalSquish: Double?
            var text: String?
            var whitespace: Double?
            var xOffset: Int?
            var yOffset: Int?

            enum CodingKeys: String, CodingKey { case width, height, scale, text, whitespace; case yPosition = "y_position"; case xPosition = "x_position"; case fontSize = "font_size"; case lineSpacing = "line_spacing"; case charSpacing = "char_spacing"; case horizontalSquish = "horizontal_squish"; case xOffset = "x_offset"; case yOffset = "y_offset" }

            var asTextBlock: TextBlock {
                TextBlock(startX: xPosition ?? 617, startY: yPosition, fontSize: fontSize ?? 52, scale: scale ?? 1.0, lineSpacing: lineSpacing ?? 0, charSpacing: charSpacing ?? 0, horizontalSquish: horizontalSquish, text: text ?? "1", whitespace: whitespace ?? 0, width: width, height: height, xOffset: xOffset ?? 0, yOffset: yOffset ?? 0)
            }
        }

        struct TextLayout: Codable, Equatable {
            var sender: TextBlock
            var receiver: TextBlock
            var receiver2nd: TextBlock?
            var tracking: TextBlock
            var centerText: CenterText?
            var zipBarcode: ZipBarcodePos?
            var topNumber: TopNumber?
            var fromLabel: TextBlock?
            var shipToLabel: TextBlock?
            var trackingPrefix: TextBlock?
            var receiverZip: TextBlock?

            enum CodingKeys: String, CodingKey { case sender, receiver, tracking; case receiver2nd = "receiver_2nd"; case centerText = "center_text"; case zipBarcode = "zip_barcode"; case topNumber = "top_number"; case fromLabel = "from_label"; case shipToLabel = "ship_to_label"; case trackingPrefix = "tracking_prefix"; case receiverZip = "receiver_zip" }
        }

        var maxicode: Maxicode
        var barcode: Barcode
        var zipBarcode: ZipBarcode
        var text: TextLayout
        var templateMask: TemplateMask?
        var customTemplatePath: String?

        enum CodingKeys: String, CodingKey { case maxicode, barcode, text; case zipBarcode = "zip_barcode"; case templateMask = "template_mask"; case customTemplatePath = "custom_template_path" }
    }

    var ups: CarrierLayout
    var usps: CarrierLayout
    var fedex: CarrierLayout
    enum CodingKeys: String, CodingKey { case ups, usps, fedex }
    static let defaultValue = LabelLayout(ups: .defaultUPS, usps: .defaultUSPS, fedex: .defaultFedEx)

    var bridgeValues: [String: Any] {
        func flatten(_ prefix: String, _ dict: [String: Any]) -> [String: Any] {
            var result: [String: Any] = [:]
            for (key, value) in dict {
                let path = "\(prefix).\(key)"
                if let sub = value as? [String: Any] { result.merge(flatten(path, sub)) { $1 } } else { result[path] = value }
            }
            return result
        }
        let enc = JSONEncoder(); enc.outputFormatting = .sortedKeys
        guard let data = try? enc.encode(self), let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [:] }
        return flatten("label_layout", obj)
    }
}

extension LabelLayout.CarrierLayout {

    static let defaultUPS = LabelLayout.CarrierLayout(
        maxicode: .init(whitespace: 0, width: 312, height: 288, xOffset: 42, yOffset: -1144, scale: 2.0, xPosition: 42, yPosition: nil),
        barcode: .init(whitespace: 6.5, moduleHeight: 15.0, width: 970, height: 300, xPosition: 90, yPosition: 1190, scale: 1.0, xOffset: 0, yOffset: 0),
        zipBarcode: .init(whitespace: 6.5, moduleHeight: 40.0, width: 720, height: 170, xPosition: 285, yPosition: 765, scale: 1.0, xOffset: 0, yOffset: 0),
        text: .init(
            sender: .init(startX: 26, startY: 3, fontSize: 28, scale: 1.3, lineSpacing: -8, charSpacing: 1.3, horizontalSquish: nil, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            receiver: .init(startX: 105, startY: 235, fontSize: 40, scale: 1.2, lineSpacing: -9, charSpacing: 1.5, horizontalSquish: nil, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            receiver2nd: .init(startX: 105, startY: 310, fontSize: 60, scale: 1.2, lineSpacing: 0, charSpacing: -4, horizontalSquish: nil, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            tracking: .init(startX: 293, startY: 1055, fontSize: 44, scale: 1.1, lineSpacing: 0, charSpacing: 0.3, horizontalSquish: nil, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            centerText: .init(scale: 2.5, yPosition: 600, xPosition: 115, width: nil, height: nil, fontSize: 50, lineSpacing: 0, charSpacing: -10, horizontalSquish: nil, text: nil, whitespace: 0, xOffset: 0, yOffset: 0),
            zipBarcode: .init(xPosition: 285, yPosition: 765),
            topNumber: .init(yPosition: -5, xPosition: 617, width: nil, height: nil, fontSize: 52, scale: 1.0, lineSpacing: 0, charSpacing: 0, horizontalSquish: nil, text: "1", whitespace: 0, xOffset: 0, yOffset: 0),
            fromLabel: nil, shipToLabel: nil, trackingPrefix: nil, receiverZip: nil
        ),
        templateMask: .init(enabled: true, xPosition: 0, yPosition: 585, width: 405, height: 375, opacity: 0.9, scale: 1.0, whitespace: 0),
        customTemplatePath: nil
    )

    static let defaultUSPS = LabelLayout.CarrierLayout(
        maxicode: .init(whitespace: 0, width: 312, height: 288, xOffset: 42, yOffset: -1144, scale: 2.0, xPosition: 42, yPosition: nil),
        barcode: .init(whitespace: 6.5, moduleHeight: 15.0, width: 760, height: 205, xPosition: 115, yPosition: 1040, scale: 1.0, xOffset: 0, yOffset: 0),
        zipBarcode: .init(whitespace: 6.5, moduleHeight: 40.0, width: 720, height: 170, xPosition: 285, yPosition: 765, scale: 1.0, xOffset: 0, yOffset: 0),
        text: .init(
            sender: .init(startX: 20, startY: 474, fontSize: 28, scale: 1.0, lineSpacing: 7, charSpacing: 1.3, horizontalSquish: nil, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            receiver: .init(startX: 165, startY: 725, fontSize: 40, scale: 1.1, lineSpacing: 8, charSpacing: 1.5, horizontalSquish: nil, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            receiver2nd: .init(startX: 165, startY: 825, fontSize: 40, scale: 1.1, lineSpacing: 0, charSpacing: 0, horizontalSquish: nil, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            tracking: .init(startX: 262, startY: 1270, fontSize: 60, scale: 0.6, lineSpacing: 0, charSpacing: -1.5, horizontalSquish: nil, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            centerText: nil, zipBarcode: nil, topNumber: nil,
            fromLabel: nil, shipToLabel: nil, trackingPrefix: nil, receiverZip: nil
        ),
        templateMask: nil,
        customTemplatePath: nil
    )

    static let defaultFedEx = LabelLayout.CarrierLayout(
        maxicode: .init(whitespace: 0, width: 312, height: 288, xOffset: 42, yOffset: -1144, scale: 2.0, xPosition: 42, yPosition: nil),
        barcode: .init(whitespace: 6.5, moduleHeight: 15.0, width: 1080, height: 310, xPosition: 155, yPosition: 1588, scale: 1.0, xOffset: 0, yOffset: 0),
        zipBarcode: .init(whitespace: 6.5, moduleHeight: 40.0, width: 720, height: 170, xPosition: 1120, yPosition: 1340, scale: 1.0, xOffset: 0, yOffset: 0),
        text: .init(
            sender: .init(startX: 70, startY: 52, fontSize: 33, scale: 1.0, lineSpacing: 20, charSpacing: 1, horizontalSquish: 0.9, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            receiver: .init(startX: 82, startY: 312, fontSize: 42, scale: 1.05, lineSpacing: 18, charSpacing: 1, horizontalSquish: 0.9, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            receiver2nd: nil,
            tracking: .init(startX: 170, startY: 1220, fontSize: 62, scale: 1.0, lineSpacing: 0, charSpacing: 0, horizontalSquish: 0.9, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            centerText: nil, zipBarcode: nil, topNumber: nil,
            fromLabel: .init(startX: 70, startY: 14, fontSize: 34, scale: 1.0, lineSpacing: 20, charSpacing: 1, horizontalSquish: 0.9, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            shipToLabel: .init(startX: 70, startY: 262, fontSize: 34, scale: 1.0, lineSpacing: 0, charSpacing: 1, horizontalSquish: 0.9, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            trackingPrefix: .init(startX: 258, startY: 1480, fontSize: 55, scale: 0.8, lineSpacing: 0, charSpacing: 2.5, horizontalSquish: 0.91, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0),
            receiverZip: .init(startX: 1120, startY: 1340, fontSize: 60, scale: 1.1, lineSpacing: 0, charSpacing: 0, horizontalSquish: 1.0, text: nil, whitespace: 0, width: nil, height: nil, xOffset: 0, yOffset: 0)
        ),
        templateMask: nil,
        customTemplatePath: nil
    )
}

enum ImportField: String, CaseIterable, Identifiable {
    case trackingNumber = "tracking_number"
    case senderZip = "sender_zip"
    case receiverZip = "receiver_zip"
    case senderName = "sender_name"
    case receiverName = "receiver_name"
    case senderAddress = "sender_address"
    case receiverAddress = "receiver_address"
    case method = "method"
    var id: String { rawValue }
    var title: String {
        switch self {
        case .trackingNumber: return "Tracking Number"
        case .senderZip: return "Sender ZIP"
        case .receiverZip: return "Receiver ZIP"
        case .senderName: return "Sender Name"
        case .receiverName: return "Receiver Name"
        case .senderAddress: return "Sender Address"
        case .receiverAddress: return "Receiver Address"
        case .method: return "Carrier / Method"
        }
    }
    var isRequired: Bool { self == .trackingNumber || self == .senderZip || self == .receiverZip }
}

enum TrackingStatus: String, Codable, CaseIterable, Identifiable {
    case pending
    case inTransit = "in_transit"
    case outForDelivery = "out_for_delivery"
    case delivered
    case exception
    case unknown
    var id: String { rawValue }
    var title: String {
        switch self {
        case .pending: return "Pending"
        case .inTransit: return "In Transit"
        case .outForDelivery: return "Out for Delivery"
        case .delivered: return "Delivered"
        case .exception: return "Exception"
        case .unknown: return "Unknown"
        }
    }
    var color: String {
        switch self {
        case .pending: return "gray"
        case .inTransit: return "blue"
        case .outForDelivery: return "orange"
        case .delivered: return "green"
        case .exception: return "red"
        case .unknown: return "gray"
        }
    }
    var systemImage: String {
        switch self {
        case .pending: return "clock"
        case .inTransit: return "shippingbox"
        case .outForDelivery: return "truck"
        case .delivered: return "checkmark.circle.fill"
        case .exception: return "exclamationmark.triangle.fill"
        case .unknown: return "questionmark.circle"
        }
    }
    var isActive: Bool { self == .pending || self == .inTransit || self == .outForDelivery }
}

struct TrackingTimelineEntry: Codable, Hashable {
    let timestamp: String
    let status: String
    let location: String
    let details: String
    var id: String { "\(timestamp)-\(status)-\(location)" }
    init(timestamp: String, status: String, location: String, details: String) { self.timestamp = timestamp; self.status = status; self.location = location; self.details = details }
    enum CodingKeys: String, CodingKey { case timestamp, status, location, details }
}

struct TrackingEntry: Codable, Hashable, Identifiable {
    let id: String
    let trackingNumber: String
    let carrier: String
    var status: String
    var statusDetails: String
    var lastUpdated: String
    var label: String
    var store: String
    var originZip: String
    var destinationZip: String
    var estimatedDelivery: String
    var history: [TrackingTimelineEntry]
    let createdAt: String
    var source: String
    var notificationSeen: Bool

    var trackingURL: URL? {
        let cleaned = trackingNumber.replacingOccurrences(of: " ", with: "")
        switch carrier.uppercased() {
        case "USPS": return URL(string: "https://tools.usps.com/go/TrackConfirmAction?tLabels=\(cleaned)")
        case "UPS": return URL(string: "https://www.ups.com/track?loc=en_US&tracknum=\(cleaned)")
        case "FEDEX": return URL(string: "https://www.fedex.com/fedextrack/?trknbr=\(cleaned)")
        default: return nil
        }
    }
    var statusEnum: TrackingStatus { TrackingStatus(rawValue: status) ?? .unknown }
    var carrierSystemImage: String { carrier.uppercased() == "USPS" ? "mail.stack.fill" : (carrier.uppercased() == "FEDEX" ? "truck.box.fill" : (carrier.uppercased() == "UPS" ? "shippingbox.fill" : "shippingbox")) }
    var carrierColor: String { carrier.uppercased() == "USPS" ? "blue" : (carrier.uppercased() == "FEDEX" ? "purple" : (carrier.uppercased() == "UPS" ? "brown" : "gray")) }

    enum CodingKeys: String, CodingKey {
        case id
        case trackingNumber = "tracking_number"
        case carrier, status
        case statusDetails = "status_details"
        case lastUpdated = "last_updated"
        case label, store
        case originZip = "origin_zip"
        case destinationZip = "destination_zip"
        case estimatedDelivery = "estimated_delivery"
        case history
        case createdAt = "created_at"
        case source
        case notificationSeen = "notification_seen"
    }
}

struct TrackingListResponse: Codable { let entries: [TrackingEntry]; let stats: TrackingStats }

struct TrackingStats: Codable {
    let total: Int
    let active: Int
    let delivered: Int
    let exception: Int
    let byCarrier: [String: Int]
    let byStatus: [String: Int]
    enum CodingKeys: String, CodingKey { case total, active, delivered, exception; case byCarrier = "by_carrier"; case byStatus = "by_status" }
}
