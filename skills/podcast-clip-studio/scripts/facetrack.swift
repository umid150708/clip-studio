// Face boxes over time using Apple's Vision framework (no downloads, no model files).
//   facetrack VIDEO OUT.json [fps=10]
// Output: [{"t": 1.2, "faces": [{"x":0.41,"y":0.20,"w":0.12,"h":0.21}, ...]}, ...]
// Boxes are normalised to the frame, origin top-left.
import Foundation
import AVFoundation
import Vision

let args = CommandLine.arguments
guard args.count >= 3 else {
    FileHandle.standardError.write("usage: facetrack VIDEO OUT.json [fps]\n".data(using: .utf8)!)
    exit(1)
}
let fps = args.count > 3 ? (Double(args[3]) ?? 10.0) : 10.0
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
let duration = CMTimeGetSeconds(asset.duration)
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.maximumSize = CGSize(width: 960, height: 540)
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter = .zero

var out: [[String: Any]] = []
var t = 0.0
while t < duration {
    let time = CMTime(seconds: t, preferredTimescale: 600)
    var faces: [[String: Double]] = []
    if let img = try? gen.copyCGImage(at: time, actualTime: nil) {
        let req = VNDetectFaceRectanglesRequest()
        let handler = VNImageRequestHandler(cgImage: img, options: [:])
        try? handler.perform([req])
        for f in req.results ?? [] {
            let b = f.boundingBox  // origin bottom-left, normalised
            faces.append(["x": Double(b.minX), "y": Double(1.0 - b.maxY), "w": Double(b.width), "h": Double(b.height)])
        }
    }
    out.append(["t": (t * 1000).rounded() / 1000, "faces": faces])
    t += 1.0 / fps
}
let data = try JSONSerialization.data(withJSONObject: out, options: [])
try data.write(to: URL(fileURLWithPath: args[2]))
print("\(out.count) samples, \(out.filter { !($0["faces"] as! [Any]).isEmpty }.count) with a face")
