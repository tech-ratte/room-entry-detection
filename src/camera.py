from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import cv2
import numpy as np

from src.config import CameraConfig

logger = logging.getLogger(__name__)


@dataclass
class FrameResult:
    ok: bool
    frame: np.ndarray | None = None


class Camera:
    def __init__(self, config: CameraConfig) -> None:
        self._config = config
        self._capture: cv2.VideoCapture | None = None
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 30.0

    def open(self) -> bool:
        self.close()
        capture = cv2.VideoCapture(self._config.device_index, cv2.CAP_DMSHOW)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.height)
        capture.set(cv2.CAP_PROP_FPS, self._config.fps)

        if not capture.isOpened():
            logger.error("Failed to open camera index %s", self._config.device_index)
            return False

        self._capture = capture
        self._reconnect_delay = 1.0
        logger.info(
            "Camera opened (index=%s, %sx%s @ %sfps)",
            self._config.device_index,
            self._config.width,
            self._config.height,
            self._config.fps,
        )
        return True

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def read(self) -> FrameResult:
        if self._capture is None or not self._capture.isOpened():
            if not self._try_reconnect():
                return FrameResult(ok=False)

        assert self._capture is not None
        ok, frame = self._capture.read()
        if not ok or frame is None:
            logger.warning("Frame read failed, reconnecting...")
            self.close()
            if not self._try_reconnect():
                return FrameResult(ok=False)
            ok, frame = self._capture.read()
            if not ok or frame is None:
                return FrameResult(ok=False)

        return FrameResult(ok=True, frame=frame)

    def _try_reconnect(self) -> bool:
        logger.info("Reconnecting to camera in %.1fs...", self._reconnect_delay)
        time.sleep(self._reconnect_delay)
        self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
        return self.open()

    def __enter__(self) -> Camera:
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
