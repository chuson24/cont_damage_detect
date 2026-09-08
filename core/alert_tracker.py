"""Decides which damage detections are "new" and worth alerting on.

For a single image this is just "every damage box found". For a video
stream the same physical damage is re-detected on every frame it stays in
view — without dedup that would trigger one alert per frame. This tracker
keeps a short memory of recently-alerted damage (matched by label + box
overlap, not by container_idx, since that index is only a per-frame
ordering and isn't a stable identity across frames) so the same damage
only re-triggers once it has been unmatched for `cooldown_seconds`.
"""
import time
from dataclasses import dataclass
from typing import List, Optional

from .detection import Detection
from .geometry import Box, iou


@dataclass
class _SeenDamage:
    label: str
    box: Box
    last_seen: float


class DamageAlertTracker:
    def __init__(self, cooldown_seconds: float = 5.0, iou_threshold: float = 0.3):
        self.cooldown_seconds = cooldown_seconds
        self.iou_threshold = iou_threshold
        self._seen: List[_SeenDamage] = []

    def reset(self):
        """Forget everything — call when a genuinely new source (new image,
        new video, new camera session) starts, so its damage always alerts."""
        self._seen.clear()

    def filter_new(self, detections: List[Detection], now: Optional[float] = None) -> List[Detection]:
        """Return the subset of damage Detections that should trigger a new alert."""
        if now is None:
            now = time.time()
        self._seen = [s for s in self._seen if now - s.last_seen <= self.cooldown_seconds]

        new_alerts = []
        for det in detections:
            if det.kind != "damage":
                continue
            match = next(
                (s for s in self._seen if s.label == det.label and iou(s.box, det.box) >= self.iou_threshold),
                None,
            )
            if match is not None:
                match.box = det.box
                match.last_seen = now
                continue
            self._seen.append(_SeenDamage(label=det.label, box=det.box, last_seen=now))
            new_alerts.append(det)
        return new_alerts
