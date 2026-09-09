# System Architecture

## High-Level Overview

Container Damage Detection is a three-layer desktop application:

1. **Core Layer** – Pure Python inference pipeline (no Qt dependencies)
2. **GUI Layer** – PyQt6 user interface (only talks to core pipeline)
3. **Entry Point** – Minimal launcher (`main.py`)

The heart of the system is a **two-stage YOLO detection pipeline** that first locates containers in a frame, then detects damage on each container by cropping and processing container-sized regions.

## Two-Stage Detection Pipeline

```
Input Frame (BGR)
      │
      ├─► Stage 1: Container Detection (Full Frame)
      │   ├─ Run container YOLO model
      │   ├─ Output: container boxes (x1,y1,x2,y2)
      │   └─ Filter: min_container_side=32 (drop tiny boxes)
      │
      ├─► [If no containers found → return empty detections]
      │
      ├─► Stage 2: Damage Detection (Per-Container Crop)
      │   ├─ For each container:
      │   │  ├─ Expand box by padding_ratio=0.08 (edges/corners safety margin)
      │   │  ├─ Clamp to frame bounds
      │   │  └─ Crop that region from frame
      │   │
      │   ├─ Batch all crops → single damage model predict() call
      │   │  (perf: fewer model invocations, effective higher resolution)
      │   │
      │   ├─ Map damage boxes back to full-frame coordinates
      │   │  (fx = damage_x + crop_offset_x, etc.)
      │   │
      │   └─ Output: damage boxes, tagged with parent container_idx
      │
      └─► Combined Output: List[Detection]
          ├─ Both container and damage detections
          ├─ Each tagged: kind="container" or kind="damage"
          └─ Damage includes container_idx (per-frame index only, not stable across frames)
```

## Data Flow: Static Image

```
User Action: "Mở ảnh..." (Open Image)
  │
  ├─► Load PNG/JPG with cv2.imread()
  │
  ├─► Call: pipeline.predict(frame_bgr)
  │   ├─ Two-stage inference (see above)
  │   └─ Annotator draws boxes/labels on copy of frame
  │
  ├─► Emit: frame_ready(annotated_frame, detections)
  │
  ├─► Update: display_label QLabel shows annotated_frame pixmap
  │
  └─► Store: last_static_frame for re-inference on parameter changes
      │
      └─ User adjusts: conf, iou, imgsz, padding, display toggles
         │
         ├─► Call: _rerun_static_if_any()
         │   └─ Re-run pipeline.predict() with new params
         │
         └─► Update display instantly (feedback within ~500ms)
```

## Data Flow: Video File or Camera

```
User Action: "Mở video..." or "Mở Camera"
  │
  ├─► MainWindow spawns VideoWorker(QThread)
  │   │
  │   ├─► VideoWorker.run() loop:
  │   │   ├─ cv2.VideoCapture(path or camera_index)
  │   │   │
  │   │   ├─ For each frame:
  │   │   │  ├─ Read frame (BGR)
  │   │   │  ├─ Call: pipeline.predict(frame_bgr)
  │   │   │  ├─ Emit: frame_ready(raw_frame, annotated_frame, detections, fps)
  │   │   │  │
  │   │   │  └─ [If recording enabled]
  │   │   │     └─ Write annotated_frame to cv2.VideoWriter
  │   │   │
  │   │   └─ When done: emit finished_signal()
  │   │
  │   └─► (Runs on separate thread; UI stays responsive)
  │
  ├─► MainWindow receives frame_ready() signal:
  │   ├─ Update display_label with annotated_frame
  │   │
  │   ├─ Filter new damage: alert_tracker.filter_new(detections)
  │   │  └─ Only returns damage detections that haven't alerted in last 5 seconds
  │   │
  │   ├─ For each new damage detection:
  │   │  ├─ Call: build_damage_snapshot(frame, detection, pad_ratio=0.6)
  │   │  ├─ Create: DamagePopup(QDialog) showing close-up crop
  │   │  └─ Show non-modal popup
  │   │
  │   └─ Update: FPS counter on status bar
  │
  └─► On stop or end of source:
      └─ alert_tracker.reset() (clear memory for next session)
```

## GPU / Device Selection

```
Application Startup
  │
  ├─► Call: gpu_check.list_working_devices()
  │   │
  │   ├─ Check: torch.cuda.is_available()
  │   │  (driver handshake only; not guaranteed to work)
  │   │
  │   ├─ For each cuda:N device:
  │   │  ├─ Run tiny test op (e.g., torch.ones(1).to(device))
  │   │  ├─ If succeeds: include in list
  │   │  └─ If fails: skip (unsupported compute capability, old driver, etc.)
  │   │
  │   └─ Always include "cpu" as fallback
  │
  └─► Return: (devices=['cuda:0', 'cuda:1', 'cpu'], warnings_dict)
      │
      └─ MainWindow device dropdown auto-populates
         Default selection: first CUDA device if available, else CPU
```

At inference time, `ContainerDamageDetector` runs models on the selected device. If a model fails on GPU, an exception is raised (current behavior); production code might want to retry on CPU.

## Alert Deduplication

For video, the same physical damage is re-detected every frame it's visible. Without deduplication, that's one alert popup per frame (unacceptable user experience).

```
Detection Loop (per frame)
  │
  ├─► pipeline.predict(frame) → detections (mix of container + damage)
  │
  ├─► alert_tracker.filter_new(detections) → only new damage
  │   │
  │   ├─ For each damage detection:
  │   │  ├─ Search _seen: find any recent damage with:
  │   │  │  ├─ Same label
  │   │  │  └─ IoU >= iou_threshold (0.3)
  │   │  │
  │   │  ├─ If found & within cooldown_seconds (5.0):
  │   │  │  ├─ Update: last_seen timestamp
  │   │  │  └─ Skip: don't include in new_alerts
  │   │  │
  │   │  └─ If not found | expired cooldown:
  │   │     ├─ Add to _seen
  │   │     └─ Include in new_alerts
  │   │
  │   └─ Return: new_alerts (only genuinely new damage)
  │
  └─► For each new damage:
      └─ Show DamagePopup
```

**Key insight**: Matching is by (label, box overlap), not by `container_idx`. The `container_idx` is only a per-frame ordering; it's not stable across frames (a container exiting and re-entering the view would get a different index). The alert tracker uses IoU to match the same physical damage across frames.

## Module Responsibility Matrix

| Module | Responsibility | Dependencies |
|---|---|---|
| `detector.py` | Load YOLO models, run two-stage inference | ultralytics, torch, numpy, cv2 |
| `pipeline.py` | Facade: combine detector + annotator, expose predict() | core.detector, core.annotator |
| `annotator.py` | Draw boxes, labels, confidence on frame | cv2, numpy |
| `alert_tracker.py` | Track recently-alerted damage, dedup video detections | core.detection, core.geometry |
| `detection.py` | Detection dataclass | – |
| `stage_config.py` | StageConfig dataclass | – |
| `geometry.py` | expand_box(), iou() helpers | – |
| `damage_snapshot.py` | Crop around damage with context, draw box overlay | cv2, numpy |
| `model_registry.py` | Find weight files, heuristic model selection | pathlib |
| `gpu_check.py` | Validate CUDA device availability | torch |
| `paths.py` | Resolve app_root(), user_data_dir(), is_frozen() | sys, pathlib |
| `main_window.py` | Full UI, event handling, lifecycle | PyQt6, cv2, core.pipeline, core.alert_tracker |
| `video_worker.py` | Off-UI-thread video/camera I/O and inference | PyQt6, cv2, core.pipeline |
| `damage_popup.py` | Non-modal alert dialog for damage close-up | PyQt6 |
| `main.py` | Entry point | PyQt6, gui.main_window |

## Configuration Points

All user-adjustable parameters live in the GUI and flow through `pipeline.set_*()` methods:

```
User adjusts in GUI:
  │
  ├─► Container Conf / IoU / ImgSize
  │   └─► pipeline.set_container_params(conf=X, iou=Y, imgsz=Z)
  │       └─ Updates ContainerDamageDetector.container_cfg
  │
  ├─► Damage Conf / IoU / ImgSize
  │   └─► pipeline.set_damage_params(conf=X, iou=Y, imgsz=Z)
  │       └─ Updates ContainerDamageDetector.damage_cfg
  │
  ├─► Padding Ratio
  │   └─► pipeline.set_padding_ratio(X)
  │       └─ Updates ContainerDamageDetector.padding_ratio
  │
  ├─► Display Toggles (show_labels, show_conf, show_container_box)
  │   └─► pipeline.set_display_params(...)
  │       └─ Updates DetectionAnnotator display rules
  │
  └─► Alert Cooldown / IoU Threshold
      └─► Directly modify: MainWindow.alert_tracker.cooldown_seconds / iou_threshold
          (or expose pipeline setters for consistency)
```

For static images, parameter changes immediately re-run inference via `_rerun_static_if_any()` so the user sees the effect on the current frame.

## Threading Model

- **Main thread**: UI, event loop
- **VideoWorker thread**: Video/camera frame reading + inference (spawned on demand, joined on stop)
- **Qt Signal/Slot**: Cross-thread communication (no locks, no polling)

Example:
```python
# Main thread
self.worker = VideoWorker(source, pipeline)
self.worker.frame_ready.connect(self._on_frame)  # signal → slot
self.worker.start()  # launches thread

# VideoWorker thread
for frame in frames:
    detections, annotated = pipeline.predict(frame)
    self.frame_ready.emit(annotated, detections)  # signal back to main
```

## Packaged Deployment

- **Build**: `pyinstaller app.spec` → creates `dist/ContainerDamageDetection/` with bundled torch (CUDA), weights, assets
- **Install**: `ISCC.exe installer.iss` → Windows installer, per-user install to `%LOCALAPPDATA%\Programs\ContainerDamageDetection`
- **Compression gotcha**: Uses zip (not lzma2) to avoid Windows Defender locking files during long compression window
- **Runtime**: Exe auto-detects GPU at startup via `gpu_check.py`, falls back to CPU if needed

See `docs/deployment-guide.md` for detailed build steps.
