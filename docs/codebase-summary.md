# Codebase Summary

## Directory Structure

```
cont_damage_detect/
├── core/                    # Pure detection pipeline (zero Qt/GUI dependency)
│   ├── __init__.py
│   ├── detector.py          # ContainerDamageDetector: two-stage YOLO inference
│   ├── pipeline.py          # ContainerDamagePipeline: facade for GUI/CLI
│   ├── detection.py         # Detection dataclass (label, conf, box, kind)
│   ├── stage_config.py      # StageConfig: inference params per stage
│   ├── annotator.py         # DetectionAnnotator: draw boxes/labels on frame
│   ├── alert_tracker.py     # DamageAlertTracker: dedup repeated detections
│   ├── damage_snapshot.py   # build_damage_snapshot(): crop + box context for popup
│   ├── geometry.py          # iou(), expand_box(): pure geometry helpers
│   ├── model_registry.py    # find_weight_files(), guess_weight_file()
│   ├── gpu_check.py         # list_working_devices(): validate CUDA capability
│   └── paths.py             # app_root(), user_data_dir(), is_frozen()
├── gui/                     # PyQt6 UI (only talks to core.pipeline)
│   ├── __init__.py
│   ├── main_window.py       # MainWindow: ~600 lines, full UI + event wiring
│   ├── video_worker.py      # VideoWorker: QThread for off-UI-thread inference
│   └── damage_popup.py      # DamagePopup: non-modal alert dialog showing damage crop
├── main.py                  # Entry point: QApplication + MainWindow launch
├── weights/                 # YOLO model files (bundled in packaged app)
│   ├── container.pt         # Stage 1: detect containers
│   └── damage.pt            # Stage 2: detect damage on container crops
├── assets/                  # Demo media
│   ├── output.mp4
│   └── result_demo_video.png
├── app.spec                 # PyInstaller config
├── installer.iss            # Inno Setup config
└── docs/
    └── HuongDanSuDung_ContainerDamageDetection.pdf  # Vietnamese end-user guide
```

## Layer Responsibilities

### 1. Core Layer (`core/`)

Pure Python inference logic with **zero Qt/GUI dependencies**. All business logic lives here; can be reused in CLI, batch processing, or headless scripts.

#### Key Classes

**`DetectorDamageDetector`** (`detector.py`)
- Loads two YOLO models (container + damage)
- Runs two-stage inference: detect containers on full frame, then for each container crop, detect damage on the crop
- Expands container boxes by `padding_ratio=0.08` before cropping to avoid cutting damage at edges
- Filters out tiny containers (`min_container_side=32`)
- Batch-processes all crops from a frame in a single damage-model predict() call
- Returns flat `List[Detection]` with both stages mixed, each tagged `kind: "container"|"damage"`

**`ContainerDamagePipeline`** (`pipeline.py`)
- Single facade class for GUI/CLI/batch code
- Wraps `ContainerDamageDetector` + `DetectionAnnotator`
- Exposes: `predict(frame_bgr) -> (detections, annotated_frame)`
- Provides setters for all tunable parameters: `set_container_params()`, `set_damage_params()`, `set_padding_ratio()`, `set_display_params()`
- All parameter defaults stored in `StageConfig` dataclass (conf=0.25, iou=0.45, imgsz=640)

**`DamageAlertTracker`** (`alert_tracker.py`)
- For video, the same physical damage is re-detected every frame; without dedup that's one popup per frame
- Tracks recently-alerted damage by (label, box IoU), not by `container_idx` (which is only per-frame)
- 5-second cooldown window; same damage re-triggers after cooldown expires
- `filter_new(detections) -> List[Detection]`: returns only genuinely-new damage
- `reset()`: clears state when a new image/video/camera session starts

#### Supporting Classes

- **`Detection`** (`detection.py`): Dataclass holding one detection result (label, confidence, box, class_id, kind, container_idx)
- **`StageConfig`** (`stage_config.py`): Dataclass for per-stage inference params (conf, iou, imgsz)
- **`DetectionAnnotator`** (`annotator.py`): Draws boxes, labels, confidence on a frame; respects display toggles
- **`build_damage_snapshot()`** (`damage_snapshot.py`): Crops around a damage box with generous padding and draws red box overlay for alert popup
- **`expand_box()`**, **`iou()`** (`geometry.py`): Pure geometry helpers
- **`find_weight_files()`**, **`guess_weight_file()`** (`model_registry.py`): Glob weight files and heuristically pick container vs damage model
- **`list_working_devices()`** (`gpu_check.py`): Validates CUDA capability via actual test ops (not just driver check)
- **`app_root()`**, **`user_data_dir()`**, **`is_frozen()`** (`paths.py`): Handle bundled vs editable install, PyInstaller `_MEIPASS`, Windows user data directory

### 2. GUI Layer (`gui/`)

PyQt6 UI that **only** talks to `core.pipeline.ContainerDamagePipeline`. No direct YOLO/OpenCV inference logic.

#### Classes

**`MainWindow`** (`main_window.py` ~600 lines)
- Full UI: left panel (image/video display + playback controls), right panel (collapsible config groups)
- Playback controls: open image/video/camera, stop, save, record
- Config groups: model selection w/ browse buttons, container/damage stage params, display toggles, alert settings, camera index
- `_make_collapsible()` helper turns QGroupBox into a collapsible section
- Owns `ContainerDamagePipeline`, `VideoWorker`, `DamageAlertTracker`, video recording (cv2.VideoWriter, MP4)
- Any parameter change re-runs inference on the current static image so effect is visible instantly (`_rerun_static_if_any`)
- Model dropdowns auto-populate from `weights/` and heuristically pick damage model if filename contains "damage"

**`VideoWorker`** (`video_worker.py`)
- Inherits `QThread`
- Opens video file or camera via cv2.VideoCapture
- Loops reading frames + calling `pipeline.predict()` off UI thread
- Emits `frame_ready()`, `info_ready()`, `finished_signal()`, `error_signal()` signals for lifecycle
- Falls back to 20fps if source reports unreliable FPS

**`DamagePopup`** (`damage_popup.py`)
- Non-modal QDialog showing one damage detection close-up (from `build_damage_snapshot()`)
- Displays label, confidence, container_idx, box coordinates
- Auto-scales displayed image between 200–480 px

#### UI Language

All UI strings (labels, buttons, tooltips, error/status messages) are **Vietnamese by design**. This is intentional and matches the product scope. Examples:
- "Mở ảnh..." (Open image...)
- "Chưa có ảnh/video" (No image/video yet)
- "Nhấn để thu gọn / mở rộng mục này" (Click to collapse/expand this section)

### 3. Entry Point

**`main.py`**
- Minimal: just `QApplication` + `MainWindow` launch
- All UI logic is in `MainWindow`; all inference logic is in `core.pipeline`

## Data Flow

1. **Static Image**:
   - User clicks "Mở ảnh..." → file dialog → load PNG/JPG with cv2.imread()
   - `pipeline.predict(frame_bgr)` → returns (detections, annotated_frame)
   - Annotated frame displayed on screen
   - Parameter changes trigger `_rerun_static_if_any()` to re-predict instantly

2. **Video File / Camera**:
   - User clicks "Mở video..." or "Mở Camera" → file dialog or camera index selected
   - MainWindow spawns `VideoWorker` thread
   - VideoWorker loop: read frame → `pipeline.predict()` → emit `frame_ready(raw, annotated, detections, fps)`
   - MainWindow receives signal, updates display, filters detections via `alert_tracker.filter_new()`
   - For any new damage: `DamagePopup` dialog spawned
   - Optionally record: each frame written to cv2.VideoWriter

3. **GPU Detection**:
   - At startup (during `_populate_models()`), call `gpu_check.list_working_devices()`
   - Returns (available_devices, warnings)
   - Populate camera/device dropdown, default to first working device

## Design Patterns

- **Facade**: `ContainerDamagePipeline` abstracts two-stage inference + annotation so GUI doesn't need to know about stages
- **Pure core layer**: No Qt imports in `core/`; can be tested/reused independently
- **Dataclasses**: `Detection`, `StageConfig`, `_SeenDamage` use @dataclass for clean data modeling
- **Thread per I/O**: `VideoWorker` runs on QThread to keep UI responsive
- **Signal/slot pattern**: All cross-thread communication uses Qt signals, not polling or locks
- **Vietnamese strings inline**: No i18n system; strings embedded in Python code as design choice

## Dependencies

- **PyQt6**: GUI framework
- **OpenCV (cv2)**: Image/video I/O, frame manipulation
- **torch**: YOLO backbone (CUDA or CPU)
- **ultralytics**: YOLO model loading and inference
- **numpy**: Array operations (implicitly via torch/cv2)

No requirements.txt or pyproject.toml exists; versions are pinned only in PyInstaller bundle via wheel URLs.
