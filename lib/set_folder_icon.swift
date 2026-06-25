// set_folder_icon.swift — setzt ein farbgetöntes SF-Symbol als Ordner-Icon.
// Usage: swift set_folder_icon.swift <path> <sfsymbol> <r> <g> <b>   (r/g/b = 0..255)
import AppKit
import Foundation

let a = CommandLine.arguments
guard a.count == 6, let r = Double(a[3]), let g = Double(a[4]), let b = Double(a[5]) else {
    fputs("usage: set_folder_icon.swift <path> <symbol> <r> <g> <b>\n", stderr); exit(2)
}
let path = a[1], symbolName = a[2]
let color = NSColor(srgbRed: r/255, green: g/255, blue: b/255, alpha: 1.0)

let cfg = NSImage.SymbolConfiguration(pointSize: 360, weight: .semibold)
    .applying(NSImage.SymbolConfiguration(paletteColors: [color]))
guard let base = NSImage(systemSymbolName: symbolName, accessibilityDescription: nil),
      let glyph = base.withSymbolConfiguration(cfg) else {
    fputs("SF Symbol '\(symbolName)' nicht gefunden\n", stderr); exit(1)
}

let size = NSSize(width: 512, height: 512)
let canvas = NSImage(size: size)
canvas.lockFocus()
let gs = glyph.size
let scale = min(360 / gs.width, 360 / gs.height)
let w = gs.width * scale, h = gs.height * scale
glyph.draw(in: NSRect(x: (512-w)/2, y: (512-h)/2, width: w, height: h),
           from: .zero, operation: .sourceOver, fraction: 1.0)
canvas.unlockFocus()

if NSWorkspace.shared.setIcon(canvas, forFile: path, options: []) {
    Thread.sleep(forTimeInterval: 1.0)
    print("icon set: \(symbolName) on \(path)")
} else {
    fputs("setIcon fehlgeschlagen\n", stderr); exit(1)
}
