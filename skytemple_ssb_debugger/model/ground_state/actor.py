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
from desmume.emulator import DeSmuME_Memory
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptLevel, Pmd2ScriptEntity
from skytemple_ssb_debugger.model.ground_state import pos_for_display_camera, AbstractScriptRuntimeState
from skytemple_ssb_debugger.model.ground_state.map import Map

ACTOR_BEGIN_SCRIPT_STRUCT = 0x38


class Actor(AbstractScriptRuntimeState):
    def __init__(self, mem: DeSmuME_Memory, rom_data: Pmd2Data, pnt: int):
        super().__init__(mem, pnt)
        self.rom_data = rom_data

    @property
    def _script_struct_offset(self):
        return ACTOR_BEGIN_SCRIPT_STRUCT

    @property
    def id(self):
        return self.mem.unsigned.read_short(self.pnt + 0x00)

    @property
    def kind(self) -> Pmd2ScriptEntity:
        kind_id = self.mem.unsigned.read_short(self.pnt + 0x02)
        try:
            return self.rom_data.script_data.level_entities__by_id[kind_id]
        except KeyError:
            return Pmd2ScriptEntity(kind_id, -1, 'UNKNOWN', -1, -1, -1)

    @property
    def hanger(self):
        return self.mem.unsigned.read_short(self.pnt + 0x06)

    @property
    def sector(self):
        return self.mem.unsigned.read_byte(self.pnt + 0x08)

    @property
    def direction(self):
        return self.rom_data.script_data.directions__by_id[self.mem.unsigned.read_byte(self.pnt + 0x15A)]

    @property
    def x_north(self):
        # via code near 0x22FC310
        return self.mem.unsigned.read_long(self.pnt + 0x15C)

    @property
    def y_west(self):
        return self.mem.unsigned.read_long(self.pnt + 0x160)

    @property
    def x_south(self):
        return self.mem.unsigned.read_long(self.pnt + 0x164)

    @property
    def y_east(self):
        return self.mem.unsigned.read_long(self.pnt + 0x168)

    def get_bounding_box_camera(self, map: Map):
        return (
            pos_for_display_camera(self.x_north, map.camera_x_pos), pos_for_display_camera(self.y_west, map.camera_y_pos),
            pos_for_display_camera(self.x_south, map.camera_x_pos), pos_for_display_camera(self.y_east, map.camera_y_pos)
        )
