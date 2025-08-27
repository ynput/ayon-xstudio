"""Use xstudio to open images and movies in the browser / loader UI."""

from __future__ import annotations

import os
import platform
import time
from typing import Any, Dict, List, Optional

import ayon_api  # type: ignore  # noqa: PGH003

from .constants import ADDON_NAME
from .version import __version__


def get_base_xstudio_icon_url() -> str:
    return f"addons/{ADDON_NAME}/{__version__}/public/xstudio.png"


def get_xstudio_icon_url(server_url: Optional[str] = None) -> str:
    server_url = server_url or ayon_api.get_base_url()
    return f"{server_url}/{get_base_xstudio_icon_url()}"


def get_xstudio_paths_from_settings(
    addon_settings: Optional[Dict[str, Any]] = None,
) -> List[str]:
    if addon_settings is None:
        addon_settings = ayon_api.get_addon_settings(ADDON_NAME, __version__)

    platform_name = platform.system().lower()
    xstudio_path_settings = {}
    if addon_settings is not None:
        xstudio_path_settings = addon_settings.get("xstudio_path", {})
    return xstudio_path_settings.get(platform_name, [])


def get_xstudio_executable_path(
    paths: Optional[List[str]] = None,
    addon_settings: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if paths is None:
        paths = get_xstudio_paths_from_settings(addon_settings)

    for path in paths:
        if path and os.path.exists(path):
            return path
    return None


class XStudioExecutableCache:
    """Simple cache for app paths."""

    lifetime = 10

    def __init__(self) -> None:
        """Initialize instance."""
        self._cached_time: Optional[float] = None
        self._xstudio_paths: Optional[List[str]] = None
        self._xstudio_path: Optional[str] = None

    def is_cache_valid(self) -> bool:
        """Cache is valid.

        Returns:
            bool: True if cache is valid, False otherwise.
        """
        if self._cached_time is None:
            return False

        start = time.time()
        return (start - self._cached_time) <= self.lifetime

    def get_paths(self) -> Optional[List[str]]:
        """Get all paths to xStudio executable from settings.

        Returns:
            list[str]: Path to xStudio executables.
        """
        if not self.is_cache_valid():
            self._xstudio_paths = get_xstudio_paths_from_settings()
            self._cached_time = time.time()
        return self._xstudio_paths

    def get_path(self) -> Optional[str]:
        """Get path to xStudio executable.

        Returns:
            Union[str, None]: Path to xStudio executable or None.
        """
        if not self.is_cache_valid():
            self._xstudio_path = get_xstudio_executable_path(self.get_paths())
        return self._xstudio_path
