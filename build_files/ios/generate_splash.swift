// SPDX-FileCopyrightText: 2026 Shlok Bhakta
//
// SPDX-License-Identifier: GPL-2.0-or-later

import AppKit
import Foundation

let size = NSSize(width: 1000, height: 500)
guard let bitmap = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: Int(size.width),
    pixelsHigh: Int(size.height),
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
) else {
    fatalError("Cannot create splash bitmap")
}

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)

let bounds = NSRect(origin: .zero, size: size)
let background = NSGradient(
    starting: NSColor(srgbRed: 0.05, green: 0.13, blue: 0.32, alpha: 1),
    ending: NSColor(srgbRed: 0.11, green: 0.35, blue: 0.73, alpha: 1)
)!
background.draw(in: bounds, angle: 25)

// A simple isometric cube, shared in shape with the iOS icon.
let cube = NSBezierPath()
cube.lineWidth = 10
cube.lineCapStyle = .round
cube.lineJoinStyle = .round
cube.move(to: NSPoint(x: 500, y: 415))
cube.line(to: NSPoint(x: 604, y: 355))
cube.line(to: NSPoint(x: 604, y: 235))
cube.line(to: NSPoint(x: 500, y: 175))
cube.line(to: NSPoint(x: 396, y: 235))
cube.line(to: NSPoint(x: 396, y: 355))
cube.close()
cube.move(to: NSPoint(x: 396, y: 355))
cube.line(to: NSPoint(x: 500, y: 295))
cube.line(to: NSPoint(x: 604, y: 355))
cube.move(to: NSPoint(x: 500, y: 295))
cube.line(to: NSPoint(x: 500, y: 175))
NSColor.white.setStroke()
cube.stroke()

let title = "3D Modelling Thingy" as NSString
let font = NSFont.systemFont(ofSize: 45, weight: .semibold)
let attributes: [NSAttributedString.Key: Any] = [
    .font: font,
    .foregroundColor: NSColor.white,
]
let titleSize = title.size(withAttributes: attributes)
title.draw(
    at: NSPoint(x: (size.width - titleSize.width) / 2, y: 73),
    withAttributes: attributes
)

NSGraphicsContext.current?.flushGraphics()
NSGraphicsContext.restoreGraphicsState()

guard CommandLine.arguments.count == 2,
      let png = bitmap.representation(using: .png, properties: [:]) else {
    fatalError("Usage: swift generate_splash.swift path/to/splash.png")
}
try png.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
