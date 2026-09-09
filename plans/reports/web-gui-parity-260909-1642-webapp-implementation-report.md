# Web GUI Parity — Implementation Report

Plan: `plans/260909-1632-web-gui-parity/`

## What was built

`webapp/` — FastAPI backend + vanilla HTML/CSS/JS frontend mirroring `gui/main_window.py`'s functionality, reusing `core/` unchanged.

- `webapp/server.py` — REST endpoints (`/api/models`, `/api/devices`, `/api/session/load_model`, `/api/session/params`, `/api/detect_image`, `/api/upload_video`) + WebSockets (`/ws/video/{video_id}`, `/ws/webcam`).
- `webapp/session.py` — per-browser-tab `AppSession` (pipeline + alert_tracker), keyed by client-generated `session_id`.
- `webapp/video_jobs.py` — temp upload storage + frame-reading generator.
- `webapp/encoding.py` — base64/JPEG + `Detection` → JSON helpers.
- `webapp/static/{index.html,app.css,app.js}` — no-build-step UI mirroring the desktop layout (collapsible config groups via native `<details>`, canvas display, playback controls, damage popups).
- `webapp/requirements.txt` — additive deps (fastapi, uvicorn, python-multipart).
- Docs: short "Web UI" section in `README.md`, "Web Client" addendum in `docs/system-architecture.md`.

## Design notes

- Save (canvas → PNG download) and record (`canvas.captureStream()` + `MediaRecorder` → `.webm`) are pure client-side — no backend endpoint needed.
- Webcam is the **browser's** camera (`getUserMedia`), pushed frame-by-frame to the server — inverted from desktop where the camera is server-side.
- Video streaming: a background thread mirrors `VideoWorker`'s read+predict loop, pushing results onto a bounded `queue.Queue(maxsize=4)`; the async handler drains it, so a slow client backpressures the reader instead of buffering the whole video in memory.

## Bug found and fixed during testing

Video WS "stop" caused a permanent hang: when the background worker thread saw `stop_event` (or gave up because the queue stayed full while blocked), it could `return`/`break` without ever enqueueing a terminal message, and the async consumer's `await run_in_threadpool(result_queue.get)` then blocked forever. Fixed by moving all terminal-message decisions into a single `finally` block in `_worker()`, guaranteeing exactly one of `done`/`error`/`stopped` is always enqueued no matter which branch runs. Root-caused by adding temporary debug prints and reproducing with a real WS test client against the live server — reverted after confirming the fix (verified: mid-stream stop, natural completion, and error paths all terminate cleanly).

Also fixed along the way: the video-stream FPS was originally measured only across `cv2.VideoCapture.read()` calls (decode speed), not the full read+predict cycle, so it wouldn't reflect real throughput like the desktop's `VideoWorker` does. Moved the timing to wrap the whole per-frame cycle in `server.py`.

## Verification performed

Ran the actual FastAPI server locally (via a project venv the user set up, with fastapi/uvicorn/torch(cpu)/torchvision/ultralytics/opencv installed) against the real weights in `weights/`:
- `/api/models`, `/api/devices` — correct weight discovery + guessing, correct CPU-only device list in this sandbox.
- `/api/session/load_model` — loads both real `.pt` files, returns correct class names (container; bent/broken/crack/dent/hole/rust/scratch/weld_damage).
- `/api/detect_image` — real image → real detections (container + damage boxes) + a damage alert with a valid JPEG snapshot crop.
- `/api/session/params` — success and "not-loaded" error paths both correct.
- `WS /ws/video/{id}` — natural completion (all 60 frames + `done`), and manual mid-stream `stop` (clean termination, no hang) — both verified after the fix.
- `WS /ws/webcam` — client-pushed frames get real detections back; repeat-frame alert dedup via `DamageAlertTracker` confirmed (1st frame: 5 new alerts, repeats: 0 new alerts).

Not verified (no browser/camera in this environment): the actual `webapp/static/*` JS in a real browser (canvas rendering, `getUserMedia`, `MediaRecorder` download). Frontend code was written to match the tested backend's exact message/field shapes, but the user should smoke-test in an actual browser before relying on it.

## Unresolved / left to the user

- Frontend not visually/interactively verified in a real browser (no display/camera in this sandbox).
- No automated tests added (matches existing repo convention — no test suite anywhere).
- `webapp/requirements.txt` lists backend-only additive deps; core deps (torch/torchvision/ultralytics/opencv/numpy) are commented as already required by `gui/`, not re-pinned.
