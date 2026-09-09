# Phase 01 — Backend (FastAPI)

## Files to create

- `webapp/__init__.py` — empty.
- `webapp/session.py` — `SessionStore`: in-memory dict `session_id -> AppSession` (pipeline, alert_tracker, params). No persistence needed (demo tool, matches desktop's single-process model).
- `webapp/video_jobs.py` — temp video upload storage + a generator that mirrors `gui/video_worker.py`'s loop (cv2.VideoCapture read loop, FPS smoothing) but yields frames instead of emitting Qt signals.
- `webapp/server.py` — FastAPI app, routes below, serves `webapp/static/`.

## Endpoints

- `GET /` → `static/index.html`.
- `GET /api/models` → `core.model_registry.find_weight_files` + `guess_weight_file` against `weights/`.
- `GET /api/devices` → `core.gpu_check.list_working_devices()`.
- `POST /api/session/load_model` `{session_id, container_path, damage_path, device}` → builds `ContainerDamagePipeline`, stores in session, returns class names.
- `POST /api/session/params` `{session_id, container:{conf,iou,imgsz}, damage:{...}, padding_ratio, display:{...}, cooldown_seconds}` → updates pipeline + alert_tracker on session.
- `POST /api/detect_image` multipart `{session_id, file}` → `alert_tracker.reset()` (new source, matches desktop `open_image`) then `pipeline.predict()`, returns `{annotated_image_b64, detections[], alerts[]}` (alerts include a `damage_snapshot` b64 crop).
- `POST /api/upload_video` multipart `{file}` → save to a temp dir, return `{video_id}`.
- `WS /ws/video/{video_id}` query `session_id` → runs the video loop from `video_jobs.py`, emits JSON frames `{type: frame|alert|done|error, ...}`; reads client `"stop"` text messages to break early.
- `WS /ws/webcam` query `session_id` → receives client-pushed frames (base64 JPEG), runs `pipeline.predict()` per frame, emits the same frame/alert message shape.

## Constraints

- Do not modify any file under `core/`.
- Base64-encode frames with `cv2.imencode(".jpg", frame)` — keep payloads reasonably small (JPEG, not PNG, for video/webcam frames; PNG fine for single-image detect).
- One `ContainerDamagePipeline` per session_id — loading YOLO weights is expensive, must not reload per request/frame.

## Validation

- Smoke test via a local venv: `uvicorn webapp.server:app --reload`, hit `/api/models`, `/api/devices`, then `/api/detect_image` with a real image against `weights/*.pt` and confirm detections + annotated image round-trip.
