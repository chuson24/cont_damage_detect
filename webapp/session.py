"""Per-browser-session server-side state: the loaded pipeline and alert
tracker. A YOLO pipeline is expensive to load, so each session_id (one per
browser tab) keeps its own instance alive across requests instead of
reloading it per call."""
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Optional

from core.alert_tracker import DamageAlertTracker
from core.pipeline import ContainerDamagePipeline


@dataclass
class AppSession:
    pipeline: Optional[ContainerDamagePipeline] = None
    alert_tracker: DamageAlertTracker = field(default_factory=DamageAlertTracker)


class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, AppSession] = {}
        self._lock = Lock()

    def get_or_create(self, session_id: str) -> AppSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = AppSession()
                self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> Optional[AppSession]:
        return self._sessions.get(session_id)


sessions = SessionStore()
