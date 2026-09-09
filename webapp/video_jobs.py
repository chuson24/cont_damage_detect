"""Temp storage for uploaded video files and the frame-reading generator for
the /ws/video WebSocket."""
import os
import tempfile
import uuid
from typing import Iterator

import cv2

_UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "cdd_web_uploads")
os.makedirs(_UPLOAD_DIR, exist_ok=True)


def save_upload(data: bytes, suffix: str) -> str:
    video_id = uuid.uuid4().hex
    path = os.path.join(_UPLOAD_DIR, f"{video_id}{suffix}")
    with open(path, "wb") as f:
        f.write(data)
    return video_id


def resolve_path(video_id: str) -> str:
    for name in os.listdir(_UPLOAD_DIR):
        if name.startswith(video_id):
            return os.path.join(_UPLOAD_DIR, name)
    raise FileNotFoundError(f"Không tìm thấy video đã upload: {video_id}")


def discard(video_id: str):
    try:
        os.remove(resolve_path(video_id))
    except FileNotFoundError:
        pass


def read_frames(path: str) -> Iterator[object]:
    """Yield each frame_bgr in the video in order. FPS (read + predict
    throughput) is measured by the caller around its full per-frame work,
    mirroring gui/video_worker.py's VideoWorker.run() loop timing."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"Không thể mở video: {path}")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            yield frame
    finally:
        cap.release()
