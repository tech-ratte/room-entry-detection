from __future__ import annotations

import logging
from pathlib import Path

import requests
import winsound

from src.state_machine import EntryEvent

logger = logging.getLogger(__name__)

NTFY_URL = "https://ntfy.sh"
ENTRY_MESSAGE = "ドアが開きました（外からの入室）"
ENTRY_TITLE = "RoomEntryDetection"


class Notifier:
    def __init__(self, *, ntfy_topic: str, sound_path: Path) -> None:
        self._ntfy_topic = ntfy_topic
        self._sound_path = sound_path

    def notify_entry(self, event: EntryEvent) -> None:
        self._play_sound()
        self._send_ntfy(event)

    def _play_sound(self) -> None:
        try:
            if self._sound_path.is_file():
                winsound.PlaySound(
                    str(self._sound_path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC,
                )
                logger.info("Played alert sound: %s", self._sound_path)
            else:
                winsound.Beep(1000, 500)
                logger.info("Played system beep (alert.wav not found)")
        except Exception:
            logger.exception("Failed to play alert sound")

    def _send_ntfy(self, event: EntryEvent) -> None:
        url = f"{NTFY_URL}/{self._ntfy_topic}"
        headers = {
            "Title": ENTRY_TITLE,
            "Tags": "door,warning",
            "Priority": "high",
        }
        body = (
            f"{ENTRY_MESSAGE}\n"
            f"SSIM: {event.ssim_score:.3f}, motion_ratio: {event.motion_ratio:.4f}"
        )
        try:
            response = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=10)
            response.raise_for_status()
            logger.info("ntfy notification sent to topic '%s'", self._ntfy_topic)
        except Exception:
            logger.exception("Failed to send ntfy notification")
