# Release notes

## Transparentor 1.1.0

Major AI and interface update following the earlier itch.io 1.0.1 release.

### Highlights

- Dedicated **Crop & Resize** editor card with exact pixel dimensions, percentage scaling, aspect-ratio locking, and four resampling choices
- Exact X/Y/width/height crop controls alongside the existing visual drag-to-crop tool
- Resize and crop operations participate in Edit Stack undo/redo and portable project persistence
- Completely redesigned modern dark interface with clearer AI-first workflow
- Redrawn left editor rail with a consistent modern geometric icon set
- Adaptive Fusion background removal combining BiRefNet structure with
  ISNet glow, particle, and detached-detail recovery
- Memory-safe sequential AI execution: the large BiRefNet session is released
  immediately after its mask is produced, before refinement or Fusion's second
  model begins
- Removed redundant automatic region-by-region model reruns that could leave
  large-model refinement stalled near completion
- Background-aware processing that separates saturated chroma screens from
  dark uniform artwork instead of applying screen cleanup to both
- Gradient-screen recognition and translucent chroma refinement for uneven,
  noisy, or bokeh-filled green/blue backgrounds, including screen-spill
  suppression and foreground-color reconstruction
- Restored fast dark-background alpha recovery for Lightweight and Fusion,
  preserving opaque interiors, glow, sparkles, and detached effects without
  launching extra regional model passes
- Fusion now uses its adaptive refinement automatically; BiRefNet remains the
  intentionally pure-mask single-model option
- Dedicated BiRefNet and ISNet modes remain available
- Stage-aware segmented AI progress with elapsed time and a locally learned ETA
- Chroma-AI hybrid matting and edge cleanup
- Batch image processing
- Live batch queue filmstrip with the active image displayed in the main canvas
- Multi-image drops in Edit now stay in Edit and create a sequential AI Queue
  filmstrip; Compose receives dropped layers only while Compose is active
- Layered Compose workspace with responsive cached previews, moving, scaling,
  rotation, flips, opacity, brightness/contrast/saturation, blur, drop shadows,
  visibility, duplication, and front-to-back arrangement
- PNG-to-GIF workflow with frame alignment and preview
- Sprite-sheet slicing and export
- Project save/load, undo/redo, crop, lasso protection, and clipboard support
- Self-contained portable `.tpr` projects with embedded AI masks, source assets,
  composition layers, and transforms
- Fusion Best Overall as the default background-removal mode
- Confirmed, progress-visible first-use model downloads
- Explicit app-exit shutdown for AI workers, downloads, batch work, and cached ONNX sessions
- In-app About, privacy, version, and diagnostic information
- WebP input plus lossless, transparency-preserving WebP export in the editor,
  batch processor, GIF-frame exporter, and sprite slicer
- Fixed ICO export to produce broadly compatible multi-resolution Windows
  icons with 16, 24, 32, 48, 64, 128, and 256 px frames
- Replaced the legacy low-resolution application icon with the new
  Transparentor artwork
- Replaced the circular `T` badge in the main header with the new application
  icon and bundled the header asset inside the portable EXE
- Added an explicit Windows application identity so source launches no longer
  inherit Python's taskbar grouping or Python icon

### Installation

Download `Transparentor.exe` and run it from any writable folder. No installer is required.

### Notes

- AI model weights download only after confirmation and can require substantial disk space.
- The executable is not currently code-signed, so Windows SmartScreen may display a warning.
- `Transparentor.exe` SHA-256:
  `B82F3DF93DD8AA086D6EDD6F5C32377431BAC91D6C440F778043C2EF795E700C`
- `Transparentor-1.1.0-windows-x64.zip` SHA-256:
  `2AECE077525EE4713BDEB72D42ACDC41ED99139C2CB0AB1AA16C6D3049236470`
