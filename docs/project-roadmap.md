# Project Roadmap

This roadmap focuses on **observed gaps and next steps** grounded in the codebase. It does not invent features; it documents recognized limitations and potential improvements that would move the app closer to production readiness.

## Current State

- **Functional**: Two-stage YOLO detection pipeline working; UI responsive; video/camera support functional
- **Demo/test tool**: By design, not a production inspection system
- **Packaged for Windows**: PyInstaller + Inno Setup working
- **No test suite, CI, or dependency pinning**: Critical gaps for maintenance

## Recognized Gaps

### High Priority

#### 1. Dependency Version Pinning

**Gap**: No `requirements.txt` or `pyproject.toml`. Runtime dependencies inferred from imports only.

- PyQt6 (GUI)
- opencv-python (image/video I/O)
- torch (YOLO backbone, GPU support)
- ultralytics (YOLO model loading)
- numpy (array operations)

**Impact**: 
- Cannot reproduce exact build environment on another machine
- CI/CD impossible without manual version specification
- New developer onboarding unclear on setup

**Next steps**:
1. Create `pyproject.toml` with version constraints (recommend: test with latest stable versions first, then pin)
2. Create `.venv` development environment; document setup in `README.md`
3. Document CUDA version assumption (currently bundled in app.spec wheel URLs)

#### 2. Automated Testing

**Gap**: Zero tests. Functional testing is manual only.

**Coverage needed**:
- Unit tests for core logic:
  - Two-stage pipeline inference (containers then damage)
  - Geometry helpers: `expand_box()`, `iou()`
  - Alert tracker deduplication (same damage re-detection)
  - Model registry heuristics (guess container vs damage model)
  - GPU device validation fallback
- Integration tests:
  - End-to-end: load image → detect → annotate → save
  - Video playback and recording (MP4 output validity)
  - Camera input simulation (mocked cv2.VideoCapture)
- GUI tests (optional for prototype, but helpful for regression):
  - Parameter change → re-run inference on static image
  - Alert popup shown on new damage

**Next steps**:
1. Add `pytest` to dev dependencies
2. Start with core logic tests (highest ROI)
3. Mock cv2.VideoCapture for video tests
4. CI workflow: run tests on each push/PR

#### 3. CI/CD Pipeline

**Gap**: No GitHub Actions or similar CI.

**Missing**:
- Tests run on every push
- Linting / type checking on PRs
- Build artifact generation (Windows installer) on tagged releases
- Security scanning (SAST)

**Next steps**:
1. Create `.github/workflows/test.yml`:
   - Install dependencies from pyproject.toml
   - Run pytest
   - Run mypy (type checking)
   - Run pylint or black (linting)
2. Create `.github/workflows/build-installer.yml`:
   - Trigger on version tags (e.g., `v1.1.0`)
   - Run `pyinstaller app.spec`
   - Run `ISCC.exe installer.iss`
   - Upload Windows installer as release artifact

#### 4. Linting & Type Checking

**Gap**: No `mypy`, `pylint`, `black`, `isort` configuration.

**Status**: Code follows PEP 8 informally; type hints present but not enforced.

**Next steps**:
1. Add `pyproject.toml` configuration for `mypy` (strict mode)
2. Add `pylint` or `ruff` config
3. Add `black` config (enforce consistent formatting)
4. Integrate into CI (fail on lint errors)

#### 5. Pre-commit Hooks

**Gap**: Secrets, lint errors, common mistakes not automatically caught.

**Current risk**:
- Model weights (*.pt files) could be accidentally added to git (large file warning)
- Secrets in code could be committed

**Next steps**:
1. Add `.pre-commit-config.yaml`:
   - Check for secrets (detect-secrets)
   - Check for large files
   - Run mypy, black, pylint
   - Check for trailing whitespace
2. Document: `pre-commit install` in developer setup guide

#### 6. Documentation of Build Process

**Gap**: PyInstaller and Inno Setup steps are not documented in the codebase.

**Current**: Only `app.spec` and `installer.iss` exist; no README for developers on how to build the installer.

**Next steps**:
1. Create `docs/deployment-guide.md` (in progress; see separate doc)
2. Add build instructions to root `README.md`
3. Document CUDA bundling approach (why it's needed, how to update)

### Medium Priority

#### 7. Structured Logging

**Gap**: No logging framework. Errors printed to console only.

**Impact**: 
- Difficult to debug issues in packaged app (where console is invisible)
- No audit trail of user actions (fine for demo, but an issue for inspection records)

**Next steps** (if moving toward production):
1. Add `logging` configuration (Python stdlib is sufficient)
2. Log to file in `user_data_dir()` so packaged app errors are visible
3. Document log file location in help / troubleshooting

#### 8. Configuration File

**Gap**: All model paths, parameters, and settings are hardcoded or UI-only.

**Impact**: 
- Cannot pre-configure app for specific use cases (e.g., customer A wants different alert cooldown, higher confidence threshold)
- No persistent state (e.g., remember last model selection, last video source across restarts)

**Next steps** (if needed):
1. Create `config.json` in `user_data_dir()`
2. Store: last-used models, confidence/iou/imgsz per stage, alert cooldown, camera index
3. Load on startup; save on exit

#### 9. Multi-Language Support

**Gap**: UI is Vietnamese only.

**Current design**: Intentional (target market is Vietnamese-speaking). Not a gap if scope is constrained.

**Next steps** (if expanding to other markets):
1. Extract UI strings to `i18n/` directory
2. Use Qt translation system (`.ts` / `.qm` files)
3. Dynamically load translation at startup based on OS locale or user preference

#### 10. Performance Benchmarking

**Gap**: No performance metrics. Frame rate, GPU utilization, memory usage not tracked.

**Current**: Anecdotal: "fast enough for demo"

**Next steps** (if deploying to resource-constrained devices):
1. Add performance telemetry: FPS, inference latency per stage, memory peak
2. Profile with `py-spy` or `cProfile` on CPU and GPU
3. Identify bottlenecks (usually GPU transfer or model size)
4. Consider model quantization or model swapping for low-end GPUs

### Low Priority

#### 11. Error Recovery

**Gap**: If model loading fails or YOLO inference throws an exception, app may hang or crash.

**Next steps**:
1. Wrap model loading in try-except with user-friendly error messages
2. Graceful fallback: if damage model fails, show containers only
3. User can recover (retry, select different weights) without restarting app

#### 12. Developer Onboarding

**Gap**: No developer setup guide, no architecture walkthrough for new contributors.

**Current**: This documentation set partially addresses it.

**Next steps**:
1. Add `CONTRIBUTING.md` with:
   - Environment setup (Python, virtual env, dependencies)
   - Running the app locally
   - Running tests
   - Building the installer
   - PR review criteria

#### 13. Release Notes / Changelog

**Gap**: Git history is minimal (2 commits); no CHANGELOG.md.

**Next steps**:
1. Create `CHANGELOG.md` with release history and notes
2. Follow Semantic Versioning: v1.0.0 (current), v1.1.0 (next with fixes), v2.0.0 (breaking changes)
3. Document: features added, bugs fixed, breaking changes per version

### Non-Issues (By Design)

- **i18n/multi-language**: Vietnamese UI is intentional per product scope
- **Production inspection system**: Demo tool as scoped; not seeking compliance/audit trail features
- **Real-time multi-GPU/distributed**: Single-threaded per-frame inference sufficient for intended use
- **Database of detections**: Out of scope; users can save annotated frames/videos
- **Mobile app**: Desktop only

## Timeline Suggestion

If maintaining and evolving this project:

1. **Phase 1 (Now)**: Dependency pinning + basic pytest setup (~1-2 days)
2. **Phase 2 (Next sprint)**: CI/CD + linting/type checking (~2-3 days)
3. **Phase 3 (Sprint after)**: Pre-commit hooks + error recovery (~1 day)
4. **Phase 4 (Ongoing)**: Performance benchmarking, logging, config files as needed per use cases

## Related Documentation

- `docs/deployment-guide.md` – Build/package steps
- `docs/code-standards.md` – Current conventions and testing notes
- `README.md` – Developer quick start (to be updated)
