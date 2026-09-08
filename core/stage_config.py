"""Inference configuration for a single YOLO stage (container or damage)."""
from dataclasses import dataclass


@dataclass
class StageConfig:
    conf: float = 0.25
    iou: float = 0.45
    imgsz: int = 640
