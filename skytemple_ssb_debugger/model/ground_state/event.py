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
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_emulator import emulator_read_long, emulator_read_short_signed, emulator_read_short, \
    emulator_read_byte

from skytemple_ssb_debugger.model.ground_state import pos_for_display_camera, pos_in_map_coord
from skytemple_ssb_debugger.model.ground_state.map import Map

EVENT_EXISTS_CHECK_OFFSET = 0x02


class Event:
    def __init__(self, rom_data: Pmd2Data, pnt_to_block_start: int, offset: int):
        super().__init__()
        self.rom_data = rom_data
        self.pnt_to_block_start = pnt_to_block_start
        self.offset = offset

    @property
    def pnt(self):
        return emulator_read_long(self.pnt_to_block_start) + self.offset

    @property
    def valid(self):
        return emulator_read_short_signed(self.pnt + EVENT_EXISTS_CHECK_OFFSET) > 0

    @property
    def id(self):
        return emulator_read_short(self.pnt + 0x00)

    @property
    def kind(self):
        return emulator_read_short(self.pnt + 0x02)

    @property
    def hanger(self):
        return emulator_read_short(self.pnt + 0x04)

    @property
    def sector(self):
        return emulator_read_byte(self.pnt + 0x06)

    @property
    def x_north(self):
        return emulator_read_long(self.pnt + 0x10)

    @property
    def y_west(self):
        return emulator_read_long(self.pnt + 0x14)

    @property
    def x_south(self):
        return emulator_read_long(self.pnt + 0x18)

    @property
    def y_east(self):
        return emulator_read_long(self.pnt + 0x1C)

    @property
    def x_map(self):
        return pos_in_map_coord(self.x_north, self.x_south)

    @property
    def y_map(self):
        return pos_in_map_coord(self.y_west, self.y_east)

    def get_bounding_box_camera(self, map: Map):
        return (
            pos_for_display_camera(self.x_north, map.camera_x_pos), pos_for_display_camera(self.y_west, map.camera_y_pos),
            pos_for_display_camera(self.x_south, map.camera_x_pos), pos_for_display_camera(self.y_east, map.camera_y_pos)
        )
