"""Main window for the Container Damage Detection demo/test GUI.

This module only builds/wires up the UI and talks to `core.pipeline` for
all actual detection work — no YOLO/OpenCV inference logic lives here.
"""
import os

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QFileDialog, QGroupBox, QCheckBox, QMessageBox, QSizePolicy, QListWidget,
    QStatusBar
)

from core.alert_tracker import DamageAlertTracker
from core.damage_snapshot import build_damage_snapshot
from core.gpu_check import list_working_devices
from core.model_registry import find_weight_files, guess_weight_file
from core.paths import app_root, user_data_dir
from core.pipeline import ContainerDamagePipeline
from gui.damage_popup import DamagePopup
from gui.video_worker import VideoWorker

APP_DIR = app_root()
WEIGHTS_DIR = os.path.join(APP_DIR, "weights")
OUTPUTS_DIR = os.path.join(user_data_dir(), "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Container Damage Detection - Demo & Test")
        self.resize(1400, 820)

        self.pipeline: ContainerDamagePipeline | None = None
        self.worker: VideoWorker | None = None
        self.current_pixmap_source = None  # 'image' or 'video'/'camera'
        self.last_static_frame = None  # for re-running inference on param change (image mode)

        self.video_writer = None
        self.is_recording = False
        self.record_path = None
        self.record_fps = 20.0
        self._record_size = None

        self.alert_tracker = DamageAlertTracker(cooldown_seconds=5.0)
        self._damage_popups = []

        self._build_ui()
        self._populate_models()
        self._load_selected_model()

    # --------------------------------------------------------- UI helpers
    @staticmethod
    def _make_collapsible(group_box: QGroupBox, expanded: bool = True) -> QGroupBox:
        """Turn a QGroupBox into a collapsible section: its title checkbox
        shows/hides the body, so a long stack of config panels can be
        shrunk down to just their titles when screen space is tight."""
        group_box.setCheckable(True)
        group_box.setChecked(expanded)
        group_box.setToolTip("Nhấn để thu gọn / mở rộng mục này")

        def _toggle(checked):
            layout = group_box.layout()
            for i in range(layout.count()):
                widget = layout.itemAt(i).widget()
                if widget is not None:
                    widget.setVisible(checked)

        group_box.toggled.connect(_toggle)
        _toggle(expanded)
        return group_box

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # ---- Left: video/image display ----
        left_panel = QVBoxLayout()
        self.display_label = QLabel("Chưa có ảnh/video")
        self.display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display_label.setStyleSheet("background-color: #202020; color: #aaa; border: 1px solid #444;")
        self.display_label.setMinimumSize(720, 480)
        self.display_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_panel.addWidget(self.display_label, stretch=1)

        # playback controls
        pb_layout = QHBoxLayout()
        self.btn_open_image = QPushButton("Mở ảnh...")
        self.btn_open_video = QPushButton("Mở video...")
        self.btn_open_camera = QPushButton("Mở Camera")
        self.btn_stop = QPushButton("Dừng")
        self.btn_save = QPushButton("Lưu ảnh hiện tại...")
        self.btn_record = QPushButton("● Ghi video kết quả")
        self.btn_stop.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.btn_record.setEnabled(False)
        for b in (self.btn_open_image, self.btn_open_video, self.btn_open_camera, self.btn_stop, self.btn_save, self.btn_record):
            pb_layout.addWidget(b)
        left_panel.addLayout(pb_layout)

        self.status_label = QLabel("Sẵn sàng")
        left_panel.addWidget(self.status_label)

        main_layout.addLayout(left_panel, stretch=3)

        # ---- Right: configuration panel ----
        right_panel = QVBoxLayout()

        # Model group (two stages)
        model_group = QGroupBox("Model (2 giai đoạn: Container -> Damage)")
        model_layout = QGridLayout(model_group)

        model_layout.addWidget(QLabel("Model Container:"), 0, 0)
        self.container_model_combo = QComboBox()
        model_layout.addWidget(self.container_model_combo, 0, 1)
        self.btn_browse_container_model = QPushButton("Duyệt...")
        model_layout.addWidget(self.btn_browse_container_model, 0, 2)

        model_layout.addWidget(QLabel("Model Damage:"), 1, 0)
        self.damage_model_combo = QComboBox()
        model_layout.addWidget(self.damage_model_combo, 1, 1)
        self.btn_browse_damage_model = QPushButton("Duyệt...")
        model_layout.addWidget(self.btn_browse_damage_model, 1, 2)

        self.btn_reload_model = QPushButton("Nạp lại model")
        model_layout.addWidget(self.btn_reload_model, 2, 0, 1, 3)

        self.model_info_label = QLabel("Chưa nạp model")
        self.model_info_label.setWordWrap(True)
        model_layout.addWidget(self.model_info_label, 3, 0, 1, 3)
        right_panel.addWidget(self._make_collapsible(model_group))

        # Container stage config
        container_cfg_group = QGroupBox("Cấu hình phát hiện Container (giai đoạn 1)")
        container_cfg_layout = QGridLayout(container_cfg_group)

        container_cfg_layout.addWidget(QLabel("Confidence:"), 0, 0)
        self.container_conf_spin = QDoubleSpinBox()
        self.container_conf_spin.setRange(0.01, 1.0)
        self.container_conf_spin.setSingleStep(0.05)
        self.container_conf_spin.setValue(0.25)
        container_cfg_layout.addWidget(self.container_conf_spin, 0, 1)

        container_cfg_layout.addWidget(QLabel("IoU:"), 1, 0)
        self.container_iou_spin = QDoubleSpinBox()
        self.container_iou_spin.setRange(0.01, 1.0)
        self.container_iou_spin.setSingleStep(0.05)
        self.container_iou_spin.setValue(0.45)
        container_cfg_layout.addWidget(self.container_iou_spin, 1, 1)

        container_cfg_layout.addWidget(QLabel("Image size:"), 2, 0)
        self.container_imgsz_spin = QSpinBox()
        self.container_imgsz_spin.setRange(160, 1920)
        self.container_imgsz_spin.setSingleStep(32)
        self.container_imgsz_spin.setValue(640)
        container_cfg_layout.addWidget(self.container_imgsz_spin, 2, 1)

        container_cfg_layout.addWidget(QLabel("Padding crop (%):"), 3, 0)
        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(0, 50)
        self.padding_spin.setSingleStep(1)
        self.padding_spin.setValue(8)
        self.padding_spin.setToolTip(
            "Nới rộng khung container thêm % trước khi crop, để không cắt mất\n"
            "hư hỏng nằm sát mép/góc container."
        )
        container_cfg_layout.addWidget(self.padding_spin, 3, 1)

        right_panel.addWidget(self._make_collapsible(container_cfg_group))

        # Damage stage config
        damage_cfg_group = QGroupBox("Cấu hình phát hiện Damage (giai đoạn 2, chạy trên ảnh crop)")
        damage_cfg_layout = QGridLayout(damage_cfg_group)

        damage_cfg_layout.addWidget(QLabel("Confidence:"), 0, 0)
        self.damage_conf_spin = QDoubleSpinBox()
        self.damage_conf_spin.setRange(0.01, 1.0)
        self.damage_conf_spin.setSingleStep(0.05)
        self.damage_conf_spin.setValue(0.25)
        damage_cfg_layout.addWidget(self.damage_conf_spin, 0, 1)

        damage_cfg_layout.addWidget(QLabel("IoU:"), 1, 0)
        self.damage_iou_spin = QDoubleSpinBox()
        self.damage_iou_spin.setRange(0.01, 1.0)
        self.damage_iou_spin.setSingleStep(0.05)
        self.damage_iou_spin.setValue(0.45)
        damage_cfg_layout.addWidget(self.damage_iou_spin, 1, 1)

        damage_cfg_layout.addWidget(QLabel("Image size:"), 2, 0)
        self.damage_imgsz_spin = QSpinBox()
        self.damage_imgsz_spin.setRange(160, 1920)
        self.damage_imgsz_spin.setSingleStep(32)
        self.damage_imgsz_spin.setValue(640)
        damage_cfg_layout.addWidget(self.damage_imgsz_spin, 2, 1)

        right_panel.addWidget(self._make_collapsible(damage_cfg_group))

        # Shared display + device config
        display_cfg_group = QGroupBox("Hiển thị & Thiết bị")
        display_cfg_layout = QGridLayout(display_cfg_group)

        display_cfg_layout.addWidget(QLabel("Thiết bị:"), 0, 0)
        self.device_combo = QComboBox()
        devices, gpu_warnings = list_working_devices()
        self.device_combo.addItems(devices)
        if len(devices) > 1:
            self.device_combo.setCurrentIndex(1)  # default to first working GPU
        if gpu_warnings:
            details = "; ".join(f"{name}: {err}" for name, err in gpu_warnings.items())
            self.device_combo.setToolTip(f"Một số GPU không dùng được, đã ẩn: {details}")
        display_cfg_layout.addWidget(self.device_combo, 0, 1)

        self.show_container_box_cb = QCheckBox("Vẽ khung container")
        self.show_container_box_cb.setChecked(True)
        display_cfg_layout.addWidget(self.show_container_box_cb, 1, 0, 1, 2)

        self.show_labels_cb = QCheckBox("Hiện nhãn/label")
        self.show_labels_cb.setChecked(True)
        display_cfg_layout.addWidget(self.show_labels_cb, 2, 0, 1, 2)

        self.show_conf_cb = QCheckBox("Hiện % confidence")
        self.show_conf_cb.setChecked(True)
        display_cfg_layout.addWidget(self.show_conf_cb, 3, 0, 1, 2)

        right_panel.addWidget(self._make_collapsible(display_cfg_group))

        # Damage alert popup config
        alert_group = QGroupBox("Cảnh báo hư hỏng (popup)")
        alert_layout = QGridLayout(alert_group)

        self.show_popup_cb = QCheckBox("Hiện popup khi phát hiện hư hỏng mới")
        self.show_popup_cb.setChecked(True)
        alert_layout.addWidget(self.show_popup_cb, 0, 0, 1, 2)

        alert_layout.addWidget(QLabel("Chờ trước khi cảnh báo lại (giây):"), 1, 0)
        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(1, 60)
        self.cooldown_spin.setValue(5)
        self.cooldown_spin.setToolTip(
            "Cùng một vết hư hỏng sẽ không mở popup mới liên tục ở mỗi frame;\n"
            "chỉ cảnh báo lại sau khi không còn thấy nó trong khoảng thời gian này."
        )
        alert_layout.addWidget(self.cooldown_spin, 1, 1)

        right_panel.addWidget(self._make_collapsible(alert_group))

        # Camera config group
        cam_group = QGroupBox("Camera")
        cam_layout = QHBoxLayout(cam_group)
        cam_layout.addWidget(QLabel("Camera index:"))
        self.camera_index_spin = QSpinBox()
        self.camera_index_spin.setRange(0, 10)
        cam_layout.addWidget(self.camera_index_spin)
        right_panel.addWidget(self._make_collapsible(cam_group))

        # Detection results list
        results_group = QGroupBox("Kết quả phát hiện")
        results_layout = QVBoxLayout(results_group)
        self.results_list = QListWidget()
        results_layout.addWidget(self.results_list)
        self.fps_label = QLabel("FPS: -")
        results_layout.addWidget(self.fps_label)
        right_panel.addWidget(self._make_collapsible(results_group), stretch=1)

        right_panel.addStretch(0)
        main_layout.addLayout(right_panel, stretch=1)

        # ---- Status bar ----
        self.setStatusBar(QStatusBar())

        # ---- Signals ----
        self.btn_open_image.clicked.connect(self.open_image)
        self.btn_open_video.clicked.connect(self.open_video)
        self.btn_open_camera.clicked.connect(self.open_camera)
        self.btn_stop.clicked.connect(self.stop_stream)
        self.btn_save.clicked.connect(self.save_result)
        self.btn_record.clicked.connect(self.toggle_recording)
        self.btn_browse_container_model.clicked.connect(lambda: self.browse_model(self.container_model_combo))
        self.btn_browse_damage_model.clicked.connect(lambda: self.browse_model(self.damage_model_combo))
        self.btn_reload_model.clicked.connect(self._load_selected_model)
        self.container_model_combo.currentIndexChanged.connect(self._load_selected_model)
        self.damage_model_combo.currentIndexChanged.connect(self._load_selected_model)
        self.device_combo.currentIndexChanged.connect(self._load_selected_model)

        for w in (self.container_conf_spin, self.container_iou_spin, self.container_imgsz_spin,
                  self.padding_spin, self.damage_conf_spin, self.damage_iou_spin, self.damage_imgsz_spin):
            w.valueChanged.connect(self._on_params_changed)
        self.show_container_box_cb.toggled.connect(self._on_params_changed)
        self.show_labels_cb.toggled.connect(self._on_params_changed)
        self.show_conf_cb.toggled.connect(self._on_params_changed)
        self.cooldown_spin.valueChanged.connect(self._on_alert_params_changed)

    # ------------------------------------------------------------- models
    def _populate_models(self):
        models = find_weight_files(WEIGHTS_DIR)
        for combo in (self.container_model_combo, self.damage_model_combo):
            combo.blockSignals(True)
            combo.clear()
            if not models:
                combo.addItem("(Không tìm thấy .pt trong thư mục weights/)")
            else:
                for m in models:
                    combo.addItem(os.path.relpath(m, APP_DIR), m)
            combo.blockSignals(False)

        if models:
            damage_path = guess_weight_file(models, lambda n: "damage" in n)
            container_path = guess_weight_file(models, lambda n: "damage" not in n)
            self._select_combo_data(self.damage_model_combo, damage_path)
            self._select_combo_data(self.container_model_combo, container_path)

    @staticmethod
    def _select_combo_data(combo, path):
        if path is None:
            return
        idx = combo.findData(path)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def browse_model(self, combo):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn model .pt", WEIGHTS_DIR, "PyTorch model (*.pt)")
        if path:
            combo.addItem(os.path.relpath(path, APP_DIR) if path.startswith(APP_DIR) else path, path)
            combo.setCurrentIndex(combo.count() - 1)
            self._load_selected_model()

    def _load_selected_model(self):
        container_path = self.container_model_combo.currentData()
        damage_path = self.damage_model_combo.currentData()
        if not container_path or not os.path.exists(container_path):
            self.model_info_label.setText("Chưa chọn model Container hợp lệ")
            return
        if not damage_path or not os.path.exists(damage_path):
            self.model_info_label.setText("Chưa chọn model Damage hợp lệ")
            return
        device = self.device_combo.currentText()
        try:
            self.statusBar().showMessage(
                f"Đang nạp model {os.path.basename(container_path)} + "
                f"{os.path.basename(damage_path)} trên {device}..."
            )
            QApplication.processEvents()
            self.pipeline = ContainerDamagePipeline(container_path, damage_path, device=device)
            container_names = ", ".join(self.pipeline.container_names.values())
            damage_names = ", ".join(self.pipeline.damage_names.values())
            self.model_info_label.setText(
                f"Container model: {os.path.basename(container_path)}\n"
                f"  Lớp: {container_names}\n"
                f"Damage model: {os.path.basename(damage_path)}\n"
                f"  Lớp: {damage_names}\n"
                f"Device: {device}"
            )
            self.statusBar().showMessage("Nạp model thành công", 3000)
            self._on_params_changed()
            self._rerun_static_if_any()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi nạp model", str(e))
            self.statusBar().showMessage("Lỗi nạp model")

    def _on_params_changed(self):
        if self.pipeline is None:
            return
        self.pipeline.set_container_params(
            conf=self.container_conf_spin.value(),
            iou=self.container_iou_spin.value(),
            imgsz=self.container_imgsz_spin.value(),
        )
        self.pipeline.set_damage_params(
            conf=self.damage_conf_spin.value(),
            iou=self.damage_iou_spin.value(),
            imgsz=self.damage_imgsz_spin.value(),
        )
        self.pipeline.set_display_params(
            show_labels=self.show_labels_cb.isChecked(),
            show_conf=self.show_conf_cb.isChecked(),
            show_container_box=self.show_container_box_cb.isChecked(),
        )
        self.pipeline.set_padding_ratio(self.padding_spin.value() / 100.0)
        self._rerun_static_if_any()

    def _rerun_static_if_any(self):
        # if currently showing a static image, re-run detection with new params
        if self.current_pixmap_source == "image" and self.last_static_frame is not None and self.pipeline:
            try:
                detections, annotated = self.pipeline.predict(self.last_static_frame)
                self._show_frame(annotated)
                self._update_results_list(detections)
                self.fps_label.setText("FPS: - (ảnh tĩnh)")
                self._handle_damage_alerts(self.last_static_frame, detections)
            except Exception as e:
                self.statusBar().showMessage(f"Lỗi: {e}")

    def _on_alert_params_changed(self):
        self.alert_tracker.cooldown_seconds = self.cooldown_spin.value()

    # -------------------------------------------------------- damage alerts
    def _handle_damage_alerts(self, raw_frame, detections):
        if not self.show_popup_cb.isChecked():
            return
        for det in self.alert_tracker.filter_new(detections):
            crop = build_damage_snapshot(raw_frame, det)
            if crop.size == 0:
                continue
            popup = DamagePopup(crop, det, parent=self)
            self._position_popup(popup)
            self._damage_popups.append(popup)
            popup.destroyed.connect(lambda _=None, p=popup: self._on_popup_closed(p))
            popup.show()

    def _position_popup(self, popup):
        base = self.geometry()
        offset = (len(self._damage_popups) % 8) * 28
        popup.move(base.x() + 60 + offset, base.y() + 60 + offset)

    def _on_popup_closed(self, popup):
        self._damage_popups = [p for p in self._damage_popups if p is not popup]

    # ------------------------------------------------------------ actions
    def open_image(self):
        self.stop_stream()
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh", APP_DIR, "Images (*.png *.jpg *.jpeg *.jfif *.bmp *.webp)"
        )
        if not path:
            return
        if self.pipeline is None:
            QMessageBox.warning(self, "Chưa có model", "Vui lòng chọn model trước.")
            return
        frame = cv2.imread(path)
        if frame is None:
            QMessageBox.critical(self, "Lỗi", "Không đọc được ảnh.")
            return
        self.last_static_frame = frame
        self.current_pixmap_source = "image"
        self.alert_tracker.reset()
        detections, annotated = self.pipeline.predict(frame)
        self._show_frame(annotated)
        self._update_results_list(detections)
        self.fps_label.setText("FPS: - (ảnh tĩnh)")
        self.btn_save.setEnabled(True)
        self.status_label.setText(f"Ảnh: {os.path.basename(path)}")
        self._handle_damage_alerts(frame, detections)

    def open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn video", APP_DIR, "Videos (*.mp4 *.avi *.mov *.mkv)"
        )
        if not path:
            return
        self._start_stream(path, is_camera=False)
        self.status_label.setText(f"Video: {os.path.basename(path)}")

    def open_camera(self):
        idx = self.camera_index_spin.value()
        self._start_stream(idx, is_camera=True)
        self.status_label.setText(f"Camera index {idx}")

    def _start_stream(self, source, is_camera):
        if self.pipeline is None:
            QMessageBox.warning(self, "Chưa có model", "Vui lòng chọn model trước.")
            return
        self.stop_stream()
        self.current_pixmap_source = "camera" if is_camera else "video"
        self.alert_tracker.reset()
        self.worker = VideoWorker(self.pipeline, source, is_camera)
        self.worker.frame_ready.connect(self._on_frame_ready)
        self.worker.error_signal.connect(self._on_worker_error)
        self.worker.finished_signal.connect(self._on_worker_finished)
        self.worker.info_ready.connect(self._on_stream_info)
        self.worker.start()
        self.btn_stop.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.btn_record.setEnabled(True)

    def stop_stream(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(2000)
            self.worker = None
        self.btn_stop.setEnabled(False)
        self.btn_record.setEnabled(False)
        if self.is_recording:
            self._finalize_recording()

    def _on_stream_info(self, fps):
        self.record_fps = fps

    def _on_frame_ready(self, frame, annotated, detections, fps):
        self._show_frame(annotated)
        self._update_results_list(detections)
        self.fps_label.setText(f"FPS: {fps:.1f}")
        self.last_static_frame = annotated  # allow saving current frame
        self.btn_save.setEnabled(True)
        self._handle_damage_alerts(frame, detections)

        if self.is_recording and self.video_writer is not None:
            h, w = annotated.shape[:2]
            if (w, h) != self._record_size:
                # frame size changed mid-stream (shouldn't normally happen) - skip to avoid corrupting file
                return
            self.video_writer.write(annotated)

    def _on_worker_error(self, msg):
        QMessageBox.critical(self, "Lỗi luồng video", msg)
        self.stop_stream()

    def _on_worker_finished(self):
        self.btn_stop.setEnabled(False)
        self.btn_record.setEnabled(False)
        if self.is_recording:
            self._finalize_recording()
        self.statusBar().showMessage("Video kết thúc", 3000)

    def toggle_recording(self):
        if not self.is_recording:
            if self.worker is None or self.last_static_frame is None:
                QMessageBox.warning(self, "Không có stream", "Vui lòng mở video hoặc camera trước khi ghi.")
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Chọn nơi lưu video kết quả", os.path.join(OUTPUTS_DIR, "output.mp4"),
                "MP4 (*.mp4);;AVI (*.avi)"
            )
            if not path:
                return
            ext = os.path.splitext(path)[1].lower()
            if ext not in (".mp4", ".avi"):
                path += ".mp4"
                ext = ".mp4"
            fourcc = cv2.VideoWriter_fourcc(*("mp4v" if ext == ".mp4" else "XVID"))

            h, w = self.last_static_frame.shape[:2]
            writer = cv2.VideoWriter(path, fourcc, self.record_fps, (w, h))
            if not writer.isOpened():
                QMessageBox.critical(self, "Lỗi", "Không thể tạo file video output.")
                return

            self.video_writer = writer
            self._record_size = (w, h)
            self.record_path = path
            self.is_recording = True
            self.btn_record.setText("■ Dừng ghi")
            self.statusBar().showMessage(f"Đang ghi video vào {path} ({self.record_fps:.1f} fps)...")
        else:
            self._finalize_recording()

    def _finalize_recording(self):
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
        self.is_recording = False
        self.btn_record.setText("● Ghi video kết quả")
        if self.record_path:
            self.statusBar().showMessage(f"Đã lưu video: {self.record_path}", 5000)
            self.record_path = None

    def _update_results_list(self, detections):
        self.results_list.clear()
        containers = [d for d in detections if d.kind == "container"]
        damages = [d for d in detections if d.kind == "damage"]

        if not containers:
            self.results_list.addItem("Không phát hiện container nào.")
            return

        for idx, c in enumerate(containers):
            self.results_list.addItem(
                f"[Container #{idx}] conf={c.conf:.2f}  box={c.box}"
            )
            own_damages = [d for d in damages if d.container_idx == idx]
            if not own_damages:
                self.results_list.addItem("    (không phát hiện hư hỏng)")
            for d in own_damages:
                self.results_list.addItem(
                    f"    - {d.label}  conf={d.conf:.2f}  box={d.box}"
                )

    def _show_frame(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.display_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.display_label.setPixmap(pix)

    def save_result(self):
        if self.last_static_frame is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu kết quả", os.path.join(OUTPUTS_DIR, "result.png"),
            "PNG (*.png);;JPEG (*.jpg)"
        )
        if path:
            cv2.imwrite(path, self.last_static_frame)
            self.statusBar().showMessage(f"Đã lưu: {path}", 3000)

    def closeEvent(self, event):
        self.stop_stream()
        for popup in list(self._damage_popups):
            popup.close()
        super().closeEvent(event)
