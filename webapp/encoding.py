"""JPEG/PNG <-> base64 helpers and Detection -> JSON shaping, shared by the
REST and WebSocket handlers."""
import base64
from typing import List

import cv2
import numpy as np

from core.detection import Detection


def frame_to_b64(frame_bgr, ext: str = ".jpg", quality: int = 80) -> str:
    params = [cv2.IMWRITE_JPEG_QUALITY, quality] if ext == ".jpg" else []
    ok, buf = cv2.imencode(ext, frame_bgr, params)
    if not ok:
        raise ValueError("Không mã hoá được frame")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def b64_to_frame(data_b64: str):
    raw = base64.b64decode(data_b64)
    arr = np.frombuffer(raw, dtype="uint8")
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def detection_to_dict(det: Detection) -> dict:
    return {
        "label": det.label,
        "conf": det.conf,
        "box": list(det.box),
        "cls_id": det.cls_id,
        "kind": det.kind,
        "container_idx": det.container_idx,
    }


def detections_to_list(detections: List[Detection]) -> list:
    return [detection_to_dict(d) for d in detections]
