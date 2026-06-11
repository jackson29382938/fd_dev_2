import AppKit
import SwiftUI

final class FTIDAppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}

@main
struct FTIDMacAppApp: App {
    @NSApplicationDelegateAdaptor(FTIDAppDelegate.self) private var appDelegate
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup("FTID Generator", id: "main") {
            ContentView()
                .environmentObject(model)
                .frame(minWidth: 480, minHeight: 560)
                .preferredColorScheme(model.settings.preferredColorScheme)
        }
        .defaultSize(width: 1320, height: 860)
        .windowResizability(.contentMinSize)

        Settings {
            SettingsView()
                .environmentObject(model)
                .frame(minWidth: 720, minHeight: 760)
                .preferredColorScheme(model.settings.preferredColorScheme)
        }
    }
}
