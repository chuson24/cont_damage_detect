"""Renders a list of Detection results onto a frame.

Kept separate from ContainerDamageDetector so inference and visualization
each have a single responsibility: the detector never touches pixels for
drawing, the annotator never runs a model.
"""
from typing import List

import cv2

from .detection import Detection

# distinct BGR colors per damage class index
_DAMAGE_COLORS = [
    (56, 56, 255), (151, 157, 255), (31, 112, 255), (29, 178, 255),
    (49, 210, 207), (10, 249, 72), (23, 204, 146), (134, 219, 61),
    (52, 147, 26), (187, 212, 0), (168, 153, 44), (255, 194, 0),
]
_CONTAINER_COLOR = (60, 220, 60)  # green


class DetectionAnnotator:
    def __init__(self, show_labels: bool = True, show_conf: bool = True, show_container_box: bool = True):
        self.show_labels = show_labels
        self.show_conf = show_conf
        self.show_container_box = show_container_box

    def draw(self, frame_bgr, detections: List[Detection]):
        annotated = frame_bgr.copy()
        for det in detections:
            if det.kind == "container":
                if self.show_container_box:
                    self._draw_box(annotated, det, _CONTAINER_COLOR)
            else:
                color = _DAMAGE_COLORS[det.cls_id % len(_DAMAGE_COLORS)]
                self._draw_box(annotated, det, color)
        return annotated

    def _draw_box(self, annotated, det: Detection, color):
        x1, y1, x2, y2 = det.box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        if not self.show_labels:
            return
        text = det.label
        if self.show_conf:
            text += f" {det.conf:.2f}"
        self._draw_label(annotated, x1, y1, text, color)

    @staticmethod
    def _draw_label(annotated, x1, y1, text, color):
        (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        ty1 = max(y1 - th - baseline - 4, 0)
        cv2.rectangle(annotated, (x1, ty1), (x1 + tw + 4, ty1 + th + baseline + 4), color, -1)
        cv2.putText(
            annotated, text, (x1 + 2, ty1 + th + 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA
        )
