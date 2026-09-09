# Code Standards & Conventions

## Layer Separation

The codebase is organized into **three layers**, each with strict boundaries:

### 1. Core Layer (`core/`)

**Rule**: Zero Qt/GUI imports. Pure Python only.

- Contains all inference, geometry, alert logic
- Testable in isolation without PyQt6 installation
- Can be reused in CLI, batch processing, or headless scripts
- Examples:
  - `core/detector.py` imports only `ultralytics`, `numpy`, `cv2`
  - `core/pipeline.py` imports only from `core/` modules
  - `core/alert_tracker.py` has no external I/O; state is in-memory

### 2. GUI Layer (`gui/`)

**Rule**: Only talks to `core.pipeline.ContainerDamagePipeline`.

- Do not import from individual `core/` modules (e.g., no `from core.detector import`)
- All inference logic must go through the pipeline facade
- Responsible for UI event wiring, threading, signal/slot connections
- Examples:
  - `gui/main_window.py` instantiates `ContainerDamagePipeline` and calls `pipeline.predict()`
  - `gui/video_worker.py` threads off inference via pipeline, emits signals back to main thread

### 3. Entry Point (`main.py`)

**Rule**: Only instantiates `QApplication` and `MainWindow`.

- Minimal; no business logic
- All initialization happens in `MainWindow.__init__()` or module-level `core/` initialization

## Data Models

Use **`@dataclass`** for all structured data:

- `Detection`: one detection result (label, conf, box, kind, container_idx)
- `StageConfig`: inference parameters per model (conf, iou, imgsz)
- `_SeenDamage`: internal to alert_tracker, tracks recently-alerted damage

**Why**: Immutable, type-safe, easy to inspect in debugger, minimal boilerplate.

Example:
```python
from dataclasses import dataclass

@dataclass
class Detection:
    label: str
    conf: float
    box: tuple  # (x1, y1, x2, y2)
    cls_id: int
    kind: str  # "container" or "damage"
    container_idx: Optional[int]
```

## Comments

**Style**: Only WHY comments, not WHAT comments.

- **Good**: `# Expand container box by padding so damage at edges isn't cut off by tight stage-1 box`
- **Bad**: `# Expand the box` (restates code)
- **Bad**: `# Calculate padding` (obvious from variable name)

**Use case**: Non-obvious tradeoffs, optimization rationales, gotchas from prior bugs.

Example (from detector.py):
```python
# Running the damage model on the container crop instead of the whole frame
# is both more accurate (damage is small relative to the full scene, so the
# crop gives the detector effectively higher resolution on the object that
# matters) and cheaper (the damage model looks at far fewer background
# pixels). All container crops from a frame are batched into a single
# damage-model predict() call for speed, which matters for video throughput.
```

## Vietnamese UI Strings

**All UI strings are in Vietnamese by design**. This is intentional, not technical debt.

- Buttons, labels, tooltips, status messages, error dialogs: all Vietnamese
- Embedded directly in Python code; no i18n system
- Examples from `gui/main_window.py`:
  - "Mở ảnh..." (Open image)
  - "Chưa có ảnh/video" (No image/video)
  - "Dừng" (Stop)
  - "Nhấn để thu gọn / mở rộng mục này" (Click to collapse/expand this section)
  - "Ghi video kết quả" (Record result video)

**Maintain this convention**: If UI changes, keep Vietnamese strings. Do not switch to English.

## Configuration Defaults

All inference parameter defaults are in `core/stage_config.py`:

```python
@dataclass
class StageConfig:
    conf: float = 0.25  # confidence threshold
    iou: float = 0.45   # IoU threshold for NMS
    imgsz: int = 640    # inference resolution
```

Other defaults scattered in `core/` initialization:

- `detector.py`: `padding_ratio=0.08`, `min_container_side=32`
- `alert_tracker.py`: `cooldown_seconds=5.0`, `iou_threshold=0.3`
- `damage_snapshot.py`: `pad_ratio=0.6`, `min_pad=24`
- `video_worker.py`: fallback FPS = 20.0 if source reports ≤1 or >240

**Update approach**: If changing defaults, edit the source file, not a config file. Document the change in commit message with WHY.

## Naming Conventions

- **Python modules & functions**: `snake_case`
  - Good: `build_damage_snapshot()`, `expand_box()`, `list_working_devices()`
  - Bad: `buildDamageSnapshot()`, `expandBox()`

- **Classes**: `PascalCase`
  - Good: `ContainerDamageDetector`, `DamageAlertTracker`, `MainWindow`
  - Bad: `container_damage_detector`, `ContainerDamageDETECTOR`

- **Constants**: `UPPER_SNAKE_CASE` (rare; most hardcoded values go in dataclasses or function defaults)
  - Good: `MIN_SIDE=200` (inside `DamagePopup`)
  - Bad: `minSide`, `min_side`

- **File names**: `snake_case.py`
  - Good: `main_window.py`, `video_worker.py`
  - Bad: `MainWindow.py`, `VideoWorker.py`

## Error Handling

- **No silent failures**: If model loading fails, let the exception propagate or wrap with meaningful message
- **User-facing errors**: QMessageBox with Vietnamese text
- **Logging**: Print to console if needed; no logging framework configured
- **Example** (from main_window.py):
  ```python
  try:
      self._load_selected_model()
  except FileNotFoundError as e:
      QMessageBox.critical(self, "Lỗi", f"Không tìm thấy mô hình: {e}")
  ```

## Testing

**Current state**: No test suite exists.

- Functional testing done manually (load image, adjust params, record video, test GPU fallback)
- Production use would require unit tests for:
  - Two-stage pipeline logic
  - Geometry (expand_box, iou)
  - Alert tracker deduplication
  - Video I/O and frame processing

See `docs/project-roadmap.md` for testing as a gap.

## No Linting / Type Checking Config

- No `mypy`, `pylint`, `black`, `isort` configuration
- No GitHub Actions / CI pipeline
- Code follows PEP 8 conventions informally
- Type hints used in function signatures but not enforced

Production use would require these.

## Git & Commits

- **Main branch only**: No feature branches in history yet
- **Recent commits**:
  - `824ca65` Add core application, GUI, model weights, and assets
  - `ac6fcef` app v1.0.0
- **Commit message style**: Brief, present tense, no emojis
- **No pre-commit hooks**: Secrets, lint errors not automatically caught

## Dependencies Pinning

**Current**: No `requirements.txt` or `pyproject.toml`.

- Runtime deps inferred from imports: PyQt6, OpenCV, torch, ultralytics
- PyInstaller `app.spec` bundles specific wheel URLs (CUDA-enabled torch, etc.) but not centrally documented
- Production use would require `pyproject.toml` with version constraints

See `docs/project-roadmap.md`.

## Performance Considerations

- **Batch crop processing**: All container crops from a single frame are batched into one damage-model predict() call, not separate calls per crop
- **GPU detection at startup**: Validates CUDA capability with actual ops, not just driver check
- **Video FPS fallback**: If source reports ≤1 or >240 fps, assume 20.0 (avoids spurious fast/slow playback)
- **Lazy model loading**: Models only loaded when user selects them, not at app startup
- **UI thread blocking**: Only when static image is shown; video/camera runs on separate `VideoWorker` thread

## Future Improvements

- Add `pytest` + test suite for core logic
- Enforce type hints with `mypy`
- Linting with `black` + `pylint`
- Configure pre-commit hooks to catch secrets
- Add `pyproject.toml` with pinned dependency versions
