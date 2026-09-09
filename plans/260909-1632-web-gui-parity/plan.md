# Web GUI Parity

Status: done (backend fully verified end-to-end against real weights; frontend written but not browser-verified — no display/camera in this environment). See `plans/reports/web-gui-parity-260909-1642-webapp-implementation-report.md`.

## Goal

Simple web app mirroring `gui/` desktop functionality/layout: image upload, video upload, browser webcam, two-stage config panels, results list, damage alert popups. Reuses `core/` pipeline as-is (no changes to `core/`).

## Decisions (confirmed with user)

- Full scope: image + video + webcam.
- Backend: FastAPI (async fits WebSocket streaming for video/webcam).
- Frontend: plain HTML/CSS/JS, no build step (per "simple" request).

## Phases

1. `phase-01-backend.md` — FastAPI app under `webapp/`: model/device listing, per-session pipeline state, image detect endpoint, video-file WebSocket streaming loop, webcam-frame WebSocket loop. Reuses `core/pipeline.py`, `core/alert_tracker.py`, `core/damage_snapshot.py`, `core/model_registry.py`, `core/gpu_check.py` unchanged.
2. `phase-02-frontend.md` — Static HTML/CSS/JS mirroring desktop layout (left: display + playback controls; right: collapsible config groups + results list). Image/video/webcam flows wired to backend endpoints. Client-side save (canvas → download) and record (MediaRecorder on canvas stream) — no backend needed for these two.

## Dependencies

New: `fastapi`, `uvicorn[standard]`, `python-multipart` (backend only, additive to existing `torch`/`ultralytics`/`opencv-python`/`numpy` already required by `core/`).

## Acceptance criteria

- `uvicorn webapp.server:app` serves a page at `/` with working image detection end-to-end (upload → annotated result + results list) against the real weights in `weights/`.
- Video upload streams annotated frames + FPS over WebSocket until EOF or stop.
- Webcam capture in-browser streams frames to backend and receives annotated frames back.
- Param changes (conf/iou/imgsz/padding/display toggles/cooldown) take effect without reloading the model.
- Damage alerts dedup per session via existing `DamageAlertTracker`, matching desktop cooldown behavior.

## Rollback

New code is additive under `webapp/`; no existing file is modified except README.md (short "Web UI" pointer) and `docs/system-architecture.md` (addendum noting the web client exists). Safe to delete `webapp/` to fully revert.
