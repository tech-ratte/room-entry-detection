"""Interactive ROI setup: draw door and presence regions on a live camera feed."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import PROJECT_ROOT as SRC_PROJECT_ROOT, save_roi_to_config
from src.config import load_config
from src.camera import Camera

# Re-export for consistency
PROJECT_ROOT = SRC_PROJECT_ROOT


class RoiSelector:
    def __init__(self, window_name: str) -> None:
        self._window = window_name
        self._drawing = False
        self._start: tuple[int, int] | None = None
        self._end: tuple[int, int] | None = None
        self._current_rect: tuple[int, int, int, int] | None = None

    def reset(self) -> None:
        self._drawing = False
        self._start = None
        self._end = None
        self._current_rect = None

    def on_mouse(self, event, x, y, _flags, _param) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self._drawing = True
            self._start = (x, y)
            self._end = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self._drawing:
            self._end = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self._drawing = False
            self._end = (x, y)
            if self._start is not None and self._end is not None:
                self._current_rect = self._normalize_rect(self._start, self._end)

    def _normalize_rect(
        self, p1: tuple[int, int], p2: tuple[int, int]
    ) -> tuple[int, int, int, int]:
        x1, y1 = p1
        x2, y2 = p2
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)
        return x, y, w, h

    @property
    def rect(self) -> tuple[int, int, int, int] | None:
        if self._drawing and self._start and self._end:
            return self._normalize_rect(self._start, self._end)
        return self._current_rect

    def draw(self, frame) -> None:
        rect = self.rect
        if rect is None:
            return
        x, y, w, h = rect
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)


def _load_or_create_config(config_path: Path) -> None:
    if config_path.is_file():
        return
    example = PROJECT_ROOT / "config.example.yaml"
    if not example.is_file():
        raise FileNotFoundError(f"Missing {example}")
    config_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Created {config_path} from config.example.yaml")


def _try_load_camera_config(config_path: Path):
    try:
        return load_config(config_path)
    except ValueError as exc:
        if "ntfy_topic" in str(exc):
            with config_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            data.setdefault("notify", {})["ntfy_topic"] = "setup-placeholder-topic"
            with config_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            return load_config(config_path)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Set door and presence ROIs from camera feed")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config.yaml",
        help="Config file to update (default: config.yaml)",
    )
    args = parser.parse_args()

    _load_or_create_config(args.config)
    config = _try_load_camera_config(args.config)

    window = "ROI Setup"
    camera = Camera(config.camera)
    if not camera.open():
        print("Could not open camera. Check USB connection and device_index.", file=sys.stderr)
        return 1

    selector = RoiSelector(window)
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, selector.on_mouse)

    door_roi: tuple[int, int, int, int] | None = None
    presence_roi: tuple[int, int, int, int] | None = None
    step = "door"

    print("Step 1: Drag to select DOOR region, then press Enter.")
    print("Step 2: Drag to select PRESENCE region (indoor side near door), then press Enter.")
    print("Press R to reset current step, Q/Esc to quit without saving.")

    try:
        while True:
            result = camera.read()
            if not result.ok or result.frame is None:
                continue

            display = result.frame.copy()
            if door_roi:
                x, y, w, h = door_roi
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(display, "door", (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            if presence_roi:
                x, y, w, h = presence_roi
                cv2.rectangle(display, (x, y), (x + w, y + h), (255, 165, 0), 2)
                cv2.putText(
                    display, "presence", (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2
                )

            selector.draw(display)
            label = "Select DOOR ROI" if step == "door" else "Select PRESENCE ROI"
            cv2.putText(
                display, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
            )
            cv2.imshow(window, display)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                print("Cancelled.")
                return 1
            if key in (ord("r"), ord("R")):
                selector.reset()
                if step == "presence":
                    presence_roi = None
                else:
                    door_roi = None
            if key in (13, 10):  # Enter
                rect = selector.rect
                if rect is None or rect[2] < 10 or rect[3] < 10:
                    print("Draw a larger rectangle first.")
                    continue
                if step == "door":
                    door_roi = rect
                    step = "presence"
                    selector.reset()
                    print("Step 2: Select PRESENCE region, then press Enter.")
                else:
                    presence_roi = rect
                    break
    finally:
        camera.close()
        cv2.destroyAllWindows()

    if door_roi is None or presence_roi is None:
        print("ROI selection incomplete.", file=sys.stderr)
        return 1

    save_roi_to_config(args.config, door_roi, presence_roi)
    print(f"Saved ROIs to {args.config}:")
    print(f"  door:     {list(door_roi)}")
    print(f"  presence: {list(presence_roi)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
