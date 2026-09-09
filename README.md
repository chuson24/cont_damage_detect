# Container Damage Detection

A PyQt6 desktop application demonstrating a two-stage YOLO detection pipeline for identifying shipping containers and classifying damage on them from static images, video files, or live camera feeds.

## Overview

This is a **demo and test tool** for evaluating container damage detection workflows. It features:

- **Two-stage detection**: First locates containers in a scene, then detects damage on each container by analyzing cropped regions
- **Real-time parameter tuning**: Adjust model confidence, IoU, inference resolution, and padding—results update instantly on the current frame
- **Multiple input sources**: Static images, pre-recorded videos, or live camera feeds
- **GPU auto-detection**: Automatically detects and uses available NVIDIA GPUs; falls back to CPU
- **Alert system**: Notifies on new damage detections; prevents spam via 5-second deduplication cooldown
- **Video recording**: Saves annotated detection output as MP4 files
- **Packaged installer**: Pre-built Windows executable with bundled dependencies (PyInstaller + Inno Setup)

All UI strings are in **Vietnamese** by design (target market).

## Quick Start

### For End-Users (Windows)

1. Download `ContainerDamageDetection_Installer.exe`
2. Run installer (no admin privileges required)
3. Launch from Start menu or `%LOCALAPPDATA%\Programs\ContainerDamageDetection`
4. Load an image, video, or camera feed and observe detection results

### For Developers (Local Setup)

```bash
# Clone repo
git clone <repo_url>
cd cont_damage_detect

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install PyQt6 opencv-python torch ultralytics numpy

# Run app
python main.py
```

**Note**: First run may take time downloading model weights and CUDA libraries.

### Web UI (browser-based, mirrors the desktop GUI)

A FastAPI + vanilla JS web app under `webapp/` offers the same functionality (image/video/webcam detection, live param tuning, damage alert popups) through a browser instead of PyQt6:

```bash
pip install -r webapp/requirements.txt   # fastapi/uvicorn, plus the core/ deps above
uvicorn webapp.server:app --reload
```

Then open `http://127.0.0.1:8000`. Recording downloads as `.webm` (browser `MediaRecorder` limitation) instead of `.mp4`/`.avi`.

## Documentation

- **[Project Overview & PDR](docs/project-overview-pdr.md)** – What this tool is, who it's for, scope, and requirements
- **[Codebase Summary](docs/codebase-summary.md)** – Directory structure, layer responsibilities, key classes
- **[Code Standards](docs/code-standards.md)** – Conventions (layer separation, naming, Vietnamese UI, no tests yet)
- **[System Architecture](docs/system-architecture.md)** – Two-stage pipeline flow, data paths, threading, GPU handling
- **[Project Roadmap](docs/project-roadmap.md)** – Recognized gaps (testing, CI/CD, linting, dependency pinning)
- **[Deployment Guide](docs/deployment-guide.md)** – Building with PyInstaller and packaging with Inno Setup

## Structure

```
cont_damage_detect/
├── core/                 # Pure detection logic (zero Qt dependency)
│   ├── detector.py       # Two-stage YOLO inference
│   ├── pipeline.py       # Facade for GUI/CLI
│   ├── alert_tracker.py  # Deduplication for video alerts
│   └── ...
├── gui/                  # PyQt6 UI
│   ├── main_window.py    # Main application window
│   ├── video_worker.py   # Off-UI-thread inference
│   └── damage_popup.py   # Alert popup dialog
├── webapp/               # FastAPI + vanilla JS web UI (browser alternative to gui/)
│   ├── server.py         # REST + WebSocket endpoints
│   └── static/           # index.html / app.css / app.js
├── main.py              # Entry point
├── weights/             # YOLO model files (bundled in packaged app)
├── assets/              # Demo media
├── app.spec             # PyInstaller configuration
├── installer.iss        # Inno Setup configuration
└── docs/                # Documentation
```

## Technical Highlights

- **Clean architecture**: Core detection logic has zero Qt dependency; can be reused in CLI or headless batch processing
- **Efficient batching**: All container crops from a frame are processed in a single damage-model inference call
- **GPU auto-detection**: Validates CUDA capability with actual test operations, not just driver checks
- **Thread-safe UI**: Video/camera processing runs on separate thread; UI stays responsive
- **Vietnamese-first design**: UI strings in Vietnamese throughout (not i18n, but deliberate by product scope)

## Current Limitations

- **Single-threaded inference**: Processes one frame at a time (sufficient for demo; not suitable for multi-stream production deployments)
- **No persistent storage**: Detections not saved to database; users can save annotated frames/videos only
- **Demo scope**: No compliance-grade audit trail or inspection record system
- **No automated tests**: Functional testing done manually; see roadmap for future test coverage

## Building for Distribution

To create a standalone Windows installer:

```bash
# 1. Build with PyInstaller
pyinstaller app.spec --distpath dist --workpath build --noconfirm

# 2. Package with Inno Setup
ISCC.exe installer.iss /DDistDir="<dist_path>" /DOutputDir="<output_path>"
```

See [Deployment Guide](docs/deployment-guide.md) for detailed steps, troubleshooting, and CI/CD integration.

## Dependencies

- **PyQt6** – GUI framework
- **OpenCV (cv2)** – Image/video I/O
- **PyTorch** – Deep learning backbone (CUDA or CPU)
- **Ultralytics** – YOLO model management
- **NumPy** – Array operations (implicitly via torch/cv2)

No `requirements.txt` or `pyproject.toml` exists yet; see [roadmap](docs/project-roadmap.md) for future work.

## Known Issues & Roadmap

- No automated test suite (work in progress)
- No CI/CD pipeline
- Dependencies not pinned in `pyproject.toml`
- No linting or type checking config

See [Project Roadmap](docs/project-roadmap.md) for detailed gaps and next steps.

## License & Attribution

Built as a demo/test tool for container damage detection evaluation.

## Support

For issues, questions, or feature requests, refer to:
- Code documentation: See `/docs` directory
- User guide (Vietnamese): `docs/HuongDanSuDung_ContainerDamageDetection.pdf`
- Troubleshooting: [Deployment Guide](docs/deployment-guide.md#troubleshooting-build-issues)
