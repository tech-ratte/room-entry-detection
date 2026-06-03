from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class CameraConfig:
    device_index: int
    width: int
    height: int
    fps: int


@dataclass(frozen=True)
class RoiConfig:
    door: tuple[int, int, int, int]
    presence: tuple[int, int, int, int]


@dataclass(frozen=True)
class DetectionConfig:
    door_ssim_threshold: float
    door_open_min_frames: int
    door_closed_stable_seconds: int
    motion_pixel_ratio_threshold: float
    motion_lookback_seconds: float
    alert_cooldown_seconds: int


@dataclass(frozen=True)
class NotifyConfig:
    ntfy_topic: str
    sound_path: Path
    entry_message: str


@dataclass(frozen=True)
class DebugConfig:
    show_preview: bool
    log_level: str


@dataclass(frozen=True)
class AppConfig:
    camera: CameraConfig
    roi: RoiConfig
    detection: DetectionConfig
    notify: NotifyConfig
    debug: DebugConfig
    config_path: Path


def _require_section(data: dict[str, Any], key: str) -> dict[str, Any]:
    section = data.get(key)
    if not isinstance(section, dict):
        raise ValueError(f"Config section '{key}' is missing or invalid")
    return section


def _parse_roi(value: Any, name: str) -> tuple[int, int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"roi.{name} must be [x, y, w, h]")
    x, y, w, h = (int(v) for v in value)
    if w <= 0 or h <= 0:
        raise ValueError(f"roi.{name} width and height must be positive")
    return x, y, w, h


def load_config(config_path: Path | str | None = None) -> AppConfig:
    path = Path(config_path) if config_path else PROJECT_ROOT / "config.yaml"
    if not path.is_file():
        example = PROJECT_ROOT / "config.example.yaml"
        raise FileNotFoundError(
            f"Config not found: {path}. Copy {example.name} to config.yaml and edit it."
        )

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    camera_data = _require_section(data, "camera")
    roi_data = _require_section(data, "roi")
    detection_data = _require_section(data, "detection")
    notify_data = _require_section(data, "notify")
    debug_data = _require_section(data, "debug")

    sound_path = Path(notify_data.get("sound_path", "assets/alert.wav"))
    if not sound_path.is_absolute():
        sound_path = PROJECT_ROOT / sound_path

    ntfy_topic = str(notify_data.get("ntfy_topic", "")).strip()
    if not ntfy_topic or ntfy_topic == "your-secret-topic-here":
        raise ValueError("notify.ntfy_topic must be set to your ntfy.sh topic name")

    return AppConfig(
        camera=CameraConfig(
            device_index=int(camera_data.get("device_index", 0)),
            width=int(camera_data.get("width", 640)),
            height=int(camera_data.get("height", 480)),
            fps=int(camera_data.get("fps", 10)),
        ),
        roi=RoiConfig(
            door=_parse_roi(roi_data.get("door"), "door"),
            presence=_parse_roi(roi_data.get("presence"), "presence"),
        ),
        detection=DetectionConfig(
            door_ssim_threshold=float(detection_data.get("door_ssim_threshold", 0.82)),
            door_open_min_frames=int(detection_data.get("door_open_min_frames", 5)),
            door_closed_stable_seconds=int(
                detection_data.get("door_closed_stable_seconds", 30)
            ),
            motion_pixel_ratio_threshold=float(
                detection_data.get("motion_pixel_ratio_threshold", 0.02)
            ),
            motion_lookback_seconds=float(
                detection_data.get("motion_lookback_seconds", 5)
            ),
            alert_cooldown_seconds=int(
                detection_data.get("alert_cooldown_seconds", 60)
            ),
        ),
        notify=NotifyConfig(
            ntfy_topic=ntfy_topic,
            sound_path=sound_path,
            entry_message=str(
                notify_data.get("entry_message", "ドアが開きました（外からの入室）")
            ).strip()
            or "ドアが開きました（外からの入室）",
        ),
        debug=DebugConfig(
            show_preview=bool(debug_data.get("show_preview", False)),
            log_level=str(debug_data.get("log_level", "INFO")).upper(),
        ),
        config_path=path.resolve(),
    )


def save_roi_to_config(
    config_path: Path,
    door: tuple[int, int, int, int],
    presence: tuple[int, int, int, int],
) -> None:
    if config_path.is_file():
        with config_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        example = PROJECT_ROOT / "config.example.yaml"
        with example.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    data.setdefault("roi", {})
    data["roi"]["door"] = list(door)
    data["roi"]["presence"] = list(presence)

    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
