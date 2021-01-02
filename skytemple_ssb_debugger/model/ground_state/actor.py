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
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptEntity
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.model.address_container import AddressContainer
from skytemple_ssb_debugger.model.ground_state import pos_for_display_camera, AbstractEntityWithScriptStruct, \
    pos_in_map_coord
from skytemple_ssb_debugger.model.ground_state.map import Map
from skytemple_ssb_debugger.threadsafe import wrap_threadsafe_emu

ACTOR_BEGIN_SCRIPT_STRUCT = 0x38


class Actor(AbstractEntityWithScriptStruct):
    def __init__(self, emulator_thread: EmulatorThread, rom_data: Pmd2Data, pnt_to_block_start: int, offset: int, unionall_load_addr: AddressContainer):
        super().__init__(emulator_thread, pnt_to_block_start, rom_data, unionall_load_addr)
        self.offset = offset

    @property
    def pnt(self):
        return super().pnt + self.offset

    @property
    def _script_struct_offset(self):
        return ACTOR_BEGIN_SCRIPT_STRUCT

    @property
    @wrap_threadsafe_emu()
    def valid(self):
        return self.emu_thread.emu.memory.signed.read_short(self.pnt + self._script_struct_offset) > 0

    @property
    @wrap_threadsafe_emu()
    def id(self):
        return self.emu_thread.emu.memory.unsigned.read_short(self.pnt + 0x00)

    @property
    @wrap_threadsafe_emu()
    def kind(self) -> Pmd2ScriptEntity:
        kind_id = self.emu_thread.emu.memory.unsigned.read_short(self.pnt + 0x02)
        try:
            return self.rom_data.script_data.level_entities__by_id[kind_id]
        except KeyError:
            return Pmd2ScriptEntity(kind_id, -1, 'UNKNOWN', -1, -1, -1)

    @property
    @wrap_threadsafe_emu()
    def hanger(self):
        return self.emu_thread.emu.memory.unsigned.read_short(self.pnt + 0x06)

    @property
    @wrap_threadsafe_emu()
    def sector(self):
        return self.emu_thread.emu.memory.unsigned.read_byte(self.pnt + 0x08)

    @property
    @wrap_threadsafe_emu()
    def direction(self):
        return self.rom_data.script_data.directions__by_id[self.emu_thread.emu.memory.unsigned.read_byte(self.pnt + 0x15A)]

    @property
    @wrap_threadsafe_emu()
    def x_north(self):
        # via code near 0x22FC310
        return self.emu_thread.emu.memory.unsigned.read_long(self.pnt + 0x15C)

    @property
    @wrap_threadsafe_emu()
    def y_west(self):
        return self.emu_thread.emu.memory.unsigned.read_long(self.pnt + 0x160)

    @property
    @wrap_threadsafe_emu()
    def x_south(self):
        return self.emu_thread.emu.memory.unsigned.read_long(self.pnt + 0x164)

    @property
    @wrap_threadsafe_emu()
    def y_east(self):
        return self.emu_thread.emu.memory.unsigned.read_long(self.pnt + 0x168)

    @property
    @wrap_threadsafe_emu()
    def x_map(self):
        return pos_in_map_coord(self.x_north, self.x_south)

    @property
    @wrap_threadsafe_emu()
    def y_map(self):
        return pos_in_map_coord(self.y_west, self.y_east)

    def get_bounding_box_camera(self, map: Map):
        return (
            pos_for_display_camera(self.x_north, map.camera_x_pos), pos_for_display_camera(self.y_west, map.camera_y_pos),
            pos_for_display_camera(self.x_south, map.camera_x_pos), pos_for_display_camera(self.y_east, map.camera_y_pos)
        )
