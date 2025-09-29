"""Open an image, movie or sequence in xStudio from the Loader / Browser UI."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import clique
from ayon_core.lib import Logger, StringTemplate, run_detached_process
from ayon_core.lib.transcoding import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from ayon_core.pipeline import Anatomy, load
from ayon_xstudio.utils import (
    XStudioExecutableCache,
    get_base_xstudio_icon_url,
)

log = Logger.get_logger(__name__)


class OpenInXStudio(load.LoaderPlugin):
    """Open Image Sequence with system default."""

    _executable_cache = XStudioExecutableCache()
    product_types = {"*"}  # noqa: RUF012
    representations = ["*"]  # noqa: RUF012
    extensions = {  # noqa: RUF012
        ext.lstrip(".")
        for ext in set(IMAGE_EXTENSIONS) | set(VIDEO_EXTENSIONS)
    }

    label = "Open in xStudio"
    order = -10

    icon = {"type": "ayon_url", "url": get_base_xstudio_icon_url()}  # noqa: RUF012
    color = "aquamarine"

    @classmethod
    def get_xstudio_path(cls) -> Optional[str]:
        """Get the path to the xStudio executable.

        Returns:
            str: The path to the xStudio executable.
        """
        return cls._executable_cache.get_path()

    @classmethod
    def is_compatible_loader(cls, context: Dict[str, Any]) -> bool:
        """Check if the loader is compatible with the given context.

        Args:
            context (dict): The context to check compatibility with.

        Returns:
            bool: True if the loader is compatible, False otherwise.
        """
        if not cls.get_xstudio_path():
            return False
        return super().is_compatible_loader(context)

    def load(
        self,
        context: Dict[str, Any],
        name: Optional[str] = None,
        namespace: Optional[str] = None,
        options: Optional[Any] = None,  # noqa: ANN401
    ) -> None:
        """Load the given context in xStudio.

        Args:
            context (dict): The context to load.
            name (Optional[str]): The name of the item to load.
            namespace (Optional[str]): The namespace of the item to load.
            options (Optional[Any]): Additional options for loading.
        """
        # print(context)
        path = self.filepath_from_context(context)
        fdir, fname = os.path.split(str(path))

        pattern = clique.PATTERNS["frames"]
        files = os.listdir(fdir)
        collections: List[Any]
        remainder: List[str]
        collections, remainder = clique.assemble(
            files, patterns=[pattern], minimum_items=1
        )
        first_image: Optional[str] = None
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

        executable = self.get_xstudio_path()
        cmd: List[str] = [
            # xStudio path
            str(executable),
            # PATH TO COMPONENT
            filepath,
        ]

        # TODO(plp): Is there a get_ayon_env() somewhere ?
        ayon_env = dict(os.environ)
        _set_ocio_env_var(context, ayon_env)

        try:
            # Run xStudio with these commands
            run_detached_process(cmd, env=ayon_env)
            # Keep process in memory for some time
            time.sleep(0.1)

        except FileNotFoundError:
            self.log.error(  # noqa: TRY400
                'File "%s" was not found.', os.path.basename(filepath)
            )


def find_ayon_ocio_config(ocio_path: Path) -> Union[Path, None]:
    """Find the AYON OCIO config path.

    Args:
        ocio_path (Path): The path to the OCIO config.

    Returns:
        Union[Path, None]: The path to the AYON OCIO config if found, None
            otherwise.
    """
    log.debug("representation ocio: %s", ocio_path.as_posix())
    path = Path(ocio_path)

    if "OpenColorIOConfigs" not in path.parts:
        return None

    try:
        from ayon_ocio import get_ocio_config_path

    except ImportError:
        pass
    else:
        ocio_folder = get_ocio_config_path()
        log.debug("ocio root: %s", ocio_folder)
        folder_index = path.parts.index("OpenColorIOConfigs")
        server_ocio = Path(ocio_folder).joinpath(
            *path.parts[folder_index + 1 :]
        )
        log.debug("server_ocio = %s", server_ocio)
        if server_ocio.exists():
            return server_ocio

        log.debug("server_ocio doesn't exist !")

    return None


def _set_ocio_env_var(context: Dict[str, Any], env: dict) -> None:
    """Set the OCIO environment variable based on the given context.

    Args:
        context (dict): The context to use for setting the OCIO environment
            variable.
        env (dict): The environment variables to update.

    Raises:
        KeyError: If the 'representation' key is not found in the context.
    """
    representation: dict = context.get("representation", {})
    if not representation:
        err = "Couldn't find 'representation' in context !"
        raise KeyError(err)

    colorspace_data: dict = representation.get("data", {}).get(
        "colorspaceData", {}
    )
    if not colorspace_data:
        log.warning("Couldn't find 'colorspaceData' in representation.")
        log.warning("Not configuring OCIO !")
        return

    ocio_path = colorspace_data.get("config", {}).get("path")
    if not ocio_path:
        log.warning("Representation OCIO path undefined")
        log.warning("Not configuring OCIO !")
        return

    ocio_path = Path(ocio_path)
    if ocio_path.is_absolute():
        ocio_path = ocio_path.resolve()

    if not ocio_path.exists():
        anatomy = Anatomy(context["project"]["name"])
        ok, rootless_path = anatomy.find_root_template_from_path(
            ocio_path.as_posix()
        )
        if ok:
            ocio_path = StringTemplate.format_strict_template(
                rootless_path, {"root": anatomy.roots}
            )
        else:
            ocio_path = find_ayon_ocio_config(ocio_path)
            if not ocio_path:
                log.warning("Not configuring xSTUDIO OCIO !")
                return

    env["OCIO"] = ocio_path
