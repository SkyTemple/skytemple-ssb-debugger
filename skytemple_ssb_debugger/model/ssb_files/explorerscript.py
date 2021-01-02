#  Copyright 2020-2021 Parakoopa and the SkyTemple Contributors
#
#  This file is part of SkyTemple.
#
#  SkyTemple is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SkyTemple is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SkyTemple.  If not, see <https://www.gnu.org/licenses/>.
import logging
import os
from typing import Optional

from explorerscript.source_map import SourceMap
from skytemple_ssb_debugger.model.ssb_files import AbstractScriptFile

logger = logging.getLogger(__name__)


class ExplorerScriptFile(AbstractScriptFile):
    def __init__(self, parent: 'SsbLoadedFile'):
        super().__init__(parent)
        self.ssb_hash: str = ''
        self._text: str = ''
        self._source_map: Optional[SourceMap] = None
        self._loaded = False

    @property
    def full_path(self):
        fm = self.parent.project_file_manager
        project_dir = fm.dir()
        return os.path.join(
            project_dir, fm.explorerscript_get_path_for_ssb(self.parent.filename)
        )

    def load(self, force=False):
        logger.debug(f"ExplorerScript load requested for {self.full_path}.")
        # We delegate the project file handling to the file manager
        fm = self.parent.project_file_manager
        if not fm.explorerscript_exists(self.parent.filename):
            # Source file doesn't exist yet
            self.force_decompile()
            fm.explorerscript_save(self.parent.filename, self._text, self._source_map)
            fm.explorerscript_save_hash(self.parent.filename, self.ssb_hash)

        if not force and not fm.explorerscript_hash_up_to_date(self.parent.filename, self.ssb_hash):
            # Hash isn't up to date and load was not forced
            raise SsbHashError()

        self._text, self._source_map = fm.explorerscript_load(self.parent.filename)
        self._loaded = True

    def force_decompile(self):
        self._text, self._source_map = self.parent.ssb_model.to_explorerscript()
        self._loaded = True

    @property
    def loaded(self):
        return self._loaded

    @property
    def text(self):
        return self._text

    @property
    def source_map(self) -> SourceMap:
        if self._source_map is None:
            # If not currently loaded, load fresh source map instead directly.
            return self.parent.project_file_manager.explorerscript_load_sourcemap(self.parent.filename)
        return self._source_map

    @source_map.setter
    def source_map(self, val: SourceMap):
        self._source_map = val


class SsbHashError(Exception):
    """Raised by load, when the exps already exists but the hash file doesn't or the hash doesn't match the ssb hash."""
    pass
