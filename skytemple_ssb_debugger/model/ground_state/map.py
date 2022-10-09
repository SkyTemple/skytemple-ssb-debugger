#  Copyright 2020-2023 Capypara and the SkyTemple Contributors
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
from __future__ import annotations
from skytemple_ssb_emulator import *
from skytemple_files.common.ppmdu_config.data import Pmd2Data


class Map:
    def __init__(self, rom_data: Pmd2Data, pnt_to_block_start: int):
        super().__init__()
        self.rom_data = rom_data
        self.pnt_to_block_start = pnt_to_block_start

    @property
    def pnt(self):
        return emulator_read_long(self.pnt_to_block_start)

    @property
    def camera_x_pos(self):
        """Returns the center position of the camera"""
        return emulator_read_long(self.pnt + 0x200)

    @property
    def camera_y_pos(self):
        """Returns the center position of the camera"""
        return emulator_read_long(self.pnt + 0x204)
