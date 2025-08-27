"""Declare the xStudio Addon."""

import os

from ayon_core.addon import AYONAddon, IPluginPaths

from .constants import ADDON_NAME, XSTUDIO_ROOT
from .version import __version__


class XStudioAddon(AYONAddon, IPluginPaths):
    """Addon adds xstudio functionality via plugins."""

    name = ADDON_NAME  # type: ignore  # noqa: PGH003
    version = __version__  # type: ignore  # noqa: PGH003

    def get_plugin_paths(self):  # noqa: ANN201, D102
        return {"load": self.get_load_plugin_paths()}

    def get_load_plugin_paths(self, host_name=None):  # noqa: ANN001, ANN201, D102, PLR6301
        return [
            os.path.join(XSTUDIO_ROOT, "plugins", "load"),
        ]

    def get_ftrack_event_handler_paths(self):  # noqa: ANN201, D102, PLR6301
        return {
            "user": [
                os.path.join(XSTUDIO_ROOT, "plugins", "ftrack"),
            ]
        }
