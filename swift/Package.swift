// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "FTIDMacApp",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(
            name: "FTIDMacApp",
            targets: ["FTIDMacApp"]
        )
    ],
    targets: [
        .executableTarget(
            name: "FTIDMacApp",
            path: "Sources/FTIDMacApp"
        )
    ]
)
