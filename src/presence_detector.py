from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import monotonic

import cv2
import numpy as np

from src.config import DetectionConfig, RoiConfig


@dataclass
class PresenceResult:
    motion_detected: bool
    motion_ratio: float
    has_recent_motion: bool


class PresenceDetector:
    def __init__(self, roi: RoiConfig, detection: DetectionConfig, fps: int) -> None:
        self._presence_roi = roi.presence
        self._motion_threshold = detection.motion_pixel_ratio_threshold
        self._lookback_seconds = detection.motion_lookback_seconds

        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=16, detectShadows=False
        )
        max_entries = max(1, int(self._lookback_seconds * fps) + 1)
        self._motion_history: deque[tuple[float, bool]] = deque(maxlen=max_entries)

    def update(self, frame: np.ndarray, *, door_closed: bool) -> PresenceResult:
        if not door_closed:
            self._record_motion(False)
            return PresenceResult(
                motion_detected=False,
                motion_ratio=0.0,
                has_recent_motion=self._has_recent_motion(),
            )

        roi_image = self._extract_roi(frame)
        fg_mask = self._subtractor.apply(roi_image)
        _, binary = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        motion_ratio = float(np.count_nonzero(binary)) / binary.size
        motion_detected = motion_ratio >= self._motion_threshold

        self._record_motion(motion_detected)
        return PresenceResult(
            motion_detected=motion_detected,
            motion_ratio=motion_ratio,
            has_recent_motion=self._has_recent_motion(),
        )

    def reset_background(self) -> None:
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=16, detectShadows=False
        )
        self._motion_history.clear()

    def _record_motion(self, motion_detected: bool) -> None:
        self._motion_history.append((monotonic(), motion_detected))

    def _has_recent_motion(self) -> bool:
        cutoff = monotonic() - self._lookback_seconds
        return any(ts >= cutoff and motion for ts, motion in self._motion_history)

    def _extract_roi(self, frame: np.ndarray) -> np.ndarray:
        x, y, w, h = self._presence_roi
        return frame[y : y + h, x : x + w]
