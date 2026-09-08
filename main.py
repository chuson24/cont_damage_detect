"""
Container Damage Detection - PyQt6 GUI Demo/Test tool for YOLO (.pt) models.

Entry point only — all detection logic lives in `core/`, all UI code in
`gui/`. See gui/main_window.py and core/pipeline.py for the actual work.

Chạy: python main.py
"""
import sys

from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
