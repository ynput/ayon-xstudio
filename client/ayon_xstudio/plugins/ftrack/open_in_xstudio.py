"""Open an image, movie or sequence in xStudio from ftrack."""

from __future__ import annotations

import os
import re
from operator import itemgetter
from typing import Any, Dict, List, Optional, Union

from ayon_core.lib import run_detached_process
from ayon_core.lib.transcoding import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from ayon_ftrack.common import LocalAction
from ayon_xstudio.utils import XStudioExecutableCache, get_xstudio_icon_url


class XStudioViewAction(LocalAction):
    """Launch xStudioView action."""

    identifier = "xstudio-view-action"
    label = "xStudio View"
    description = "xStudio View Launcher"
    icon = get_xstudio_icon_url()

    type = "Application"

    allowed_types = {  # noqa: RUF012
        ext.lstrip(".")
        for ext in set(IMAGE_EXTENSIONS) | set(VIDEO_EXTENSIONS)
    }
    _executable_cache = XStudioExecutableCache()

    def discover(
        self,
        session: Any,  # noqa: ANN401
        entities: List[Any],
        event: Dict[str, Any],
    ) -> bool:
        """Return available actions based on event.

        Args:
            session: The ftrack session.
            entities: List of entities.
            event: The event dictionary.

        Returns:
            bool: True if action is available, False otherwise.
        """
        selection = event["data"].get("selection", [])
        if len(selection) != 1:
            return False

        entity_type = selection[0].get("entityType", None)
        if entity_type not in {"assetversion", "task"}:
            return False

        return self._executable_cache.get_path() is not None

    def interface(
        self,
        session: Any,  # noqa: ANN401
        entities: List[Any],
        event: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate the interface for the action.

        Args:
            session: The ftrack session.
            entities: List of entities.
            event: The event dictionary.

        Returns:
            Optional[Dict[str, Any]]: Interface definition or None.
        """
        # NOTE: `interface` is too complex (18 > 10)
        #       Too many branches (19 > 12)

        if event["data"].get("values", {}):
            return None

        entity = entities[0]
        versions: List[Any] = []

        entity_type = entity.entity_type.lower()
        if entity_type == "assetversion":
            if entity["components"][0]["file_type"][1:] in self.allowed_types:
                versions.append(entity)
        else:
            master_entity = entity
            if entity_type == "task":
                master_entity = entity["parent"]

            for asset in master_entity["assets"]:
                for version in asset["versions"]:
                    # Get only AssetVersion of selected task
                    if (
                        entity_type == "task"
                        and version["task"]["id"] != entity["id"]
                    ):
                        continue
                    # Get only components with allowed type
                    filetype = version["components"][0]["file_type"]
                    if filetype[1:] in self.allowed_types:
                        versions.append(version)

        if len(versions) < 1:
            return {
                "success": False,
                "message": "There are no Asset Versions to open.",
            }

        path = self._executable_cache.get_path()
        if not path:
            return {
                "success": False,
                "message": "Couldn't find xStudio executable.",
            }

        version_items: List[Dict[str, str]] = []
        base_label = "v{0} - {1} - {2}"
        default_component: Optional[str] = None
        last_available: Optional[str] = None
        select_value: Optional[str] = None
        for version in versions:
            for component in version["components"]:
                label = base_label.format(
                    str(version["version"]).zfill(3),
                    version["asset"]["type"]["name"],
                    component["name"],
                )

                try:
                    location = component["component_locations"][0]["location"]
                    file_path = location.get_filesystem_path(component)
                except Exception:  # noqa: BLE001
                    file_path = component["component_locations"][0][
                        "resource_identifier"
                    ]

                if os.path.isdir(os.path.dirname(file_path)):
                    last_available = file_path
                    if component["name"] == default_component:
                        select_value = file_path
                    version_items.append({"label": label, "value": file_path})

        if len(version_items) == 0:
            return {
                "success": False,
                "message": (
                    "There are no Asset Versions with accessible path."
                ),
            }

        item: Dict[str, Any] = {
            "label": "Items to view",
            "type": "enumerator",
            "name": "path",
            "data": sorted(
                version_items, key=itemgetter("label"), reverse=True
            ),
        }
        if select_value is not None:
            item["value"] = select_value
        else:
            item["value"] = last_available

        return {"items": [item]}

    def launch(
        self,
        session: Any,  # noqa: ANN401
        entities: List[Any],
        event: Dict[str, Any],
    ) -> Union[bool, Dict[str, Any]]:
        """Callback method for xStudioView action.

        Args:
            session: The ftrack session.
            entities: List of entities.
            event: The event dictionary.

        Returns:
            Union[bool, Dict[str, Any]]: True if application was launched,
                or a dictionary with success status and message.
        """
        # Launching application
        event_values = event["data"].get("values")
        if not event_values:
            return False

        executable = self._executable_cache.get_path()
        if not executable:
            return {
                "success": False,
                "message": "Couldn't find xStudio executable.",
            }

        filepath = os.path.normpath(event_values["path"])

        # replace the frame number with padded '#'
        filepath = re.sub(
            r"(.*\.)(\d+)(\.\w{3})$",
            lambda m: f"{m.group(1)}{'#' * len(m.group(2))}{m.group(3)}",
            filepath,
        )

        cmd: List[str] = [
            # xStudio path
            str(executable),
            # PATH TO COMPONENT
            filepath,
        ]
        self.log.info("Opening: %s", cmd)

        try:
            # Run xStudio with these commands
            run_detached_process(cmd)

        except FileNotFoundError:
            return {
                "success": False,
                "message": (
                    f'File "{os.path.basename(filepath)}" was not found.'
                ),
            }

        return True


def register(session: Any) -> None:  # noqa: ANN401
    """Register hooks.

    Args:
        session: The ftrack session.
    """
    XStudioViewAction(session).register()
