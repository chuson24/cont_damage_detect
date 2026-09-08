"""High-level facade combining detection + visualization for GUI/CLI consumption.

This is the only class the GUI layer should talk to for running inference —
it hides whether results come from one detector or several, and whether
drawing is done by one annotator or a themed one.
"""
from .annotator import DetectionAnnotator
from .detector import ContainerDamageDetector


class ContainerDamagePipeline:
    def __init__(self, container_weights: str, damage_weights: str, device: str = "cpu"):
        self.detector = ContainerDamageDetector(container_weights, damage_weights, device=device)
        self.annotator = DetectionAnnotator()

    @property
    def container_names(self):
        return self.detector.container_names

    @property
    def damage_names(self):
        return self.detector.damage_names

    def set_container_params(self, conf=None, iou=None, imgsz=None):
        self.detector.set_container_params(conf=conf, iou=iou, imgsz=imgsz)

    def set_damage_params(self, conf=None, iou=None, imgsz=None):
        self.detector.set_damage_params(conf=conf, iou=iou, imgsz=imgsz)

    def set_padding_ratio(self, ratio: float):
        self.detector.set_padding_ratio(ratio)

    def set_display_params(self, show_labels=None, show_conf=None, show_container_box=None):
        if show_labels is not None:
            self.annotator.show_labels = show_labels
        if show_conf is not None:
            self.annotator.show_conf = show_conf
        if show_container_box is not None:
            self.annotator.show_container_box = show_container_box

    def predict(self, frame_bgr):
        """Run detection then draw the results. Returns (detections, annotated_frame)."""
        detections = self.detector.detect(frame_bgr)
        annotated = self.annotator.draw(frame_bgr, detections)
        return detections, annotated
