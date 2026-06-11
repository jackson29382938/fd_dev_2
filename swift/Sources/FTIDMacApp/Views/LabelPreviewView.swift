import AppKit
import CoreText
import SwiftUI

struct NativeTextRenderer {
    let fontMainURL: URL?
    let fontBoldURL: URL?
    let fontArialURL: URL?

    init() {
        if let resourceRoot = Bundle.main.resourceURL {
            let backend = resourceRoot.appendingPathComponent("backend")
            let req = backend.appendingPathComponent("requirements")
            fontMainURL = req.appendingPathComponent("NotoSans-ExtraCondensedSemiBold.ttf")
            fontBoldURL = req.appendingPathComponent("NotoSans-CondensedBold.ttf")
            fontArialURL = req.appendingPathComponent("ARIAL.TTF")
        } else {
            fontMainURL = nil
            fontBoldURL = nil
            fontArialURL = nil
        }
    }

    private func loadFont(at url: URL?, size: CGFloat) -> CTFont? {
        guard let url,
              let data = try? Data(contentsOf: url),
              let provider = CGDataProvider(data: data as CFData),
              let cgFont = CGFont(provider) else { return nil }
        return CTFontCreateWithGraphicsFont(cgFont, size, nil, nil)
    }

    func render(lines: [String], fontURL: URL?, baseFontSize: CGFloat, scale: CGFloat, lineSpacing: CGFloat, charSpacing: CGFloat, uppercase: Bool = true, horizontalSquish: CGFloat = 1.0) -> NSImage {
        let fontSize = max(1, baseFontSize * scale)
        guard let font = loadFont(at: fontURL, size: fontSize) else { return NSImage(size: NSSize(width: 1, height: 1)) }

        var maxWidth: CGFloat = 0
        var totalHeight: CGFloat = 0
        var lineMetrics: [(height: CGFloat, maxY: CGFloat)] = []

        for line in lines {
            let text = uppercase ? line.uppercased() : line
            var lineWidth: CGFloat = 0
            var maxY: CGFloat = -.greatestFiniteMagnitude
            var minY: CGFloat = .greatestFiniteMagnitude
            for char in text {
                let utf16 = Array(String(char).utf16)
                var glyph: CGGlyph = 0
                _ = CTFontGetGlyphsForCharacters(font, utf16, &glyph, 1)
                if glyph == 0 {
                    let fallback = Array(".".utf16)
                    _ = CTFontGetGlyphsForCharacters(font, fallback, &glyph, 1)
                }
                var rect = CGRect.zero
                CTFontGetBoundingRectsForGlyphs(font, .default, &glyph, &rect, 1)
                let advance = CTFontGetAdvancesForGlyphs(font, .default, &glyph, nil, 1)
                lineWidth += advance + charSpacing * scale
                maxY = max(maxY, rect.maxY)
                minY = min(minY, rect.minY)
            }
            maxWidth = max(maxWidth, lineWidth * horizontalSquish)
            let height = max(1, maxY - minY + lineSpacing * scale)
            lineMetrics.append((height: height, maxY: maxY))
            totalHeight += height
        }

        let canvasWidth = max(1, maxWidth)
        let canvasHeight = max(1, totalHeight)
        guard let ctx = CGContext(data: nil, width: Int(ceil(canvasWidth)), height: Int(ceil(canvasHeight)), bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
            return NSImage(size: NSSize(width: 1, height: 1))
        }
        ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 0))
        ctx.fill(CGRect(x: 0, y: 0, width: canvasWidth, height: canvasHeight))
        ctx.setFillColor(CGColor(red: 0, green: 0, blue: 0, alpha: 1))
        ctx.textMatrix = .identity

        var yOffset: CGFloat = 0
        for (index, line) in lines.enumerated() {
            let text = uppercase ? line.uppercased() : line
            let metrics = lineMetrics[index]
            let baselineY = canvasHeight - yOffset - metrics.maxY
            var xPos: CGFloat = 0
            for char in text {
                let utf16 = Array(String(char).utf16)
                var glyph: CGGlyph = 0
                _ = CTFontGetGlyphsForCharacters(font, utf16, &glyph, 1)
                if glyph == 0 {
                    let fallback = Array(".".utf16)
                    _ = CTFontGetGlyphsForCharacters(font, fallback, &glyph, 1)
                }
                let advance = CTFontGetAdvancesForGlyphs(font, .default, &glyph, nil, 1)
                var transform = CGAffineTransform.identity
                    .translatedBy(x: xPos, y: baselineY)
                    .scaledBy(x: horizontalSquish, y: 1)
                if let path = CTFontCreatePathForGlyph(font, glyph, &transform) {
                    ctx.addPath(path)
                    ctx.fillPath()
                }
                xPos += advance + charSpacing * scale
            }
            yOffset += metrics.height
        }

        guard let cgImage = ctx.makeImage() else { return NSImage(size: NSSize(width: 1, height: 1)) }
        return NSImage(cgImage: cgImage, size: NSSize(width: canvasWidth, height: canvasHeight)).previewTextContentImage()
    }
}

private struct PreviewRasterOverlay: View {
    let image: NSImage
    let displayScale: CGFloat
    let width: CGFloat
    let height: CGFloat
    let whitespace: CGFloat
    let x: CGFloat
    let y: CGFloat
    var interpolation: Image.Interpolation = .none
    var onDragEnded: ((CGSize) -> Void)? = nil

    private var outerWidth: CGFloat { max(width, 1) }
    private var outerHeight: CGFloat { max(height, 1) }
    private var safeWhitespace: CGFloat { min(max(0, whitespace), max(0, min(outerWidth, outerHeight) / 2 - 0.5)) }
    private var innerWidth: CGFloat { max(outerWidth - safeWhitespace * 2, 1) }
    private var innerHeight: CGFloat { max(outerHeight - safeWhitespace * 2, 1) }

    var body: some View {
        ZStack(alignment: .topLeading) {
            Image(nsImage: image.previewRasterContentImage())
                .resizable()
                .interpolation(interpolation)
                .frame(width: innerWidth * displayScale, height: innerHeight * displayScale)
                .offset(x: safeWhitespace * displayScale, y: safeWhitespace * displayScale)
        }
        .frame(width: outerWidth * displayScale, height: outerHeight * displayScale, alignment: .topLeading)
        .contentShape(Rectangle())
        .offset(x: x * displayScale, y: y * displayScale)
        .gesture(DragGesture().onEnded { onDragEnded?($0.translation) })
    }
}

private struct PreviewGuideFrame: View {
    let label: String
    let x: CGFloat
    let y: CGFloat
    let width: CGFloat
    let height: CGFloat
    let displayScale: CGFloat
    var color: Color = .accentColor

    var body: some View {
        ZStack(alignment: .topLeading) {
            Rectangle().stroke(color, style: StrokeStyle(lineWidth: 1, dash: [4, 3])).background(color.opacity(0.04))
            Text(label).font(.system(size: 9, weight: .semibold, design: .monospaced)).padding(.horizontal, 3).padding(.vertical, 1).background(.thinMaterial).clipShape(RoundedRectangle(cornerRadius: 3)).offset(x: 2, y: 2)
        }
        .frame(width: max(width * displayScale, 1), height: max(height * displayScale, 1))
        .offset(x: x * displayScale, y: y * displayScale)
        .allowsHitTesting(false)
    }
}

private struct PreviewMaskOverlay: View {
    let mask: LabelLayout.CarrierLayout.TemplateMask
    let displayScale: CGFloat
    var onDragEnded: ((CGSize) -> Void)? = nil

    var body: some View {
        let scale = CGFloat(mask.scale ?? 1.0)
        Rectangle()
            .fill(Color.white.opacity(mask.opacity))
            .frame(width: CGFloat(mask.width) * scale * displayScale, height: CGFloat(mask.height) * scale * displayScale)
            .overlay(Rectangle().stroke(Color.gray.opacity(0.7), style: StrokeStyle(lineWidth: 1, dash: [5, 3])))
            .offset(x: CGFloat(mask.xPosition) * displayScale, y: CGFloat(mask.yPosition) * displayScale)
            .gesture(DragGesture().onEnded { onDragEnded?($0.translation) })
    }
}

struct LabelPreviewView: View {
    @Binding var layout: LabelLayout.CarrierLayout
    let ftidInfo: FTIDInfo?
    let compositeImage: NSImage?
    let templateImage: NSImage?
    let barcodeImage: NSImage?
    let maxicodeImage: NSImage?
    let zipBarcodeImage: NSImage?
    var templatePixelSize: CGSize? = nil
    var showElementFrames: Bool = false

    private var usesCompositePreview: Bool { compositeImage != nil }

    @State private var textImages: [String: NSImage] = [:]
    @State private var templateSize: CGSize = .zero
    @State private var renderTask: Task<Void, Never>?
    private let renderer = NativeTextRenderer()
    private let maxicodeScaleBaseline: CGFloat = 2.0

    var body: some View {
        GeometryReader { geo in
            let widthScale = geo.size.width / max(templateSize.width, 1)
            let heightScale = geo.size.height > 0 ? geo.size.height / max(templateSize.height, 1) : widthScale
            let scale = min(1.0, widthScale, heightScale)
            let displaySize = CGSize(width: templateSize.width * scale, height: templateSize.height * scale)
            let maxicodeScale = max(0.1, CGFloat(layout.maxicode.scale) / maxicodeScaleBaseline)
            let maxicodeWidth = CGFloat(layout.maxicode.width) * maxicodeScale
            let maxicodeHeight = CGFloat(layout.maxicode.height) * maxicodeScale
            let maxicodeY = templateSize.height + CGFloat(layout.maxicode.yOffset)

            ZStack(alignment: .topLeading) {
                if let composite = compositeImage {
                    Image(nsImage: composite).resizable().interpolation(.high).frame(width: displaySize.width, height: displaySize.height)
                } else if let img = templateImage {
                    Image(nsImage: img).resizable().interpolation(.high).frame(width: displaySize.width, height: displaySize.height)
                }

                if let mask = layout.templateMask, mask.enabled, !usesCompositePreview {
                    PreviewMaskOverlay(mask: mask, displayScale: scale) { translation in
                        layout.templateMask?.xPosition += Int(round(translation.width / max(scale, 0.01)))
                        layout.templateMask?.yPosition += Int(round(translation.height / max(scale, 0.01)))
                    }
                }

                if !usesCompositePreview, let mc = maxicodeImage {
                    PreviewRasterOverlay(image: mc, displayScale: scale, width: maxicodeWidth, height: maxicodeHeight, whitespace: CGFloat(layout.maxicode.whitespace), x: CGFloat(layout.maxicode.xOffset), y: maxicodeY) { translation in
                        layout.maxicode.xOffset += Int(round(translation.width / max(scale, 0.01)))
                        layout.maxicode.yOffset += Int(round(translation.height / max(scale, 0.01)))
                    }
                }

                if !usesCompositePreview, let bc = barcodeImage {
                    PreviewRasterOverlay(image: bc, displayScale: scale, width: CGFloat(layout.barcode.width) * CGFloat(layout.barcode.scale ?? 1.0), height: CGFloat(layout.barcode.height) * CGFloat(layout.barcode.scale ?? 1.0), whitespace: CGFloat(layout.barcode.whitespace), x: CGFloat(layout.barcode.xPosition), y: CGFloat(layout.barcode.yPosition)) { translation in
                        layout.barcode.xPosition += Int(round(translation.width / max(scale, 0.01)))
                        layout.barcode.yPosition += Int(round(translation.height / max(scale, 0.01)))
                    }
                }

                if !usesCompositePreview, let zipBc = zipBarcodeImage {
                    PreviewRasterOverlay(image: zipBc, displayScale: scale, width: CGFloat(layout.zipBarcode.width) * CGFloat(layout.zipBarcode.scale ?? 1.0), height: CGFloat(layout.zipBarcode.height) * CGFloat(layout.zipBarcode.scale ?? 1.0), whitespace: CGFloat(layout.zipBarcode.whitespace), x: CGFloat(layout.zipBarcode.xPosition), y: CGFloat(layout.zipBarcode.yPosition)) { translation in
                        layout.zipBarcode.xPosition += Int(round(translation.width / max(scale, 0.01)))
                        layout.zipBarcode.yPosition += Int(round(translation.height / max(scale, 0.01)))
                    }
                }

                if !usesCompositePreview {
                    textOverlay("sender", block: $layout.text.sender, scale: scale)
                    textOverlay("receiver", block: $layout.text.receiver, scale: scale)
                    if layout.text.receiver2nd != nil { optionalTextOverlay("receiver_2nd", block: Binding(get: { layout.text.receiver2nd ?? .defaultFedExText }, set: { layout.text.receiver2nd = $0 }), scale: scale) }
                    textOverlay("tracking", block: $layout.text.tracking, scale: scale)
                    if layout.text.fromLabel != nil { optionalTextOverlay("from_label", block: Binding(get: { layout.text.fromLabel ?? .defaultFedExText }, set: { layout.text.fromLabel = $0 }), scale: scale) }
                    if layout.text.shipToLabel != nil { optionalTextOverlay("ship_to_label", block: Binding(get: { layout.text.shipToLabel ?? .defaultFedExText }, set: { layout.text.shipToLabel = $0 }), scale: scale) }
                    if layout.text.trackingPrefix != nil { optionalTextOverlay("tracking_prefix", block: Binding(get: { layout.text.trackingPrefix ?? .defaultFedExText }, set: { layout.text.trackingPrefix = $0 }), scale: scale) }
                    if layout.text.receiverZip != nil { optionalTextOverlay("receiver_zip_text", block: Binding(get: { layout.text.receiverZip ?? .defaultFedExText }, set: { layout.text.receiverZip = $0 }), scale: scale) }

                    if layout.text.centerText != nil {
                        centerTextOverlay(scale: scale)
                    }
                    if layout.text.topNumber != nil {
                        topNumberOverlay(scale: scale)
                    }
                }

                if showElementFrames {
                    previewGuideFrames(scale: scale, maxicodeWidth: maxicodeWidth, maxicodeHeight: maxicodeHeight, maxicodeY: maxicodeY)
                }
            }
            .frame(width: displaySize.width, height: displaySize.height, alignment: .topLeading)
            .clipped()
        }
        .onAppear { templateSize = resolvedTemplateSize; if !usesCompositePreview { renderAllText() } }
        .onChange(of: ftidInfo) { _, _ in if !usesCompositePreview { debouncedRender() } }
        .onChange(of: layout) { _, _ in if !usesCompositePreview { debouncedRender() } }
        .onChange(of: compositeImage?.pixelSize) { _, _ in templateSize = resolvedTemplateSize }
        .onChange(of: templateImage?.pixelSize) { _, _ in templateSize = resolvedTemplateSize }
        .onChange(of: templatePixelSize) { _, _ in templateSize = resolvedTemplateSize }
        .aspectRatio(templateSize.width > 0 ? templateSize.width / templateSize.height : 0.7, contentMode: .fit)
    }

    private var resolvedTemplateSize: CGSize {
        if let templatePixelSize, templatePixelSize.width > 0, templatePixelSize.height > 0 { return templatePixelSize }
        if let compositeImage { return compositeImage.pixelSize }
        return templateImage?.pixelSize ?? .zero
    }

    @ViewBuilder private func textOverlay(_ key: String, block: Binding<LabelLayout.CarrierLayout.TextBlock>, scale: CGFloat) -> some View {
        if let img = textImages[key] {
            previewTextImage(img, block: block, scale: scale)
        }
    }

    @ViewBuilder private func optionalTextOverlay(_ key: String, block: Binding<LabelLayout.CarrierLayout.TextBlock>, scale: CGFloat) -> some View {
        textOverlay(key, block: block, scale: scale)
    }

    @ViewBuilder private func centerTextOverlay(scale: CGFloat) -> some View {
        if let img = textImages["center_text"] {
            let block = Binding(get: { layout.text.centerText?.asTextBlock ?? .defaultCenterText }, set: { newValue in
                layout.text.centerText = .init(scale: newValue.scale, yPosition: newValue.startY, xPosition: newValue.startX, width: newValue.width, height: newValue.height, fontSize: newValue.fontSize, lineSpacing: newValue.lineSpacing, charSpacing: newValue.charSpacing, horizontalSquish: newValue.horizontalSquish, text: newValue.text, whitespace: newValue.whitespace, xOffset: newValue.xOffset, yOffset: newValue.yOffset)
            })
            previewTextImage(img, block: block, scale: scale)
        }
    }

    @ViewBuilder private func topNumberOverlay(scale: CGFloat) -> some View {
        if let img = textImages["top_number"] {
            let block = Binding(get: { layout.text.topNumber?.asTextBlock ?? .defaultTopNumber }, set: { newValue in
                layout.text.topNumber = .init(yPosition: newValue.startY, xPosition: newValue.startX, width: newValue.width, height: newValue.height, fontSize: newValue.fontSize, scale: newValue.scale, lineSpacing: newValue.lineSpacing, charSpacing: newValue.charSpacing, horizontalSquish: newValue.horizontalSquish, text: newValue.text, whitespace: newValue.whitespace, xOffset: newValue.xOffset, yOffset: newValue.yOffset)
            })
            previewTextImage(img, block: block, scale: scale)
        }
    }

    @ViewBuilder private func previewTextImage(_ image: NSImage, block: Binding<LabelLayout.CarrierLayout.TextBlock>, scale: CGFloat) -> some View {
        let x = CGFloat(block.wrappedValue.startX + (block.wrappedValue.xOffset ?? 0))
        let y = CGFloat(block.wrappedValue.startY + (block.wrappedValue.yOffset ?? 0))
        let width = CGFloat(block.wrappedValue.width ?? Int(image.size.width))
        let height = CGFloat(block.wrappedValue.height ?? Int(image.size.height))
        let whitespace = CGFloat(block.wrappedValue.whitespace ?? 0)
        Image(nsImage: image)
            .resizable()
            .frame(width: max(1, width - whitespace * 2) * scale, height: max(1, height - whitespace * 2) * scale)
            .padding(whitespace * scale)
            .offset(x: x * scale, y: y * scale)
            .contentShape(Rectangle())
            .gesture(DragGesture().onEnded { value in
                block.wrappedValue.startX += Int(round(value.translation.width / max(scale, 0.01)))
                block.wrappedValue.startY += Int(round(value.translation.height / max(scale, 0.01)))
            })
    }

    @ViewBuilder private func previewGuideFrames(scale: CGFloat, maxicodeWidth: CGFloat, maxicodeHeight: CGFloat, maxicodeY: CGFloat) -> some View {
        if let mask = layout.templateMask, mask.enabled {
            PreviewGuideFrame(label: "White Sq", x: CGFloat(mask.xPosition), y: CGFloat(mask.yPosition), width: CGFloat(mask.width) * CGFloat(mask.scale ?? 1), height: CGFloat(mask.height) * CGFloat(mask.scale ?? 1), displayScale: scale, color: .gray)
        }
        PreviewGuideFrame(label: "Maxi", x: CGFloat(layout.maxicode.xOffset), y: maxicodeY, width: maxicodeWidth, height: maxicodeHeight, displayScale: scale, color: .purple)
        PreviewGuideFrame(label: "Barcode", x: CGFloat(layout.barcode.xPosition), y: CGFloat(layout.barcode.yPosition), width: CGFloat(layout.barcode.width) * CGFloat(layout.barcode.scale ?? 1), height: CGFloat(layout.barcode.height) * CGFloat(layout.barcode.scale ?? 1), displayScale: scale, color: .blue)
        PreviewGuideFrame(label: "ZIP", x: CGFloat(layout.zipBarcode.xPosition), y: CGFloat(layout.zipBarcode.yPosition), width: CGFloat(layout.zipBarcode.width) * CGFloat(layout.zipBarcode.scale ?? 1), height: CGFloat(layout.zipBarcode.height) * CGFloat(layout.zipBarcode.scale ?? 1), displayScale: scale, color: .orange)
        guideForText("Sender", key: "sender", block: layout.text.sender, scale: scale)
        guideForText("Receiver", key: "receiver", block: layout.text.receiver, scale: scale)
        if let r2 = layout.text.receiver2nd { guideForText("Receiver 2", key: "receiver_2nd", block: r2, scale: scale) }
        guideForText("Tracking", key: "tracking", block: layout.text.tracking, scale: scale)
        if let ct = layout.text.centerText { guideForText("Center", key: "center_text", block: ct.asTextBlock, scale: scale) }
        if let tn = layout.text.topNumber { guideForText("Top #", key: "top_number", block: tn.asTextBlock, scale: scale) }
    }

    @ViewBuilder private func guideForText(_ label: String, key: String, block: LabelLayout.CarrierLayout.TextBlock, scale: CGFloat) -> some View {
        if let img = textImages[key] {
            PreviewGuideFrame(label: label, x: CGFloat(block.startX + (block.xOffset ?? 0)), y: CGFloat(block.startY + (block.yOffset ?? 0)), width: CGFloat(block.width ?? Int(img.size.width)), height: CGFloat(block.height ?? Int(img.size.height)), displayScale: scale, color: .green)
        }
    }

    private func debouncedRender() {
        renderTask?.cancel()
        renderTask = Task { try? await Task.sleep(for: .milliseconds(100)); guard !Task.isCancelled else { return }; renderAllText() }
    }

    private func renderAllText() {
        guard let info = ftidInfo else { return }
        let text = layout.text
        let t = renderer

        func renderBlock(_ key: String, block: LabelLayout.CarrierLayout.TextBlock, lines: [String], fontURL: URL?, uppercase: Bool = true) {
            let overrideLines = block.text?.isEmpty == false ? [block.text ?? ""] : lines
            textImages[key] = t.render(lines: overrideLines, fontURL: fontURL, baseFontSize: CGFloat(block.fontSize), scale: CGFloat(block.scale), lineSpacing: CGFloat(block.lineSpacing), charSpacing: CGFloat(block.charSpacing), uppercase: uppercase, horizontalSquish: CGFloat(block.horizontalSquish ?? 1.0))
        }

        renderBlock("sender", block: text.sender, lines: [info.sender, info.senderAddress, info.sender2ndLine], fontURL: text.fromLabel == nil ? t.fontMainURL : t.fontArialURL, uppercase: text.fromLabel == nil)
        renderBlock("receiver", block: text.receiver, lines: [info.receiver, info.receiverAddress], fontURL: text.fromLabel == nil ? t.fontMainURL : t.fontArialURL, uppercase: text.fromLabel == nil)
        if let r2 = text.receiver2nd { renderBlock("receiver_2nd", block: r2, lines: [info.receiver2ndLine], fontURL: t.fontBoldURL) }
        renderBlock("tracking", block: text.tracking, lines: [formatTracking(info.trackingNumber)], fontURL: text.fromLabel == nil ? t.fontMainURL : t.fontArialURL)
        if let fromLabel = text.fromLabel { renderBlock("from_label", block: fromLabel, lines: ["FROM:"], fontURL: t.fontArialURL, uppercase: false) }
        if let shipToLabel = text.shipToLabel { renderBlock("ship_to_label", block: shipToLabel, lines: ["SHIP TO:"], fontURL: t.fontArialURL, uppercase: false) }
        if let trackingPrefix = text.trackingPrefix { renderBlock("tracking_prefix", block: trackingPrefix, lines: ["9622  0137  0  (000  000  0000)  0  00  \(formatTracking(info.trackingNumber))"], fontURL: t.fontBoldURL) }
        if let receiverZip = text.receiverZip, let zip = info.receiverZip.split(separator: " ").last { renderBlock("receiver_zip_text", block: receiverZip, lines: [String(zip)], fontURL: t.fontBoldURL) }

        if let center = text.centerText {
            let parts = info.receiver2ndLine.split(separator: " ")
            let generated: String
            if parts.count >= 2 { generated = "\(parts[parts.count - 2]) \(String(parts[parts.count - 1].prefix(2)))5 7-67" } else { generated = "CENTER TEXT" }
            renderBlock("center_text", block: center.asTextBlock, lines: [generated], fontURL: t.fontBoldURL)
        }
        if let top = text.topNumber {
            renderBlock("top_number", block: top.asTextBlock, lines: [top.text ?? "1"], fontURL: t.fontBoldURL)
        }
    }

    private func formatTracking(_ tracking: String) -> String {
        tracking.uppercased().replacingOccurrences(of: " ", with: "")
    }
}

extension NSImage {
    var pixelSize: CGSize {
        if let rep = representations.first { return CGSize(width: rep.pixelsWide, height: rep.pixelsHigh) }
        return size
    }

    func previewRasterContentImage() -> NSImage {
        guard let cg = cgImage(forProposedRect: nil, context: nil, hints: nil) else { return self }
        let width = cg.width
        let height = cg.height
        guard let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return self }
        ctx.draw(cg, in: CGRect(x: 0, y: 0, width: width, height: height))
        guard let out = ctx.makeImage() else { return self }
        return NSImage(cgImage: out, size: NSSize(width: width, height: height))
    }

    func previewTextContentImage(alphaThreshold: UInt8 = 8) -> NSImage {
        guard let cg = cgImage(forProposedRect: nil, context: nil, hints: nil) else { return self }
        let width = cg.width
        let height = cg.height
        guard width > 0, height > 0 else { return self }

        let bytesPerPixel = 4
        let bytesPerRow = width * bytesPerPixel
        var pixels = [UInt8](repeating: 0, count: height * bytesPerRow)
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let bitmapInfo = CGImageAlphaInfo.premultipliedLast.rawValue

        let didDraw = pixels.withUnsafeMutableBytes { pointer -> Bool in
            guard let ctx = CGContext(data: pointer.baseAddress, width: width, height: height, bitsPerComponent: 8, bytesPerRow: bytesPerRow, space: colorSpace, bitmapInfo: bitmapInfo) else { return false }
            ctx.draw(cg, in: CGRect(x: 0, y: 0, width: width, height: height))
            return true
        }
        guard didDraw else { return self }

        var minX = width
        var minY = height
        var maxX = -1
        var maxY = -1

        for y in 0..<height {
            for x in 0..<width {
                let offset = y * bytesPerRow + x * bytesPerPixel
                let alpha = pixels[offset + 3]
                guard alpha > alphaThreshold else { continue }
                minX = min(minX, x)
                minY = min(minY, y)
                maxX = max(maxX, x)
                maxY = max(maxY, y)
            }
        }

        guard maxX >= minX, maxY >= minY else {
            return NSImage(size: NSSize(width: 1, height: 1))
        }

        let cropRect = CGRect(x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1)
        guard let cropped = cg.cropping(to: cropRect) else { return self }
        return NSImage(cgImage: cropped, size: NSSize(width: cropped.width, height: cropped.height))
    }
}
