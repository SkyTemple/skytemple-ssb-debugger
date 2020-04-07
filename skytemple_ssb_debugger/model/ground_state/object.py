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
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptObject
from skytemple_ssb_debugger.model.ground_state import pos_for_display_camera, AbstractScriptRuntimeState
from skytemple_ssb_debugger.model.ground_state.map import Map

OBJECT_BEGIN_SCRIPT_STRUCT = 0x3C


class Object(AbstractScriptRuntimeState):
    def __init__(self, mem: DeSmuME_Memory, rom_data: Pmd2Data, pnt: int):
        super().__init__(mem, pnt)
        self.rom_data = rom_data

    @property
    def _script_struct_offset(self):
        return OBJECT_BEGIN_SCRIPT_STRUCT

    @property
    def id(self):
        return self.mem.unsigned.read_short(self.pnt + 0x04)

    @property
    def kind(self) -> Pmd2ScriptObject:
        kind_id = self.mem.unsigned.read_short(self.pnt + 0x06)
        try:
            return self.rom_data.script_data.objects__by_id[kind_id]
        except KeyError:
            return Pmd2ScriptObject(kind_id, -1, -1, -1, 'UNKNOWN')

    @property
    def hanger(self):
        return self.mem.signed.read_short(self.pnt + 0x0A)

    @property
    def sector(self):
        return self.mem.signed.read_byte(self.pnt + 0x0C)

    @property
    def direction(self):
        return self.rom_data.script_data.directions__by_id[0]  # TODO!!

    @property
    def x_north(self):
        return self.mem.unsigned.read_long(self.pnt + 0x134)

    @property
    def y_west(self):
        return self.mem.unsigned.read_long(self.pnt + 0x138)

    @property
    def x_south(self):
        return self.mem.unsigned.read_long(self.pnt + 0x13C)

    @property
    def y_east(self):
        return self.mem.unsigned.read_long(self.pnt + 0x140)

    def get_bounding_box_camera(self, map: Map):
        return (
            pos_for_display_camera(self.x_north, map.camera_x_pos), pos_for_display_camera(self.y_west, map.camera_y_pos),
            pos_for_display_camera(self.x_south, map.camera_x_pos), pos_for_display_camera(self.y_east, map.camera_y_pos)
        )
