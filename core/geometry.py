"""Small geometry helpers shared across the core layer."""
from typing import Tuple

Box = Tuple[int, int, int, int]


def iou(box_a: Box, box_b: Box) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def expand_box(box: Box, frame_w: int, frame_h: int, pad_ratio: float, min_pad: int = 0) -> Box:
    """Grow `box` by `pad_ratio` of its own size (at least `min_pad` px on
    each side), clamped to the frame bounds."""
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    pad_x = max(int(bw * pad_ratio), min_pad)
    pad_y = max(int(bh * pad_ratio), min_pad)
    nx1 = max(0, x1 - pad_x)
    ny1 = max(0, y1 - pad_y)
    nx2 = min(frame_w, x2 + pad_x)
    ny2 = min(frame_h, y2 + pad_y)
    return nx1, ny1, nx2, ny2
