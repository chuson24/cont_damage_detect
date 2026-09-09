# Deployment Guide

This guide covers building and packaging the Container Damage Detection app for Windows end-users using PyInstaller and Inno Setup.

## Prerequisites

- Windows 10/11 (build tested on Windows)
- Python 3.10+ (or version installed in development environment)
- PyInstaller (from dev environment)
- Inno Setup 6.x (ISCC.exe must be in PATH or manually specified)
- Git (for version tagging, optional)

## Step 1: Prepare Environment

```bash
# Clone/navigate to repo
cd cont_damage_detect

# Create virtual environment (if not already done)
python -m venv venv
.\venv\Scripts\activate

# Install dependencies (from pyproject.toml or requirements.txt)
pip install -r requirements.txt

# Verify key packages
python -c "import PyQt6, cv2, torch, ultralytics; print('OK')"
```

## Step 2: Build with PyInstaller

```bash
# Ensure weights/ and assets/ directories exist and contain:
#   weights/
#     ├── container.pt
#     └── damage.pt
#   assets/
#     ├── output.mp4
#     └── result_demo_video.png

# Run PyInstaller with app.spec config
pyinstaller app.spec --distpath dist --workpath build --noconfirm
```

**What happens**:
- Reads `app.spec` configuration
- Bundles PyQt6, OpenCV, CUDA-enabled torch, ultralytics, and all dependencies
- Copies `weights/` and `assets/` into bundled app
- Generates `dist/ContainerDamageDetection/` folder (one-directory mode)
- Creates `dist/ContainerDamageDetection/ContainerDamageDetection.exe` entry point

**Output**:
```
dist/
└── ContainerDamageDetection/
    ├── ContainerDamageDetection.exe
    ├── weights/
    │   ├── container.pt
    │   └── damage.pt
    ├── assets/
    │   ├── output.mp4
    │   └── result_demo_video.png
    ├── PyQt6/
    ├── cv2/
    ├── torch/
    ├── ... (many bundled libraries)
    └── _internal/
        └── (bundled dependencies)
```

**Notes on app.spec**:
- CUDA-enabled torch is specified via wheel URL in `datas` / hidden imports
- IPython, jedi, notebook, ipykernel are explicitly excluded (unused, long nested paths that can hit Windows MAX_PATH during installer build)
- Does **not** use UPX compression (can cause issues on some systems)

**Troubleshooting**:
- If weights files are missing: Verify `weights/` directory exists and contains `.pt` files
- If torch import fails: Try `pip install --upgrade torch` and re-run
- If build takes >5 minutes on first run: Normal (downloading torch wheels, analyzing dependencies)

## Step 3: Test Standalone Executable

Before packaging:

```bash
# Run the bundled exe directly
dist\ContainerDamageDetection\ContainerDamageDetection.exe

# Verify:
# ✓ App window appears
# ✓ No console errors
# ✓ "Mở ảnh..." button works (can browse for image)
# ✓ GPU detection runs and shows device list
```

If this works, proceed to installer step. If not, debug before building installer (easier to fix now).

## Step 4: Build Windows Installer with Inno Setup

```bash
# Ensure Inno Setup is installed and ISCC.exe is in PATH
# Or provide full path to ISCC.exe

cd <repo_root>

# Build installer
ISCC.exe installer.iss /DDistDir="<full_path_to_dist>\ContainerDamageDetection" /DOutputDir="<output_path>"

# Example (cmd):
ISCC.exe installer.iss /DDistDir="C:\Users\YourName\cont_damage_detect\dist\ContainerDamageDetection" /DOutputDir="C:\temp\installers"
```

**What happens**:
- Reads `installer.iss` configuration
- Copies bundled app to installer build
- Uses **zip compression** (NOT lzma2) — see important note below
- Generates installer executable: `ContainerDamageDetection_Installer.exe`

**Output**:
```
<output_path>/
└── ContainerDamageDetection_Installer.exe
```

**Compression note (CRITICAL)**:
- `installer.iss` specifies `Compression=zip` with `SolidCompression=no`
- **Do NOT change to lzma2**: Previous attempts with lzma2 compression (~38 min per build) silently dropped thousands of files, including model weights. Root cause: Windows Defender real-time scanning locks source files mid-read during long compression window, causing silent read failures. Shorter zip compression reduces that window.
- If you change this, expect build failures and missing weights in installer output.

## Step 5: Install & Test

```bash
# End-user installation
ContainerDamageDetection_Installer.exe

# Installer options:
# ✓ Per-user install (no admin needed)
# ✓ Install to: C:\Users\<user>\AppData\Local\Programs\ContainerDamageDetection
# ✓ Start menu shortcuts created
```

**Verify installation**:
```bash
# App should be in:
%LOCALAPPDATA%\Programs\ContainerDamageDetection\ContainerDamageDetection.exe

# Run it:
%LOCALAPPDATA%\Programs\ContainerDamageDetection\ContainerDamageDetection.exe

# Verify same as step 3:
# ✓ Window appears
# ✓ Models load (gpu_check.py runs, device list shown)
# ✓ Can load image and run detection
```

## GPU Bundling & Fallback

**How it works**:
1. `app.spec` bundles CUDA-enabled torch (PyTorch pre-built wheels with CUDA runtime)
2. At app startup, `core/gpu_check.py` validates each CUDA device:
   - `torch.cuda.is_available()` checks driver handshake
   - For each `cuda:N`, runs a tiny test op (e.g., `torch.ones(1).to(device)`)
   - If op fails (old driver, unsupported compute capability, device out of memory): device is dropped
   - Always includes "cpu" as fallback
3. GUI device dropdown auto-populates with working devices
4. Default selection: first CUDA device if available, else CPU

**Result**: App works on machines with/without NVIDIA GPU. No separate CPU-only build needed.

## Distributing the Installer

```bash
# The installer can be distributed via:
# - Direct file download (small enough for email/USB if ZIP'ed)
# - Windows installer hosting (inno setup supports auto-updates, but not configured here)
# - Software deployment tool (SCCM, Intune, etc.)

# File size: typically 500MB-1GB (depends on torch/weights size)
#   - torch pre-built wheel: ~300-400 MB (CUDA + CPU fallback)
#   - weights (container.pt + damage.pt): ~50-100 MB each
#   - OpenCV + PyQt6 + ultralytics: ~200-300 MB combined

# Estimate: 1-1.5 GB installer size
```

## Troubleshooting Build Issues

| Issue | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'PyQt6'` | Dependencies not installed | `pip install -r requirements.txt` |
| Installer size >2 GB | Unnecessary libraries bundled | Check `app.spec` excludes (IPython, jedi, etc.) |
| Weights missing in installer | Build interrupted or zip compressed wrong | Re-run ISCC.exe, ensure Compression=zip |
| App fails to start after install | Path issues, permissions | Check installer created files in `%LOCALAPPDATA%`, run app as same user |
| GPU not detected at runtime | CUDA not bundled, or old driver | Verify torch import `torch.cuda.is_available()`, check NVIDIA driver version |
| Detector models fail to load | Weights not found at expected path | Verify `weights/` bundled, `core/paths.py:app_root()` correctly resolves bundled location |

## Updating for New Releases

To create a new version:

1. **Update version in code** (if tracked in `main.py` or config):
   ```python
   APP_VERSION = "1.1.0"
   self.setWindowTitle(f"Container Damage Detection v{APP_VERSION}")
   ```

2. **Update weights** (if new models available):
   ```bash
   # Replace weights/container.pt and/or weights/damage.pt
   cp /path/to/new/container.pt weights/
   ```

3. **Re-build PyInstaller**:
   ```bash
   pyinstaller app.spec --distpath dist --workpath build --noconfirm
   ```

4. **Re-build Inno Setup installer** (same commands as step 4)

5. **Tag release in git** (optional but recommended):
   ```bash
   git tag -a v1.1.0 -m "Release 1.1.0: updated damage detection model"
   git push origin v1.1.0
   ```

6. **Publish installer** to distribution channel (download link, app store, etc.)

## CI/CD Integration

For automated building (see `docs/project-roadmap.md`):

```yaml
# .github/workflows/build-installer.yml (example)
on:
  push:
    tags: ['v*']

jobs:
  build-installer:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pyinstaller app.spec --distpath dist --workpath build --noconfirm
      - run: |
          choco install innosetup
          ISCC.exe installer.iss /DDistDir="${{ github.workspace }}\dist\ContainerDamageDetection" /DOutputDir="${{ github.workspace }}\output"
      - uses: actions/upload-artifact@v3
        with:
          name: installer
          path: output/ContainerDamageDetection_Installer.exe
```

## Related Documentation

- `docs/system-architecture.md` – GPU detection and device selection flow
- `docs/project-roadmap.md` – CI/CD pipeline (future)
- `app.spec` – PyInstaller configuration (source)
- `installer.iss` – Inno Setup configuration (source)
