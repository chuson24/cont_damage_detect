"""Background thread that pulls frames from a video/camera source and runs
the detection pipeline on each one, without blocking the UI thread."""
import time

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from core.pipeline import ContainerDamagePipeline


class VideoWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray, np.ndarray, list, float)  # raw frame(bgr), annotated frame(bgr), detections, fps
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    info_ready = pyqtSignal(float)  # source fps (for recording)

    def __init__(self, pipeline: ContainerDamagePipeline, source, is_camera: bool = False):
        super().__init__()
        self.pipeline = pipeline
        self.source = source
        self.is_camera = is_camera
        self._running = False

    def stop(self):
        self._running = False

    def run(self):
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.error_signal.emit(f"Không thể mở nguồn video: {self.source}")
            return

        source_fps = cap.get(cv2.CAP_PROP_FPS)
        if not source_fps or source_fps <= 1 or source_fps > 240:
            source_fps = 20.0  # fallback for cameras/files that report unreliable fps
        self.info_ready.emit(source_fps)

        self._running = True
        prev_t = time.time()
        fps = 0.0
        while self._running:
            ret, frame = cap.read()
            if not ret:
                break
            try:
                detections, annotated = self.pipeline.predict(frame)
            except Exception as e:
                self.error_signal.emit(str(e))
                break

            now = time.time()
            dt = now - prev_t
            prev_t = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps > 0 else 1.0 / dt

            self.frame_ready.emit(frame, annotated, detections, fps)

        cap.release()
        self.finished_signal.emit()
