from __future__ import annotations

import logging
import threading
from pathlib import Path

import requests
import winsound

from src.state_machine import EntryEvent

logger = logging.getLogger(__name__)

NTFY_URL = "https://ntfy.sh"
ENTRY_TITLE = "RoomEntryDetection"


class Notifier:
    def __init__(
        self, *, ntfy_topic: str, sound_path: Path, entry_message: str
    ) -> None:
        self._ntfy_topic = ntfy_topic
        self._sound_path = sound_path
        self._entry_message = entry_message
        self._sound_data: bytes | None = None
        self._sound_lock = threading.Lock()

        if self._sound_path.is_file():
            self._sound_data = self._sound_path.read_bytes()
            logger.info("Preloaded alert sound (%d bytes)", len(self._sound_data))
        else:
            logger.info("Alert sound not found, will use system beep: %s", self._sound_path)

    def notify_entry(self, event: EntryEvent) -> None:
        self._play_sound()
        self._send_ntfy(event)

    def _play_sound(self) -> None:
        try:
            if self._sound_data is not None:
                threading.Thread(
                    target=self._play_sound_blocking,
                    daemon=True,
                    name="alert-sound",
                ).start()
                logger.info("Playing alert sound from memory")
            else:
                winsound.Beep(1000, 500)
                logger.info("Played system beep (alert.wav not found)")
        except Exception:
            logger.exception("Failed to play alert sound")

    def _play_sound_blocking(self) -> None:
        with self._sound_lock:
            winsound.PlaySound(None, winsound.SND_PURGE)
            winsound.PlaySound(
                self._sound_data,
                winsound.SND_MEMORY | winsound.SND_NODEFAULT,
            )

    def _send_ntfy(self, event: EntryEvent) -> None:
        url = f"{NTFY_URL}/{self._ntfy_topic}"
        headers = {
            "Title": ENTRY_TITLE,
            "Tags": "door,warning",
            "Priority": "high",
        }
        body = (
            f"{self._entry_message}\n"
            f"SSIM: {event.ssim_score:.3f}, motion_ratio: {event.motion_ratio:.4f}"
        )
        try:
            response = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=10)
            response.raise_for_status()
            logger.info("ntfy notification sent to topic '%s'", self._ntfy_topic)
        except Exception:
            logger.exception("Failed to send ntfy notification")
