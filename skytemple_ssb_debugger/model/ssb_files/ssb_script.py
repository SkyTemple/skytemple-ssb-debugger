#  Copyright 2020 Parakoopa
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
from typing import Optional

from explorerscript.source_map import SourceMap
from skytemple_ssb_debugger.model.ssb_files import AbstractScriptFile


class SsbScriptFile(AbstractScriptFile):
    def __init__(self, parent: 'SsbLoadedFile'):
        super().__init__(parent)
        self._text: str = ''
        self._source_map: Optional[SourceMap] = None

    def load(self):
        self._text, self._source_map = self.parent.ssb_model.to_ssb_script()

    @property
    def text(self):
        return self._text

    @property
    def source_map(self):
        return self._source_map
