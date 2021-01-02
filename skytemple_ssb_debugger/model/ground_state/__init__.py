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
from abc import abstractmethod, ABC

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.script.ssa_sse_sss.position import TILE_SIZE
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.model.address_container import AddressContainer
from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct
from skytemple_ssb_debugger.threadsafe import threadsafe_emu


def pos_for_display_camera(pos: int, camera_pos: int) -> float:
    """Subtracts the camera positon, but also turns the 'subpixel' position into a float"""
    # TODO: is this actually correct...?
    pos_abs = (pos >> 8) - camera_pos
    pos_sub = (pos & 0xFF) / 0xFF
    return pos_abs + pos_sub


def pos_in_map_coord(low_coord: int, high_coord: int):
    """Translates a RAM map position of an entity into the map position in tiles (same units as poisition markers"""
    # Positions are centered on hitbox:
    center = low_coord + (high_coord - low_coord) / 2
    # TODO: How exactly is the number calculated?
    #       Theory: 256 subpixel precision and then 8 pixel per tile.
    return round(center / 0x100 / TILE_SIZE, 1)


class AbstractEntityWithScriptStruct(ABC):
    """An entity that has a script struct embedded into it's data struct."""
    def __init__(self, emu_thread: EmulatorThread, pnt_to_block_start: int, rom_data: Pmd2Data, unionall_load_addr: AddressContainer):
        super().__init__()
        self.emu_thread: EmulatorThread = emu_thread
        self.pnt_to_block_start = pnt_to_block_start
        self.rom_data = rom_data
        self.unionall_load_addr = unionall_load_addr

    @property
    def pnt(self):
        return threadsafe_emu(
            self.emu_thread, lambda: self.emu_thread.emu.memory.unsigned.read_long(self.pnt_to_block_start)
        )

    @property
    @abstractmethod
    def _script_struct_offset(self):
        pass

    @property
    def script_struct(self):
        return ScriptRuntimeStruct(
            self.emu_thread, self.rom_data.script_data, lambda: self.pnt + self._script_struct_offset, self.unionall_load_addr, self
        )
