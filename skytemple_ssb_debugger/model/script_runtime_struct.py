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

from explorerscript.ssb_converting.ssb_data_types import SsbRoutineType
from range_typed_integers import u32
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.util import read_u32, read_u16, read_i16
from skytemple_ssb_emulator import emulator_unionall_load_address, emulator_read_mem_from_ptr

# This is not the actual size, increase this if we need to read more!
STRUCT_SIZE = u32(0x34)


class ScriptRuntimeStruct:
    def __init__(self, rom_data: Pmd2Data, pnt_to_block_start: u32, script_struct_offset_from_start: u32, parent=None, *, _do_not_refresh=False):
        super().__init__()
        self.rom_data = rom_data
        self.pnt_to_block_start = pnt_to_block_start
        self.script_struct_offset_from_start = script_struct_offset_from_start
        self.buffer = bytes(STRUCT_SIZE)
        self._cached_target_id: int = 0
        self._do_not_refresh = _do_not_refresh
        self.refresh()
        
        # for debugging
        self._parent = parent

    @classmethod
    def from_data(cls, rom_data: Pmd2Data, pnt_to_block_start: u32, data: bytes, target_slot_id: u32):
        slf = cls(
            rom_data,
            pnt_to_block_start,
            None,  # type: ignore
            _do_not_refresh=True
        )
        slf.buffer = data
        slf._cached_target_id = target_slot_id
        return slf

    def refresh(self):
        def set_val(val: bytes):
            self.buffer = val
            self.refresh_target_id()

        if self.pnt_to_block_start is not None and not self._do_not_refresh:
            self._cached_target_id = 0
            emulator_read_mem_from_ptr(self.pnt_to_block_start, self.script_struct_offset_from_start, STRUCT_SIZE, set_val)

    def refresh_target_id(self):
        def set_cached_target_id(val: bytes):
            self._cached_target_id = read_u16(val, 0)

        script_target_address = read_u32(self.buffer, 0x04)
        if script_target_address != 0:
            emulator_read_mem_from_ptr(script_target_address, u32(0), u32(2), set_cached_target_id)

    @property
    def valid(self):
        """The first entry contains a pointer to something unknown (global script state?) when valid"""
        return read_u32(self.buffer, 0) != 0

    @property
    def script_target_type(self) -> SsbRoutineType:
        """The type of target for this script struct (ACTOR, OBJECT, PERFORMER) or GENERIC for global script"""
        idx = read_u32(self.buffer, 0x08)
        return SsbRoutineType.create_for_index(idx)

    @property
    def script_target_slot_id(self) -> int:
        """The slot id of the target type's entity list (always 0 for global script)"""
        return self._cached_target_id

    @property
    def start_addr_routine_infos(self) -> int:
        return read_u32(self.buffer, 0x14)

    @property
    def start_addr_opcodes(self) -> int:
        return read_u32(self.buffer, 0x18)

    @property
    def current_opcode_addr(self) -> int:
        return read_u32(self.buffer, 0x1c)

    @property
    def current_opcode_addr_relative(self) -> int:
        """The current opcode address relative to the start of the SSB file (after header), in words."""
        return int((self.current_opcode_addr - self.start_addr_routine_infos) / 2)

    @property
    def start_addr_str_table(self) -> int:
        return read_u32(self.buffer, 0x20)

    @property
    def has_call_stack(self) -> bool:
        """Whether or not there is a script return address on the stack -> the debugger can step out"""
        return read_u32(self.buffer, 0x2c) != 0

    @property
    def call_stack__start_addr_routine_infos(self) -> int:
        return read_u32(self.buffer, 0x24)

    @property
    def call_stack__start_addr_opcodes(self) -> int:
        return read_u32(self.buffer, 0x28)

    @property
    def call_stack__current_opcode_addr(self) -> int:
        return read_u32(self.buffer, 0x2c)

    @property
    def call_stack__current_opcode_addr_relative(self) -> int:
        """The stack opcode address relative to the start of the SSB file (after header), in words."""
        return int((self.call_stack__current_opcode_addr - self.call_stack__start_addr_routine_infos) / 2)

    @property
    def call_stack__start_addr_str_table(self) -> int:
        return read_u32(self.buffer, 0x30)

    @property
    def target_type(self) -> SsbRoutineType:
        return SsbRoutineType(read_u16(self.buffer, 8))

    @property
    def is_in_unionall(self):
        unionall_load_addr = emulator_unionall_load_address()
        return self.start_addr_routine_infos == unionall_load_addr and unionall_load_addr != 0

    @property
    def hanger_ssb(self):
        """
        The number of the SSB script this operation is in!
        Normally just returns the value stored in RAM for this field. If the current loaded address of the script
        is the same as unionall it will return 0 instead.
        """
        if not self.valid:
            return -1
        if self.is_in_unionall:
            return 0
        return read_i16(self.buffer, 0x10)

    def __eq__(self, other):
        if not isinstance(other, ScriptRuntimeStruct):
            return False
        if self.pnt_to_block_start is None or other.pnt_to_block_start is None:
            return self.buffer == other.buffer
        return self.pnt_to_block_start == other.pnt_to_block_start and self.script_struct_offset_from_start == other.script_struct_offset_from_start
