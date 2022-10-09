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
from typing import Callable, Union

from explorerscript.ssb_converting.ssb_data_types import SsbRoutineType
from skytemple_ssb_emulator import *
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptOpCode


class ScriptRuntimeStruct:
    def __init__(self, rom_data: Pmd2Data, pnt: Union[int, Callable], parent=None):
        super().__init__()
        self.rom_data = rom_data
        # Can either be int or a callable. If it's a callable, it's called each time
        # a value is accesed to retreive the current position.
        self._pnt = pnt
        # for debugging
        self._parent = parent

    @property
    def pnt(self):
        if callable(self._pnt):
            return self._pnt()
        return self._pnt

    @property
    def valid(self):
        """The first entry contains a pointer to something unknown (global script state?) when valid"""
        return emulator_read_long(self.pnt) != 0

    @property
    def script_target_type(self) -> SsbRoutineType:
        """The type of target for this script struct (ACTOR, OBJECT, PERFORMER) or GENERIC for global script"""
        idx = emulator_read_long(self.pnt + 0x08)
        return SsbRoutineType.create_for_index(idx)

    @property
    def script_target_slot_id(self) -> int:
        """The slot id of the target type's entity list (always 0 for global script)"""
        script_target_id: int
        script_target_address: int
        script_target_id = script_target_address = emulator_read_long(self.pnt + 0x04)
        if script_target_address != 0:
            script_target_id = emulator_read_short(script_target_address)
        return script_target_id

    @property
    def current_opcode(self) -> Pmd2ScriptOpCode:
        address_current_opcode = self.current_opcode_addr
        return self.rom_data.script_data.op_codes__by_id[emulator_read_short(address_current_opcode)]

    @property
    def start_addr_routine_infos(self) -> int:
        return emulator_read_long(self.pnt + 0x14)

    @property
    def start_addr_opcodes(self) -> int:
        return emulator_read_long(self.pnt + 0x18)

    @property
    def current_opcode_addr(self) -> int:
        return emulator_read_long(self.pnt + 0x1c)

    @property
    def current_opcode_addr_relative(self) -> int:
        """The current opcode address relative to the start of the SSB file (after header), in words."""
        return int((self.current_opcode_addr - self.start_addr_routine_infos) / 2)

    @property
    def start_addr_str_table(self) -> int:
        return emulator_read_long(self.pnt + 0x20)

    @property
    def has_call_stack(self) -> bool:
        """Whether or not there is a script return address on the stack -> the debugger can step out"""
        return emulator_read_long(self.pnt + 0x2c) != 0

    @property
    def call_stack__start_addr_routine_infos(self) -> int:
        return emulator_read_long(self.pnt + 0x24)

    @property
    def call_stack__start_addr_opcodes(self) -> int:
        return emulator_read_long(self.pnt + 0x28)

    @property
    def call_stack__current_opcode_addr(self) -> int:
        return emulator_read_long(self.pnt + 0x2c)

    @property
    def call_stack__current_opcode_addr_relative(self) -> int:
        """The stack opcode address relative to the start of the SSB file (after header), in words."""
        return int((self.call_stack__current_opcode_addr - self.call_stack__start_addr_routine_infos) / 2)

    @property
    def call_stack__start_addr_str_table(self) -> int:
        return emulator_read_long(self.pnt + 0x30)

    @property
    def target_type(self) -> SsbRoutineType:
        return SsbRoutineType(emulator_read_short(self.pnt + 8))

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
        return emulator_read_short_signed(self.pnt + 0x10)

    @property
    def target_id(self) -> int:
        script_target_id: int
        script_target_address: int
        script_target_id = script_target_address = emulator_read_long(self.pnt + 4)
        if script_target_address != 0:
            script_target_id = emulator_read_short(script_target_address)
        return script_target_id

    def __eq__(self, other):
        if not isinstance(other, ScriptRuntimeStruct):
            return False
        return self.pnt == other.pnt
