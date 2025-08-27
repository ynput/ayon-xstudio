"""Defines server settings for xstudio."""

from ayon_server.settings import (
    BaseSettingsModel,
    MultiplatformPathListModel,
    SettingsField,
)


class XStudioSettings(BaseSettingsModel):
    """xStudio addon settings."""

    enabled: bool = SettingsField(True)  # noqa: FBT003
    xstudio_path: MultiplatformPathListModel = SettingsField(
        title="xStudio paths",
        default_factory=MultiplatformPathListModel,
        scope=["studio"],
    )


DEFAULT_VALUES = {
    "enabled": True,
    "xstudio_path": {
        "windows": [
            "C:\\Program Files\\xSTUDIO.exe",
        ],
        "linux": [],
        "darwin": [
            "/Applications/xSTUDIO.app/Contents/MacOS/xstudio.bin",
        ],
    },
}
