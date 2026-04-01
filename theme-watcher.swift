import Cocoa
import Foundation

// Parse CLI args: --dark <name> --light <name>
var darkTheme = "dark-ansi"
var lightTheme = "light-ansi"
let args = CommandLine.arguments
for i in 0..<args.count {
    if args[i] == "--dark", i + 1 < args.count { darkTheme = args[i + 1] }
    if args[i] == "--light", i + 1 < args.count { lightTheme = args[i + 1] }
}

let outputPath = NSString("~/.claude/.current-theme").expandingTildeInPath

func isDarkMode() -> Bool {
    UserDefaults.standard.string(forKey: "AppleInterfaceStyle") == "Dark"
}

func writeTheme() {
    let theme = isDarkMode() ? darkTheme : lightTheme
    let outputURL = URL(fileURLWithPath: outputPath)
    let dir = outputURL.deletingLastPathComponent()

    // Atomic write: temp file + rename
    let tmpURL = dir.appendingPathComponent(".current-theme.\(ProcessInfo.processInfo.processIdentifier).tmp")
    do {
        try (theme + "\n").write(to: tmpURL, atomically: false, encoding: .utf8)
        _ = try FileManager.default.replaceItemAt(outputURL, withItemAt: tmpURL)
    } catch {
        // Fallback: direct atomic write
        try? (theme + "\n").write(toFile: outputPath, atomically: true, encoding: .utf8)
    }

    print(theme)
    fflush(stdout)
}

// Emit current theme immediately
writeTheme()

// Listen for appearance changes
DistributedNotificationCenter.default().addObserver(
    forName: Notification.Name("AppleInterfaceThemeChangedNotification"),
    object: nil,
    queue: .main
) { _ in
    writeTheme()
}

// Run forever
RunLoop.main.run()
