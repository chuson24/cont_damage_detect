"""FastAPI web app mirroring gui/main_window.py's functionality: image
upload, video upload, and browser-webcam detection against the same
core/ pipeline the desktop app uses.

Run from the repo root:  uvicorn webapp.server:app --reload
"""
import asyncio
import os
import queue
import threading
import time

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.damage_snapshot import build_damage_snapshot
from core.gpu_check import list_working_devices
from core.model_registry import find_weight_files, guess_weight_file
from core.pipeline import ContainerDamagePipeline
from webapp.encoding import b64_to_frame, detections_to_list, frame_to_b64
from webapp.session import AppSession, sessions
from webapp.video_jobs import discard as discard_video, read_frames, resolve_path, save_upload

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS_DIR = os.path.join(APP_DIR, "weights")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="Container Damage Detection - Web")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# --------------------------------------------------------------- discovery
@app.get("/api/models")
def api_models():
    models = find_weight_files(WEIGHTS_DIR)
    rel = [os.path.relpath(m, APP_DIR) for m in models]
    damage_guess = guess_weight_file(rel, lambda n: "damage" in n)
    container_guess = guess_weight_file(rel, lambda n: "damage" not in n)
    return {"models": rel, "guess": {"container": container_guess, "damage": damage_guess}}


@app.get("/api/devices")
def api_devices():
    devices, warnings = list_working_devices()
    return {"devices": devices, "warnings": warnings}


# ------------------------------------------------------------------ session
class LoadModelBody(BaseModel):
    session_id: str
    container_path: str
    damage_path: str
    device: str = "cpu"


def _resolve_weight(rel_path: str) -> str:
    abs_path = os.path.normpath(os.path.join(APP_DIR, rel_path))
    if not (abs_path == WEIGHTS_DIR or abs_path.startswith(WEIGHTS_DIR + os.sep)) or not os.path.isfile(abs_path):
        raise HTTPException(400, f"Đường dẫn model không hợp lệ: {rel_path}")
    return abs_path


@app.post("/api/session/load_model")
async def load_model(body: LoadModelBody):
    container_path = _resolve_weight(body.container_path)
    damage_path = _resolve_weight(body.damage_path)
    session = sessions.get_or_create(body.session_id)

    def _build():
        return ContainerDamagePipeline(container_path, damage_path, device=body.device)

    try:
        session.pipeline = await run_in_threadpool(_build)
    except Exception as e:
        raise HTTPException(400, f"Lỗi nạp model: {e}")

    return {
        "container_names": list(session.pipeline.container_names.values()),
        "damage_names": list(session.pipeline.damage_names.values()),
    }


class StageParams(BaseModel):
    conf: float
    iou: float
    imgsz: int


class DisplayParams(BaseModel):
    show_labels: bool = True
    show_conf: bool = True
    show_container_box: bool = True


class SessionParamsBody(BaseModel):
    session_id: str
    container: StageParams
    damage: StageParams
    padding_ratio: float = 0.08
    display: DisplayParams = DisplayParams()
    cooldown_seconds: float = 5.0


def _require_pipeline(session_id: str) -> AppSession:
    session = sessions.get(session_id)
    if session is None or session.pipeline is None:
        raise HTTPException(400, "Chưa nạp model cho phiên này. Vui lòng nạp model trước.")
    return session


@app.post("/api/session/params")
def set_params(body: SessionParamsBody):
    session = _require_pipeline(body.session_id)
    pipeline = session.pipeline
    pipeline.set_container_params(conf=body.container.conf, iou=body.container.iou, imgsz=body.container.imgsz)
    pipeline.set_damage_params(conf=body.damage.conf, iou=body.damage.iou, imgsz=body.damage.imgsz)
    pipeline.set_padding_ratio(body.padding_ratio)
    pipeline.set_display_params(**body.display.model_dump())
    session.alert_tracker.cooldown_seconds = body.cooldown_seconds
    return {"ok": True}


# ------------------------------------------------------------------- alerts
def _build_alerts(raw_frame, session: AppSession, detections) -> list:
    alerts = []
    for det in session.alert_tracker.filter_new(detections):
        crop = build_damage_snapshot(raw_frame, det)
        if crop.size == 0:
            continue
        alerts.append({
            "label": det.label,
            "conf": det.conf,
            "box": list(det.box),
            "container_idx": det.container_idx,
            "snapshot_b64": frame_to_b64(crop),
        })
    return alerts


# --------------------------------------------------------------- image mode
@app.post("/api/detect_image")
async def detect_image(session_id: str = Form(...), file: UploadFile = File(...)):
    session = _require_pipeline(session_id)
    data = await file.read()
    frame = cv2.imdecode(np.frombuffer(data, dtype="uint8"), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "Không đọc được ảnh.")

    session.alert_tracker.reset()  # new static image == new source, like desktop open_image()
    detections, annotated = await run_in_threadpool(session.pipeline.predict, frame)
    alerts = _build_alerts(frame, session, detections)

    return {
        "annotated_image_b64": frame_to_b64(annotated, quality=92),
        "detections": detections_to_list(detections),
        "alerts": alerts,
    }


# --------------------------------------------------------------- video mode
@app.post("/api/upload_video")
async def upload_video(file: UploadFile = File(...)):
    data = await file.read()
    suffix = os.path.splitext(file.filename or "")[1] or ".mp4"
    video_id = save_upload(data, suffix)
    return {"video_id": video_id}


@app.websocket("/ws/video/{video_id}")
async def ws_video(websocket: WebSocket, video_id: str, session_id: str):
    await websocket.accept()
    session = sessions.get(session_id)
    if session is None or session.pipeline is None:
        await websocket.send_json({"type": "error", "message": "Chưa nạp model cho phiên này."})
        await websocket.close()
        return

    try:
        path = resolve_path(video_id)
    except FileNotFoundError as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()
        return

    session.alert_tracker.reset()  # new video == new source, like desktop _start_stream()

    # A background thread does the blocking cv2 read + YOLO predict loop
    # (mirrors gui/video_worker.py's QThread) and pushes results onto a
    # bounded queue; the async handler just drains the queue and sends
    # over the socket, so a slow network client naturally backpressures
    # the reader instead of buffering the whole video in memory.
    result_queue: "queue.Queue" = queue.Queue(maxsize=4)
    stop_event = threading.Event()

    def _put_frame(item) -> bool:
        """Put a frame result, giving up (returns False) once stop_event
        fires while blocked on a full queue — the consumer already left."""
        while not stop_event.is_set():
            try:
                result_queue.put(item, timeout=0.5)
                return True
            except queue.Full:
                continue
        return False

    def _put_final(item):
        """Terminal message (frame/error/stopped) — always keeps retrying
        past stop_event so the consumer's blocking get() is guaranteed to
        unblock instead of hanging forever."""
        for _ in range(20):  # ~10s of retrying before giving up
            try:
                result_queue.put(item, timeout=0.5)
                return
            except queue.Full:
                continue

    def _worker():
        # Exactly one terminal message is always enqueued via `finally`, no
        # matter which branch below is taken — this is what guarantees the
        # consumer's blocking queue.get() can never wait forever.
        prev_t = time.time()
        fps = 0.0
        terminal = ("stopped",)
        try:
            for frame in read_frames(path):
                if stop_event.is_set():
                    break
                detections, annotated = session.pipeline.predict(frame)
                alerts = _build_alerts(frame, session, detections)

                # fps covers the whole read+predict cycle, same as
                # gui/video_worker.py's VideoWorker.run() loop timing.
                now = time.time()
                dt = now - prev_t
                prev_t = now
                if dt > 0:
                    fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps > 0 else 1.0 / dt

                if not _put_frame(("frame", annotated, detections, fps, alerts)):
                    break  # consumer/socket already gone
            else:
                terminal = ("done",)
        except Exception as e:
            terminal = ("error", str(e))
        finally:
            _put_final(terminal)

    worker_thread = threading.Thread(target=_worker, daemon=True)
    worker_thread.start()

    async def _watch_stop():
        try:
            while True:
                msg = await websocket.receive_text()
                if msg == "stop":
                    stop_event.set()
                    break
        except WebSocketDisconnect:
            stop_event.set()

    watcher = asyncio.create_task(_watch_stop())
    try:
        while True:
            item = await run_in_threadpool(result_queue.get)
            if item[0] == "error":
                await websocket.send_json({"type": "error", "message": item[1]})
                break
            if item[0] == "done":
                await websocket.send_json({"type": "done"})
                break
            if item[0] == "stopped":
                break
            _, annotated, detections, fps, alerts = item
            await websocket.send_json({
                "type": "frame",
                "annotated_image_b64": frame_to_b64(annotated),
                "detections": detections_to_list(detections),
                "fps": fps,
            })
            for alert in alerts:
                await websocket.send_json({"type": "alert", **alert})
    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        watcher.cancel()
        await run_in_threadpool(worker_thread.join, 2.0)
        discard_video(video_id)
        try:
            await websocket.close()
        except RuntimeError:
            pass


# -------------------------------------------------------------- webcam mode
@app.websocket("/ws/webcam")
async def ws_webcam(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = sessions.get(session_id)
    if session is None or session.pipeline is None:
        await websocket.send_json({"type": "error", "message": "Chưa nạp model cho phiên này."})
        await websocket.close()
        return

    session.alert_tracker.reset()  # new webcam session == new source, like desktop _start_stream()
    prev_t = time.time()
    fps = 0.0
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "stop":
                break
            frame = b64_to_frame(msg["image_b64"])
            if frame is None:
                continue

            now = time.time()
            dt = now - prev_t
            prev_t = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps > 0 else 1.0 / dt

            detections, annotated = await run_in_threadpool(session.pipeline.predict, frame)
            alerts = _build_alerts(frame, session, detections)
            await websocket.send_json({
                "type": "frame",
                "annotated_image_b64": frame_to_b64(annotated),
                "detections": detections_to_list(detections),
                "fps": fps,
            })
            for alert in alerts:
                await websocket.send_json({"type": "alert", **alert})
    except WebSocketDisconnect:
        pass
