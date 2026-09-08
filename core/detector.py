"""Two-stage container damage detector: pure inference logic (no drawing, no Qt).

Stage 1 (container model): locate container(s) in the full frame.
Stage 2 (damage model): for each container box (expanded by a small padding
margin and clamped to the frame), crop that region and run the damage model
on the crop only, then map the resulting boxes back to full-frame
coordinates.

Running the damage model on the container crop instead of the whole frame
is both more accurate (damage is small relative to the full scene, so the
crop gives the detector effectively higher resolution on the object that
matters) and cheaper (the damage model looks at far fewer background
pixels). All container crops from a frame are batched into a single
damage-model predict() call for speed, which matters for video throughput.
"""
from typing import List

from ultralytics import YOLO

from .detection import Detection
from .geometry import expand_box
from .stage_config import StageConfig


class ContainerDamageDetector:
    def __init__(self, container_weights: str, damage_weights: str, device: str = "cpu"):
        self.container_model = YOLO(container_weights)
        self.damage_model = YOLO(damage_weights)
        self.device = device

        self.container_names = self.container_model.names
        self.damage_names = self.damage_model.names

        self.container_cfg = StageConfig()
        self.damage_cfg = StageConfig()

        # extra margin (fraction of box size) added around each container
        # crop so damage sitting right at the container's edge/corner isn't
        # cut off by a tight box from stage 1.
        self.padding_ratio = 0.08
        # ignore obviously spurious/tiny container detections before cropping
        self.min_container_side = 32

    # ------------------------------------------------------------- params
    def set_container_params(self, conf=None, iou=None, imgsz=None):
        if conf is not None:
            self.container_cfg.conf = conf
        if iou is not None:
            self.container_cfg.iou = iou
        if imgsz is not None:
            self.container_cfg.imgsz = imgsz

    def set_damage_params(self, conf=None, iou=None, imgsz=None):
        if conf is not None:
            self.damage_cfg.conf = conf
        if iou is not None:
            self.damage_cfg.iou = iou
        if imgsz is not None:
            self.damage_cfg.imgsz = imgsz

    def set_padding_ratio(self, ratio: float):
        self.padding_ratio = max(0.0, float(ratio))

    # ------------------------------------------------------------- detect
    def detect(self, frame_bgr) -> List[Detection]:
        """Run the 2-stage pipeline and return a flat list of Detection
        objects (container boxes + damage boxes already mapped back to
        full-frame coordinates). Damage inference only runs on crops of
        containers actually found; if no container is found, an empty
        list is returned without touching the damage model at all.
        """
        h, w = frame_bgr.shape[:2]
        detections: List[Detection] = []

        container_result = self.container_model.predict(
            source=frame_bgr,
            conf=self.container_cfg.conf,
            iou=self.container_cfg.iou,
            imgsz=self.container_cfg.imgsz,
            device=self.device,
            verbose=False,
        )[0]

        container_boxes = []  # (x1, y1, x2, y2, cls_id, conf)
        if container_result.boxes is not None:
            for box in container_result.boxes:
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                if (x2 - x1) < self.min_container_side or (y2 - y1) < self.min_container_side:
                    continue
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                container_boxes.append((x1, y1, x2, y2, cls_id, conf))

        if not container_boxes:
            return detections

        crops_meta = [expand_box(b[:4], w, h, self.padding_ratio) for b in container_boxes]
        crops = [frame_bgr[cy1:cy2, cx1:cx2] for (cx1, cy1, cx2, cy2) in crops_meta]

        valid = [(m, c) for m, c in zip(crops_meta, crops) if c.size > 0]
        crops_meta = [m for m, _ in valid]
        crops = [c for _, c in valid]

        damage_results_list = []
        if crops:
            damage_results_list = self.damage_model.predict(
                source=crops,
                conf=self.damage_cfg.conf,
                iou=self.damage_cfg.iou,
                imgsz=self.damage_cfg.imgsz,
                device=self.device,
                verbose=False,
            )

        for container_idx, (x1, y1, x2, y2, cls_id, conf) in enumerate(container_boxes):
            label = self.container_names.get(cls_id, str(cls_id))
            detections.append(Detection(
                label=label, conf=conf, box=(x1, y1, x2, y2),
                cls_id=cls_id, kind="container", container_idx=container_idx,
            ))

        for container_idx, ((cx1, cy1, cx2, cy2), dmg_result) in enumerate(zip(crops_meta, damage_results_list)):
            if dmg_result.boxes is None:
                continue
            for box in dmg_result.boxes:
                bx1, by1, bx2, by2 = [int(v) for v in box.xyxy[0].tolist()]
                fx1, fy1 = bx1 + cx1, by1 + cy1
                fx2, fy2 = bx2 + cx1, by2 + cy1
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                label = self.damage_names.get(cls_id, str(cls_id))
                detections.append(Detection(
                    label=label, conf=conf, box=(fx1, fy1, fx2, fy2),
                    cls_id=cls_id, kind="damage", container_idx=container_idx,
                ))

        return detections
