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
from range_typed_integers import u16, u8

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptObject
from skytemple_ssb_emulator import emulator_read_short_signed, emulator_read_short, emulator_read_byte_signed, \
    emulator_read_long

from skytemple_ssb_debugger.model.ground_state import pos_for_display_camera, AbstractEntityWithScriptStruct, \
    pos_in_map_coord
from skytemple_ssb_debugger.model.ground_state.map import Map

OBJECT_BEGIN_SCRIPT_STRUCT = 0x3C


class Object(AbstractEntityWithScriptStruct):
    def __init__(self, rom_data: Pmd2Data, pnt_to_block_start: int, offset: int):
        super().__init__(pnt_to_block_start, rom_data)
        self.offset = offset

    @property
    def pnt(self):
        return super().pnt + self.offset

    @property
    def _script_struct_offset(self):
        return OBJECT_BEGIN_SCRIPT_STRUCT

    @property
    def valid(self):
        return emulator_read_short_signed(self.pnt + self._script_struct_offset) > 0

    @property
    def id(self):
        return emulator_read_short(self.pnt + 0x04)

    @property
    def kind(self) -> Pmd2ScriptObject:
        kind_id = emulator_read_short(self.pnt + 0x06)
        try:
            return self.rom_data.script_data.objects__by_id[kind_id]
        except KeyError:
            return Pmd2ScriptObject(u16(kind_id), u16(0), u16(0), u8(0), 'UNKNOWN')

    @property
    def hanger(self):
        return emulator_read_short_signed(self.pnt + 0x0A)

    @property
    def sector(self):
        return emulator_read_byte_signed(self.pnt + 0x0C)

    @property
    def direction(self):
        return self.rom_data.script_data.directions__by_ssb_id[0]  # TODO!!

    @property
    def x_north(self):
        return emulator_read_long(self.pnt + 0x134)

    @property
    def y_west(self):
        return emulator_read_long(self.pnt + 0x138)

    @property
    def x_south(self):
        return emulator_read_long(self.pnt + 0x13C)

    @property
    def y_east(self):
        return emulator_read_long(self.pnt + 0x140)

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
