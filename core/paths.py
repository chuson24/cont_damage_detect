"""Resolves file paths that work both running from source and frozen into
a standalone PyInstaller executable.

Bundled read-only resources (weights/, assets/) live next to the app;
anything the app writes at runtime (saved images, recorded videos) must
go to a per-user writable folder instead, since a frozen install commonly
lives under Program Files where a normal user has no write access.
"""
import os
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_root() -> str:
    """Directory containing bundled resources (weights/, assets/)."""
    if is_frozen():
        # onedir builds ship resources next to the exe; onefile builds
        # extract them under sys._MEIPASS at startup.
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_dir() -> str:
    """Writable per-user directory for outputs (saved images/videos)."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "ContainerDamageDetection")
    os.makedirs(path, exist_ok=True)
    return path
