# Phase 02 — Frontend (static HTML/CSS/JS)

## Files to create

- `webapp/static/index.html` — layout mirroring `gui/main_window.py`: left column (canvas display + playback buttons: open image/video, start/stop webcam, save current frame, record), right column (collapsible `<details>` groups: model select + reload, container-stage config, damage-stage config, display & device, alert/cooldown, results list + FPS).
- `webapp/static/app.css` — minimal styling, dark display area like desktop (`#202020` background), collapsible sections via native `<details>`.
- `webapp/static/app.js` — all wiring: session id (crypto.randomUUID, kept in memory), populate models/devices on load, param change → `POST /api/session/params` (debounced) + re-run detect on the last static image if in image mode (mirrors `_rerun_static_if_any`), image upload → `POST /api/detect_image` → draw to canvas + results list + popups, video upload → `POST /api/upload_video` then `WS /ws/video/{id}`, webcam → `getUserMedia` + offscreen canvas capture loop → `WS /ws/webcam`, damage popups as floating `<div>`s (label/conf/container idx/box + snapshot image), client-side save (canvas → `toBlob` → download link) and record (`canvas.captureStream()` + `MediaRecorder` → webm download).

## UI text

Vietnamese, matching desktop strings where equivalent (see `core/CLAUDE.md` UI-language convention and `gui/main_window.py` labels).

## Constraints

- No frontend build step / bundler / framework — plain JS, one file, keep dependency-free.
- Recording produces `.webm` (browser `MediaRecorder` constraint) instead of desktop's `.mp4`/`.avi` — note this in the UI/status text as an intentional simplification, not a bug.

## Validation

- Manual browser check against the running `uvicorn` server: image flow, then video flow, then webcam flow (webcam requires a real browser + camera permission — verify via `run`/Playwright or ask user to confirm if no camera is available in this environment).
