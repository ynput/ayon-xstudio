from __future__ import annotations

import os
import collections
import time
from pathlib import Path
import typing
from typing import Any, Optional

import clique

from ayon_core.lib import run_detached_process, StringTemplate

from ayon_core.lib.transcoding import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from ayon_core.pipeline.load import get_representation_path_with_anatomy
from ayon_core.pipeline.actions import (
    LoaderActionPlugin,
    LoaderActionItem,
    LoaderActionSelection,
    LoaderActionResult,
)

from ayon_xstudio.utils import (
    XStudioExecutableCache,
    get_base_xstudio_icon_url,
)
if typing.TYPE_CHECKING:
    from ayon_core.pipeline import Anatomy


class OpenInXStudio(LoaderActionPlugin):
    """Open Image Sequence or Video with system default"""
    identifier = "xstudio.open-in-xstudio"

    _executable_cache = XStudioExecutableCache()
    extensions = set(IMAGE_EXTENSIONS) | set(VIDEO_EXTENSIONS)

    @classmethod
    def get_xstudio_path(cls) -> Optional[str]:
        """Get the path to the xStudio executable.

        Returns:
            str: The path to the xStudio executable.
        """
        return cls._executable_cache.get_path()

    def get_action_items(
        self, selection: LoaderActionSelection
    ) -> list[LoaderActionItem]:
        if not self.get_xstudio_path():
            return []

        repres = []
        if selection.selected_type == "representation":
            repres = selection.entities.get_representations(
                selection.selected_ids
            )

        if selection.selected_type == "version":
            repres = selection.entities.get_versions_representations(
                selection.selected_ids
            )

        if not repres:
            return []

        repre_ids_by_name = collections.defaultdict(set)
        for repre in repres:
            repre_context = repre.get("context")
            if not repre_context:
                continue
            ext = repre_context.get("ext")
            if not ext:
                path = repre["attrib"].get("path")
                if path:
                    ext = os.path.splitext(path)[1]

            if ext:
                ext = ext.lower()
                if not ext.startswith("."):
                    ext = f".{ext}"
                if ext not in self.extensions:
                    continue
                name = repre["name"]
                repre_ids_by_name[name].add(repre["id"])

        if not repre_ids_by_name:
            return []

        return [
            LoaderActionItem(
                label=repre_name,
                group_label="Open in xStudio",
                order=-10,
                data={"representation_id": next(iter(repre_ids))},
                icon={
                    "type": "ayon_url",
                    "url": get_base_xstudio_icon_url(),
                },
            )
            for repre_name, repre_ids in repre_ids_by_name.items()
            if len(repre_ids) == 1
        ]

    def execute_action(
        self,
        selection: LoaderActionSelection,
        data: dict[str, Any],
        form_values: dict[str, Any],
    ) -> Optional[LoaderActionResult]:
        executable = self.get_xstudio_path()
        if not executable:
            return LoaderActionResult(
                "Couldn't find xStudio executable.",
                success=False,
            )

        repre_id = data["representation_id"]
        repre = next(
            iter(selection.entities.get_representations({repre_id})),
            None
        )
        if not repre:
            return LoaderActionResult(
                "Failed to find representation in AYON...",
                success=False,
            )

        repre_path = get_representation_path_with_anatomy(
            repre, selection.get_project_anatomy()
        )
        if not repre_path:
            return LoaderActionResult(
                "Failed to fill representation path...",
                success=False,
            )

        if not os.path.exists(repre_path):
            return LoaderActionResult(
                "File to open was not found...",
                success=False,
            )

        fdir, fname = os.path.split(repre_path)
        pattern = clique.PATTERNS["frames"]
        files = os.listdir(fdir)
        collections: list[Any]
        remainder: list[str]
        collections, remainder = clique.assemble(
            files, patterns=[pattern], minimum_items=1
        )
        first_image: str | None = None
        for other_file in remainder:
            if other_file == fname:
                first_image = other_file
                break

        if not first_image:
            seq = collections[0]
            # NOTE: clique padding == 0 when the seq number does not start
            # with 0. "1001" has a padding of 0 and "0101" has a padding of 1.
            # we output the seq path with hashes.
            idxs = list(seq.indexes)
            pad = "#" * len(str(idxs[-1]))
            first_image = f"{seq.head}{pad}{seq.tail}={idxs[0]}-{idxs[-1]}"

        filepath = os.path.normpath(os.path.join(fdir, first_image))
        self.log.info("Opening xStudio with : %s", filepath)

        anatomy = selection.get_project_anatomy()
        # TODO(plp): Is there a get_ayon_env() somewhere ?
        env = dict(os.environ)
        ocio_path = self._get_ocio_path(anatomy, repre)
        if ocio_path:
            env["OCIO"] = ocio_path

        cmd: list[str] = [
            # xStudio path
            str(executable),
            # PATH TO COMPONENT
            filepath,
        ]
        # Run XStudio with these commands
        run_detached_process(cmd, env=env)
        # Keep process in memory for some time
        time.sleep(0.1)

        return LoaderActionResult(
            "File opened in xStudio...",
            success=True,
        )

    def _get_ocio_path(
        self,
        anatomy: Anatomy,
        repre_entity: dict[str, Any],
    ) -> str | None:
        """Set the OCIO environment variable based on the given context.

        Args:
            anatomy (Anatomy): Project anatomy.
            repre_entity (dict): Representation entity.

        Raises:
            KeyError: If the 'representation' key is not found in the context.
        """
        colorspace_config: dict = (
            repre_entity
            .get("data", {})
            .get("colorspaceData", {})
            .get("config", {})
        )
        if not colorspace_config:
            self.log.info(
                "Couldn't find 'colorspaceData.config' in representation."
                " Not configuring OCIO"
            )
            return None

        ocio_template: str | None = colorspace_config.get("template")
        if ocio_template:
            data = os.environ.copy()
            data["root"] = anatomy.roots
            ocio_path = StringTemplate.format_template(
                ocio_template, data
            )
            if ocio_path.solved and os.path.exists(ocio_path):
                return str(ocio_path)

        ocio_path = colorspace_config.get("path")
        if not ocio_path:
            self.log.info(
                "Representation OCIO path undefined."
                " Not configuring OCIO"
            )
            return None

        ocio_path = Path(ocio_path)
        if ocio_path.is_absolute():
            ocio_path = ocio_path.resolve()

        if ocio_path.exists():
            return str(ocio_path)

        success, rootless_path = anatomy.find_root_template_from_path(
            ocio_path.as_posix()
        )
        if success:
            return StringTemplate.format_strict_template(
                rootless_path, {"root": anatomy.roots}
            )

        ocio_path = self.find_ayon_ocio_config(ocio_path)
        if ocio_path:
            return str(ocio_path)

        self.log.info("Not configuring xSTUDIO OCIO !")
        return None

    def find_ayon_ocio_config(self, ocio_path: Path) -> Path | None:
        """Find the AYON OCIO config path.

        Args:
            ocio_path (Path): The path to the OCIO config.

        Returns:
            Path | None: The path to the AYON OCIO config if found, None
                otherwise.
        """
        self.log.debug("representation ocio: %s", ocio_path.as_posix())
        path = Path(ocio_path)

        if "OpenColorIOConfigs" not in path.parts:
            return None

        try:
            from ayon_ocio import get_ocio_config_path

        except ImportError:
            pass
        else:
            ocio_folder = get_ocio_config_path()
            self.log.debug("ocio root: %s", ocio_folder)
            folder_index = path.parts.index("OpenColorIOConfigs")
            server_ocio = Path(ocio_folder).joinpath(
                *path.parts[folder_index + 1 :]
            )
            self.log.debug("server_ocio = %s", server_ocio)
            if server_ocio.exists():
                return server_ocio

            self.log.debug("server_ocio doesn't exist !")

        return None
