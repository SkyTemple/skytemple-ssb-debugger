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
from typing import Optional


class SsbFileInRam:
    def __init__(self, file_name: str, hanger: int, hash: str = None):
        self.file_name = file_name
        self.hanger = hanger
        # If true, the debugger is currently breaking at this file.
        self.breaked = False
        # If breaked is true: This contains the path of the file that handles the breakpoint.
        # May either be the same as file_name, then the SsbScript or ExplorerScript file for the SSB itself
        # handles the breakpoint, or the absolute path to an ExplorerScript source file that contains a macro
        # that is halted at.
        self.breaked__handler_file: Optional[str] = None
        # Stored hash if loaded from a serialized state, only temporary and valid during deserialization!
        self.hash = hash
