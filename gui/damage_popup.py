"""Non-modal popup window showing a close-up of one newly-detected damage."""
import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton

from core.detection import Detection

_MAX_SIDE = 480
_MIN_SIDE = 200


class DamagePopup(QDialog):
    def __init__(self, crop_bgr, detection: Detection, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Phát hiện hư hỏng: {detection.label}")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        image_label = QLabel()
        image_label.setPixmap(self._to_pixmap(crop_bgr))
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(image_label)

        container_txt = "?" if detection.container_idx is None else str(detection.container_idx)
        info_label = QLabel(
            f"Loại hư hỏng: {detection.label}\n"
            f"Độ tin cậy: {detection.conf:.0%}\n"
            f"Container #{container_txt}\n"
            f"Vị trí (khung gốc): {detection.box}"
        )
        layout.addWidget(info_label)

        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    @staticmethod
    def _to_pixmap(bgr):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg)

        longest = max(pix.width(), pix.height())
        if longest > _MAX_SIDE:
            pix = pix.scaled(_MAX_SIDE, _MAX_SIDE, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        elif longest < _MIN_SIDE and longest > 0:
            scale = _MIN_SIDE / longest
            pix = pix.scaled(int(pix.width() * scale), int(pix.height() * scale),
                              Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return pix
