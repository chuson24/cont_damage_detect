"""Data model for a single detected object (container or damage box)."""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class Detection:
    label: str
    conf: float
    box: Tuple[int, int, int, int]  # x1, y1, x2, y2 in full-frame coordinates
    cls_id: int
    kind: str  # "container" or "damage"
    container_idx: Optional[int] = None  # which container box this belongs to
