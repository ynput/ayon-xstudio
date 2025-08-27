"""Server package."""

from typing import Type

from ayon_server.addons import BaseServerAddon

from .settings import DEFAULT_VALUES, XStudioSettings


class XStudioAddon(BaseServerAddon):
    """Add-on class for the server."""

    settings_model: Type[XStudioSettings] = XStudioSettings

    async def get_default_settings(self) -> XStudioSettings:
        """Return default settings."""
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)
