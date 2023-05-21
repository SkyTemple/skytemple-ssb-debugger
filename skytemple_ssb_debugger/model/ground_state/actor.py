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
from range_typed_integers import u16

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptEntity
from skytemple_ssb_emulator import emulator_read_short_signed, emulator_read_short, emulator_read_byte, \
    emulator_read_long

from skytemple_ssb_debugger.model.ground_state import pos_for_display_camera, AbstractEntityWithScriptStruct, \
    pos_in_map_coord
from skytemple_ssb_debugger.model.ground_state.map import Map

ACTOR_BEGIN_SCRIPT_STRUCT = 0x38


class Actor(AbstractEntityWithScriptStruct):
    def __init__(self, rom_data: Pmd2Data, pnt_to_block_start: int, offset: int):
        super().__init__(pnt_to_block_start, rom_data)
        self.offset = offset

    @property
    def pnt(self):
        return super().pnt + self.offset

    @property
    def _script_struct_offset(self):
        return ACTOR_BEGIN_SCRIPT_STRUCT

    @property
    def valid(self):
        return emulator_read_short_signed(self.pnt + self._script_struct_offset) > 0

    @property
    def id(self):
        return emulator_read_short(self.pnt + 0x00)

    @property
    def kind(self) -> Pmd2ScriptEntity:
        kind_id = emulator_read_short(self.pnt + 0x02)
        try:
            return self.rom_data.script_data.level_entities__by_id[kind_id]
        except KeyError:
            return Pmd2ScriptEntity(u16(kind_id), u16(0), 'UNKNOWN', u16(0), u16(0), u16(0))

    @property
    def hanger(self):
        return emulator_read_short(self.pnt + 0x06)

    @property
    def sector(self):
        return emulator_read_byte(self.pnt + 0x08)

    @property
    def direction(self):
        return self.rom_data.script_data.directions__by_ssb_id[emulator_read_byte(self.pnt + 0x15A)]

    @property
    def x_north(self):
        # via code near 0x22FC310
        return emulator_read_long(self.pnt + 0x15C)

    @property
    def y_west(self):
        return emulator_read_long(self.pnt + 0x160)

    @property
    def x_south(self):
        return emulator_read_long(self.pnt + 0x164)

    @property
    def y_east(self):
        return emulator_read_long(self.pnt + 0x168)

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
