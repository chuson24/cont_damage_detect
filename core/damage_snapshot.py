"""Builds a cropped, highlighted preview image for a single damage
Detection — used to show the user a close-up of what was just detected
(e.g. in a popup window). Pure pixel work, no Qt involved."""
import cv2

from .detection import Detection
from .geometry import expand_box

_HIGHLIGHT_COLOR = (0, 0, 255)  # red, in BGR


def build_damage_snapshot(frame_bgr, detection: Detection, pad_ratio: float = 0.6, min_pad: int = 24):
    """Crop `frame_bgr` around `detection.box` with generous context padding
    and draw the exact damage box on the crop so the user can see precisely
    what triggered the alert. Returns an empty array if the box is degenerate."""
    h, w = frame_bgr.shape[:2]
    cx1, cy1, cx2, cy2 = expand_box(detection.box, w, h, pad_ratio, min_pad=min_pad)
    crop = frame_bgr[cy1:cy2, cx1:cx2].copy()
    if crop.size == 0:
        return crop

    x1, y1, x2, y2 = detection.box
    rx1, ry1 = x1 - cx1, y1 - cy1
    rx2, ry2 = x2 - cx1, y2 - cy1
    cv2.rectangle(crop, (rx1, ry1), (rx2, ry2), _HIGHLIGHT_COLOR, 2)
    return crop
