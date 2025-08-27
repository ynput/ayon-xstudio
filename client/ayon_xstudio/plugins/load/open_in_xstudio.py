"""Open an image, movie or sequence in xStudio from the Loader / Browser UI."""

import os
import time

import clique
from ayon_core.lib import run_detached_process
from ayon_core.lib.transcoding import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from ayon_core.pipeline import load
from ayon_xstudio.utils import (
    XStudioExecutableCache,
    get_base_xstudio_icon_url,
)


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
    def get_xstudio_path(cls):  # noqa: ANN206
        """Get the path to the xStudio executable.

        Returns:
            str: The path to the xStudio executable.
        """
        return cls._executable_cache.get_path()

    @classmethod
    def is_compatible_loader(cls, context: dict) -> bool:
        """Check if the loader is compatible with the given context.

        Args:
            context (dict): The context to check compatibility with.

        Returns:
            bool: True if the loader is compatible, False otherwise.
        """
        if not cls.get_xstudio_path():
            return False
        return super().is_compatible_loader(context)

    def load(self, context, name=None, namespace=None, options=None) -> None:  # noqa: ANN001
        """Load the given context in xStudio.

        Args:
            context (dict): The context to load.
            name (Optional[str]): The name of the item to load.
            namespace (Optional[str]): The namespace of the item to load.
            options (Optional[Any]): Additional options for loading.
        """
        # print("YAY")
        path = self.filepath_from_context(context)
        fdir, fname = os.path.split(str(path))

        pattern = clique.PATTERNS["frames"]
        files = os.listdir(fdir)
        collections, remainder = clique.assemble(
            files, patterns=[pattern], minimum_items=1
        )
        first_image = None
        for other_file in remainder:
            if other_file == fname:
                first_image = other_file
                break

        if not first_image:
            seq = collections[0]
            # NOTE: clique padding == 0 when the seq number does not start
            # with 0. "1001" has a padding of 0 and "0101" has a padding of 1.
            # we output the seq path with hashes.
            pad = "#" * (seq.padding + len(str(next(iter(seq.indexes)))))
            first_image = f"{seq.head}{pad}{seq.tail}"

        filepath = os.path.normpath(os.path.join(fdir, first_image))

        self.log.info("Opening xStudio with : %s", filepath)

        executable = self.get_xstudio_path()
        cmd = [
            # xStudio path
            str(executable),
            # PATH TO COMPONENT
            filepath,
        ]

        try:
            # Run xStudio with these commands
            run_detached_process(cmd)
            # Keep process in memory for some time
            time.sleep(0.1)

        except FileNotFoundError:
            self.log.error(  # noqa: TRY400
                'File "%s" was not found.', os.path.basename(filepath)
            )
