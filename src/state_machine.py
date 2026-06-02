from __future__ import annotations

import logging
from dataclasses import dataclass
from time import monotonic

from src.door_detector import DoorResult
from src.presence_detector import PresenceResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EntryEvent:
    ssim_score: float
    motion_ratio: float


class EntryStateMachine:
    """Fires EntryEvent when door opens with no recent motion near the door (external entry)."""

    def __init__(self, *, alert_cooldown_seconds: int) -> None:
        self._alert_cooldown_seconds = alert_cooldown_seconds
        self._was_door_open = False
        self._motion_at_open_start = False
        self._last_alert_time: float | None = None

    def update(
        self,
        door: DoorResult,
        presence: PresenceResult,
    ) -> EntryEvent | None:
        if door.open_transition_started:
            self._motion_at_open_start = presence.has_recent_motion
            logger.debug(
                "Door open transition started (motion_at_start=%s)",
                self._motion_at_open_start,
            )

        event: EntryEvent | None = None
        if door.is_open and not self._was_door_open:
            event = self._evaluate_entry(door, presence)

        self._was_door_open = door.is_open
        return event

    def _evaluate_entry(
        self,
        door: DoorResult,
        presence: PresenceResult,
    ) -> EntryEvent | None:
        if self._motion_at_open_start:
            logger.info(
                "Door opened but motion was detected beforehand — treating as exit (suppressed)"
            )
            return None

        now = monotonic()
        if (
            self._last_alert_time is not None
            and now - self._last_alert_time < self._alert_cooldown_seconds
        ):
            logger.info("Entry detected but alert cooldown is active — suppressed")
            return None

        self._last_alert_time = now
        logger.info("External entry detected (door opened, no prior motion)")
        return EntryEvent(ssim_score=door.ssim_score, motion_ratio=presence.motion_ratio)
