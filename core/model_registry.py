"""Discovering and picking YOLO .pt weight files on disk (pure, no GUI)."""
import glob
import os
from typing import Callable, List, Optional


def find_weight_files(root: str) -> List[str]:
    return sorted(glob.glob(os.path.join(root, "**", "*.pt"), recursive=True))


def guess_weight_file(paths: List[str], predicate: Callable[[str], bool]) -> Optional[str]:
    """Return the first path whose lowercase basename satisfies `predicate`,
    falling back to the first path if none match."""
    for path in paths:
        if predicate(os.path.basename(path).lower()):
            return path
    return paths[0] if paths else None
