"""Declare the xStudio Addon."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from ayon_core.addon import AYONAddon, IPluginPaths

from .constants import ADDON_NAME, XSTUDIO_ROOT
from .version import __version__


class XStudioAddon(AYONAddon, IPluginPaths):
    """Addon adds xstudio functionality via plugins."""

    name = ADDON_NAME  # type: ignore  # noqa: PGH003
    version = __version__  # type: ignore  # noqa: PGH003

    def get_plugin_paths(self) -> Dict[str, List[str]]:
        """Get plugin paths for the addon.

        Returns:
            Dict[str, List[str]]: A dictionary with plugin paths.
        """
        return {"load": self.get_load_plugin_paths()}

    def get_load_plugin_paths(
        self, host_name: Optional[str] = None
    ) -> List[str]:
        """Get load plugin paths.

        Args:
            host_name: Optional host name to filter paths.

        Returns:
            List[str]: List of load plugin paths.
        """
        return [
            os.path.join(XSTUDIO_ROOT, "plugins", "load"),
        ]

    def get_ftrack_event_handler_paths(self) -> Dict[str, List[str]]:  # noqa: PLR6301
        """Get ftrack event handler paths.

        Returns:
            Dict[str, List[str]]: A dictionary with ftrack event handler paths.
        """
        return {
            "user": [
                os.path.join(XSTUDIO_ROOT, "plugins", "ftrack"),
            ]
        }
