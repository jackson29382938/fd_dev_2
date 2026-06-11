import CoreGraphics

extension CGRect {
    init(x: Int, y: Int, width: Int, height: Int) {
        self.init(
            x: CGFloat(x),
            y: CGFloat(y),
            width: CGFloat(width),
            height: CGFloat(height)
        )
    }
}
