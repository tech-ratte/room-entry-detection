from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import cv2

from src.camera import Camera
from src.config import AppConfig, load_config
from src.door_detector import DoorDetector
from src.notifier import Notifier
from src.presence_detector import PresenceDetector
from src.state_machine import EntryStateMachine

logger = logging.getLogger(__name__)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _draw_overlay(frame, config: AppConfig, door, presence) -> None:
    dx, dy, dw, dh = config.roi.door
    px, py, pw, ph = config.roi.presence

    door_color = (0, 0, 255) if door.is_open else (0, 255, 0)
    cv2.rectangle(frame, (dx, dy), (dx + dw, dy + dh), door_color, 2)
    cv2.putText(
        frame,
        f"door SSIM={door.ssim_score:.3f}",
        (dx, max(dy - 8, 15)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        door_color,
        1,
    )

    presence_color = (0, 165, 255) if presence.has_recent_motion else (255, 165, 0)
    cv2.rectangle(frame, (px, py), (px + pw, py + ph), presence_color, 2)
    cv2.putText(
        frame,
        f"presence motion={presence.motion_ratio:.3f}",
        (px, max(py - 8, 15)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        presence_color,
        1,
    )

    status = "OPEN" if door.is_open else "CLOSED"
    motion_label = "recent_motion" if presence.has_recent_motion else "clear"
    cv2.putText(
        frame,
        f"{status} | {motion_label}",
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )


def run(config: AppConfig) -> int:
    camera = Camera(config.camera)
    if not camera.open():
        logger.error("Could not open camera. Check device_index and USB connection.")
        return 1

    door_detector = DoorDetector(config.roi, config.detection, config.camera.fps)
    presence_detector = PresenceDetector(
        config.roi, config.detection, config.camera.fps
    )
    state_machine = EntryStateMachine(
        alert_cooldown_seconds=config.detection.alert_cooldown_seconds,
    )
    notifier = Notifier(
        ntfy_topic=config.notify.ntfy_topic,
        sound_path=config.notify.sound_path,
        entry_message=config.notify.entry_message,
    )

    frame_interval = 1.0 / config.camera.fps
    logger.info("Monitoring started (preview=%s)", config.debug.show_preview)

    try:
        while True:
            loop_start = time.perf_counter()
            result = camera.read()
            if not result.ok or result.frame is None:
                time.sleep(1.0)
                continue

            frame = result.frame
            door_result = door_detector.update(frame)
            presence_result = presence_detector.update(
                frame, door_closed=not door_result.is_open
            )
            entry_event = state_machine.update(door_result, presence_result)

            if entry_event is not None:
                notifier.notify_entry(entry_event)

            if config.debug.show_preview:
                display = frame.copy()
                _draw_overlay(display, config, door_result, presence_result)
                cv2.imshow("RoomEntryDetection", display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    logger.info("Quit requested from preview window")
                    break

            elapsed = time.perf_counter() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        camera.close()
        if config.debug.show_preview:
            cv2.destroyAllWindows()

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Door entry detection (intercom replacement)")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: ./config.yaml)",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    _setup_logging(config.debug.log_level)
    return run(config)


if __name__ == "__main__":
    raise SystemExit(main())
