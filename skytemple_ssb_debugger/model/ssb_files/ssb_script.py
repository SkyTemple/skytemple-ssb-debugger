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
from typing import Optional

from explorerscript.source_map import SourceMap
from skytemple_ssb_debugger.model.ssb_files import AbstractScriptFile

logger = logging.getLogger(__name__)


class SsbScriptFile(AbstractScriptFile):
    def __init__(self, parent: 'SsbLoadedFile'):
        super().__init__(parent)
        self._text: str = ''
        self._source_map: Optional[SourceMap] = None
        self._loaded = False

    def load(self):
        logger.debug(f"SSBScript load requested for {self.parent.filename}.")
        self._text, self._source_map = self.parent.ssb_model.to_ssb_script()
        self._loaded = True

    @property
    def loaded(self):
        return self._loaded

    @property
    def text(self):
        return self._text

    @property
    def source_map(self):
        return self._source_map

    @source_map.setter
    def source_map(self, val):
        self._source_map = val
