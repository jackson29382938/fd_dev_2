import AppKit
import UniformTypeIdentifiers

enum FilePanelService {
    static func chooseImportFile() -> URL? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = compactTypes(["xlsx", "xls", "csv"])
        return panel.runModal() == .OK ? panel.url : nil
    }

    static func chooseSettingsImportFile() -> URL? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = compactTypes(["json"])
        return panel.runModal() == .OK ? panel.url : nil
    }

    static func chooseTemplateImageFile() -> URL? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = compactTypes(["png", "jpg", "jpeg"])
        return panel.runModal() == .OK ? panel.url : nil
    }

    static func chooseTemplateDestination(defaultName: String) -> URL? {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = defaultName
        panel.allowedContentTypes = compactTypes(["xlsx"])
        panel.canCreateDirectories = true
        return panel.runModal() == .OK ? panel.url : nil
    }

    static func chooseSettingsExportDestination(defaultName: String) -> URL? {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = defaultName
        panel.allowedContentTypes = compactTypes(["json"])
        panel.canCreateDirectories = true
        return panel.runModal() == .OK ? panel.url : nil
    }

    static func chooseTextExportDestination(defaultName: String) -> URL? {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = defaultName
        panel.allowedContentTypes = compactTypes(["txt"])
        panel.canCreateDirectories = true
        return panel.runModal() == .OK ? panel.url : nil
    }

    private static func compactTypes(_ extensions: [String]) -> [UTType] {
        extensions.compactMap { UTType(filenameExtension: $0) }
    }
}
