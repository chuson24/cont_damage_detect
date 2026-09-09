# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PyQt6 desktop GUI for demoing/testing a two-stage YOLO (ultralytics) pipeline that detects shipping containers and then classifies damage on them, from a static image, a video file, or a live camera. Ships to end users as a Windows installer built via PyInstaller + Inno Setup.

## Running

```
python main.py
```

No `requirements.txt`/`pyproject.toml` is checked in. Runtime deps (import them to infer versions if needed): `PyQt6`, `opencv-python` (`cv2`), `torch`, `ultralytics`, `numpy`.

There are no automated tests, lint config, or CI in this repo. Verify changes by running the app and exercising the affected flow (open image/video/camera) manually.

## Build (Windows packaging)

```
pyinstaller app.spec --distpath <dist> --workpath <work> --noconfirm
ISCC.exe installer.iss /DDistDir="<dist>\ContainerDamageDetection" /DOutputDir="<path>"
```

`app.spec` bundles a CUDA-enabled torch build plus `weights/` so the packaged app auto-detects GPU vs CPU at runtime (see `core/gpu_check.py`). The Inno Setup script installs per-user (no admin) and uses plain `zip` compression, not solid lzma2 — a prior lzma2 build silently dropped files (including model weights) under Defender's real-time scan; keep it that way unless the cause is fixed differently.

## Architecture

Three layers, strictly separated:

- **`core/`** — pure detection/pipeline logic, no Qt, no drawing side effects mixed with inference.
- **`gui/`** — PyQt6 UI, talks only to `core.pipeline.ContainerDamagePipeline`. Never put YOLO/OpenCV inference logic here.
- **`main.py`** — entry point only.

### Two-stage detection (`core/detector.py`)

`ContainerDamageDetector` runs container detection on the full frame first, then crops each container box (expanded by `padding_ratio`, clamped to frame bounds) and runs the damage model only on those crops, batched into a single `predict()` call. Damage boxes are mapped back to full-frame coordinates. If no container is found, the damage model is never invoked. This is deliberate: cropping gives the damage model effectively higher resolution on the region that matters and is cheaper than scanning the whole frame.

`core/pipeline.py`'s `ContainerDamagePipeline` is the single facade the GUI is meant to use — it wraps a `ContainerDamageDetector` (inference) and a `DetectionAnnotator` (drawing) so callers never need to know there are two separate stages/models.

Key `core/` modules:
- `detection.py` — `Detection` dataclass (label, conf, box, cls_id, kind: "container"|"damage", container_idx).
- `geometry.py` — shared `iou()` and `expand_box()` (padding + clamping) helpers.
- `stage_config.py` — `StageConfig` dataclass (conf/iou/imgsz) per stage.
- `annotator.py` — draws `Detection`s onto a frame; kept separate from the detector so inference never touches drawing.
- `alert_tracker.py` — `DamageAlertTracker` dedups damage across video frames (matched by label + IoU, not `container_idx`, since that index is only a per-frame ordering) so the same physical damage doesn't retrigger a popup every frame; alerts re-fire after `cooldown_seconds` of not being seen.
- `damage_snapshot.py` — builds a cropped, highlighted close-up image of one damage detection for the alert popup.
- `model_registry.py` — discovers `.pt` files under `weights/` and guesses which is the damage vs. container model by filename.
- `paths.py` — resolves `app_root()` (bundled read-only resources: `weights/`, `assets/`) vs `user_data_dir()` (writable per-user output dir) so paths work both running from source and frozen via PyInstaller (onedir/onefile).
- `gpu_check.py` — `torch.cuda.is_available()` only confirms driver/runtime handshake, not that a kernel actually runs; `list_working_devices()` smoke-tests each `cuda:N` with a real op and falls back to CPU for any that fail, so the app degrades gracefully instead of crashing mid-inference.

### GUI (`gui/`)

- `main_window.py` — `MainWindow` builds/wires the whole UI (model selection, per-stage conf/IoU/imgsz controls, display toggles, alert/cooldown config, camera index, results list) and owns the `ContainerDamagePipeline` and `VideoWorker` lifecycle. Config panels are made collapsible via `_make_collapsible()`. Changing any detection/display param live re-runs inference on the current static image (`_rerun_static_if_any`) so the effect is visible immediately.
- `video_worker.py` — `VideoWorker(QThread)` pulls frames from a video file or camera and runs `pipeline.predict()` per frame off the UI thread, emitting `frame_ready(raw_frame, annotated_frame, detections, fps)`.
- `damage_popup.py` — non-modal `DamagePopup` dialog showing a close-up of one newly-alerted damage detection.

### UI language

UI strings (labels, tooltips, status messages) are in Vietnamese — this is intentional for the target users; match that convention when adding UI text.

## Assets

- `weights/*.pt` — YOLO model weights (container detector, damage detector), bundled with the packaged app.
- `assets/` — demo media (sample output video/screenshot).
- `docs/` — end-user usage guide (PDF, Vietnamese).
