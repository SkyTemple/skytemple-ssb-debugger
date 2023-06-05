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
from abc import abstractmethod, ABC
from typing import Optional

from range_typed_integers import u32
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.script.ssa_sse_sss.position import TILE_SIZE
from skytemple_ssb_emulator import emulator_read_mem_from_ptr, emulator_read_mem_from_ptr_with_validity_check

from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct


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


class AbstractEntity(ABC):
    """An entity"""
    def __init__(self, pnt_to_block_start: u32, offset: u32, rom_data: Pmd2Data):
        super().__init__()
        self.pnt_to_block_start = pnt_to_block_start
        self.rom_data = rom_data
        self.offset = offset
        self.buffer = bytes(self._block_size)
        self.refresh()

    def refresh(self):
        self.buffer = bytes(self._block_size)
        def set_val(val):
            self.buffer = val

        if self._block_size != 0:
            if self._validity_offset is not None:
                emulator_read_mem_from_ptr_with_validity_check(self.pnt_to_block_start, self.offset, self._block_size, self._validity_offset, set_val)
            else:
                emulator_read_mem_from_ptr(self.pnt_to_block_start, self.offset, self._block_size, set_val)

    @property
    @abstractmethod
    def _block_size(self):
        pass

    @property
    @abstractmethod
    def _validity_offset(self) -> Optional[u32]:
        """If defined, only refresh the memory if the i16 at the given offset starting at the block start is > 0."""


class AbstractEntityWithScriptStruct(AbstractEntity, ABC):
    """An entity that has a script struct embedded into it's data struct."""
    @property
    @abstractmethod
    def _script_struct_offset(self):
        pass

    @property
    def script_struct(self):
        return ScriptRuntimeStruct(
            self.rom_data, self.pnt_to_block_start, self.offset + self._script_struct_offset, self
        )
