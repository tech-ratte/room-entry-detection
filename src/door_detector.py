from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np
from skimage.metrics import structural_similarity

from src.config import DetectionConfig, RoiConfig

logger = logging.getLogger(__name__)


@dataclass
class DoorResult:
    is_open: bool
    ssim_score: float
    open_transition_started: bool = False
    reference_updated: bool = False


class DoorDetector:
    def __init__(self, roi: RoiConfig, detection: DetectionConfig, fps: int) -> None:
        self._door_roi = roi.door
        self._ssim_threshold = detection.door_ssim_threshold
        self._open_min_frames = detection.door_open_min_frames
        self._stable_frames_required = max(
            1, detection.door_closed_stable_seconds * fps
        )

        self._reference: np.ndarray | None = None
        self._open_candidate_frames = 0
        self._close_candidate_frames = 0
        self._stable_closed_frames = 0
        self._is_open = False

    @property
    def is_open(self) -> bool:
        return self._is_open

    def update(self, frame: np.ndarray) -> DoorResult:
        roi_image = self._extract_roi(frame)
        gray = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY)

        if self._reference is None:
            self._reference = gray.copy()
            logger.info("Door reference image initialized")
            return DoorResult(is_open=False, ssim_score=1.0)

        score = float(
            structural_similarity(self._reference, gray, data_range=255)
        )
        is_open_candidate = score < self._ssim_threshold
        open_transition_started = False
        reference_updated = False

        if self._is_open:
            if is_open_candidate:
                self._close_candidate_frames = 0
            else:
                self._close_candidate_frames += 1
                if self._close_candidate_frames >= self._open_min_frames:
                    self._is_open = False
                    self._close_candidate_frames = 0
                    self._open_candidate_frames = 0
                    self._stable_closed_frames = 0
        else:
            if is_open_candidate:
                self._open_candidate_frames += 1
                self._stable_closed_frames = 0
                if self._open_candidate_frames == 1:
                    open_transition_started = True
                if self._open_candidate_frames >= self._open_min_frames:
                    self._is_open = True
            else:
                self._open_candidate_frames = 0
                self._stable_closed_frames += 1
                if self._stable_closed_frames >= self._stable_frames_required:
                    self._reference = gray.copy()
                    self._stable_closed_frames = 0
                    reference_updated = True
                    logger.debug("Door reference image updated")

        return DoorResult(
            is_open=self._is_open,
            ssim_score=score,
            open_transition_started=open_transition_started,
            reference_updated=reference_updated,
        )

    def _extract_roi(self, frame: np.ndarray) -> np.ndarray:
        x, y, w, h = self._door_roi
        return frame[y : y + h, x : x + w]
