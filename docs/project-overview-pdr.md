# Container Damage Detection - Project Overview & PDR

## Product Definition

**Container Damage Detection** is a PyQt6 desktop application that demonstrates and tests a two-stage YOLO-based computer vision pipeline for detecting shipping containers and classifying damage on them from static images, video files, or live camera feeds.

### Target Users

- Vietnamese-speaking users (domestic/target market)
- Container inspection teams evaluating automated damage detection workflows
- Developers and engineers prototyping/testing detection performance

### Product Scope

This is a **demo and test tool**, not a production inspection system. Key limitations are intentional:

- Single-threaded video processing with optional GPU acceleration (CPU fallback always available)
- No persistent damage database or reporting system
- No multi-camera or enterprise deployment features
- Alert deduplication via 5-second cooldown window (prevents video spam, suitable for testing; not a compliance-grade record)
- Vietnamese UI only

### Core Capabilities

1. **Static image detection** – Load a PNG/JPG, run both stages, view annotated output
2. **Video file playback** – Process a pre-recorded video frame-by-frame; result saved as MP4
3. **Live camera** – Detect from webcam or USB camera; optional recording
4. **Real-time result adjustment** – Adjust model parameters (confidence, IoU, inference resolution, padding) and re-run detection on the current frame instantly
5. **GPU/CPU auto-detection** – Detect available CUDA devices and fall back to CPU if none found
6. **Packaged deployment** – PyInstaller bundle + Inno Setup installer for Windows end-users

### Key Technical Decisions

- **Two-stage pipeline**: Container detection on full frame, damage detection on per-container crops. This improves accuracy (damage is small relative to scene) and reduces latency (fewer pixels processed by damage model).
- **Batch crop processing**: All container crops from a frame are batched into one damage-model predict() call for throughput.
- **No tests/CI/lint config**: This is a prototype. Production use would require these.
- **Pure core layer**: `core/` has zero Qt/GUI dependency, enabling CLI reuse or headless batch processing if needed later.
- **Vietnamese UI by design**: Application is intended for Vietnamese-speaking users; all UI strings are in Vietnamese.

### Functional Requirements

| Requirement | Status | Notes |
|---|---|---|
| Load and display static images | Done | Supports PNG, JPG via OpenCV |
| Detect containers and damage | Done | YOLO ultralytics pipeline, two stages |
| Display detections annotated on frame | Done | Via DetectionAnnotator class |
| Adjust model parameters live | Done | GUI re-runs inference on current frame |
| Record output video | Done | MP4, fps auto-detected from source |
| Live camera input | Done | Via cv2.VideoCapture, index selectable in UI |
| GPU auto-detection and fallback | Done | Via gpu_check.py, always falls back to CPU |
| Alert on new damage | Done | DamageAlertTracker with 5-second cooldown |
| Package for Windows end-users | Done | PyInstaller + Inno Setup |

### Non-Functional Requirements

| Requirement | Status | Notes |
|---|---|---|
| Responsive UI | Done | Inference runs on separate thread (VideoWorker) |
| Reasonable latency for video | Done | Batch crop processing, GPU support |
| Works without GPU | Done | Tested fallback to CPU |
| No external API dependencies | Done | Self-contained (models bundled in installer) |
| Minimal installer size | Done | Uses zip compression (not lzma2) to avoid Windows lockfile issues |
| No setup.py/requirements.txt version pinning | Not done | See roadmap |

## Success Metrics

- Application launches and loads a demo image without errors
- Container and damage boxes appear on annotated output
- Parameter changes re-run inference and update display in <500ms
- Video processing completes and saves output
- Damage alert popup appears on first new damage detection, then not again for 5+ seconds
- Packaged .exe installs and runs on Windows without pre-installed Python

## Known Gaps / Roadmap

See `docs/project-roadmap.md` for next steps and recognized limitations.
