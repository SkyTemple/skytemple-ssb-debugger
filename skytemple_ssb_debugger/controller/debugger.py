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
from typing import TYPE_CHECKING, Optional, Iterable

from range_typed_integers import u32
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_emulator import emulator_register_script_debug, emulator_register_debug_print, \
    emulator_register_debug_flag, emulator_set_debug_mode, emulator_set_debug_flag_1, emulator_set_debug_flag_2, \
    EmulatorLogType, emulator_unregister_script_debug, \
    emulator_unregister_debug_print, emulator_unregister_debug_flag, emulator_debug_breakpoints_disabled_get, \
    emulator_debug_breakpoints_disabled_set, BreakpointState, emulator_set_debug_dungeon_skip

from skytemple_ssb_debugger.model.ground_engine_state import GroundEngineState
from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct
from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager

if TYPE_CHECKING:
    from skytemple_ssb_debugger.controller.main import MainController


NB_DEBUG_FLAGS_1 = 0xC
NB_DEBUG_FLAGS_2 = 0x10


class DebuggerController:
    def __init__(self, print_callback, parent: 'MainController'):
        self.rom_data: Optional[Pmd2Data] = None
        self._print_callback_fn = print_callback
        self.ground_engine_state: Optional[GroundEngineState] = None
        self.parent: 'MainController' = parent

        self._debug_flags_1 = [0]*NB_DEBUG_FLAGS_1
        self._debug_flags_2 = [0]*NB_DEBUG_FLAGS_2
        self._debug_flag_temp_input = 0
        
        self._log_operations = False
        self._log_debug_print = False
        self._log_printfs = False
        self._log_ground_engine_state = False
        self._boost = False

    @property
    def breakpoints_disabled(self):
        return emulator_debug_breakpoints_disabled_get()

    @breakpoints_disabled.setter
    def breakpoints_disabled(self, val):
        emulator_debug_breakpoints_disabled_set(val)

    def enable(
            self, rom_data: Pmd2Data, ssb_file_manager: SsbFileManager,
            inform_ground_engine_start_cb,
            *, debug_mode: bool, debug_flag_1: Iterable[bool], debug_flag_2: Iterable[bool]
    ):
        self.rom_data = rom_data

        arm9 = self.rom_data.bin_sections.arm9
        ov11 = self.rom_data.bin_sections.overlay11
        emulator_register_script_debug(
            [ov11.functions.FuncThatCallsCommandParsing.absolute_address + 0x58],
            self.hook__breaking_point,
        )
        emulator_register_debug_print(
            arm9.functions.DebugPrint0.absolute_addresses,  # register offset = 0: -> registers[register_offset + i + 1]
            arm9.functions.DebugPrint.absolute_addresses,   # register offset = 1
            [ov11.functions.ScriptCommandParsing.absolute_address + 0x3C40],
            self.hook__log_msg
        )
        emulator_register_debug_flag(
            arm9.functions.GetDebugFlag.absolute_addresses,
            arm9.functions.GetDebugLogFlag.absolute_addresses,
            arm9.functions.SetDebugFlag.absolute_addresses,
            arm9.functions.SetDebugLogFlag.absolute_addresses,
            [ov11.functions.ScriptCommandParsing.absolute_address + 0x15C8],
            self.hook__set_debug_flag
        )

        # Send current debug flags and debug mode flag to emulator
        emulator_set_debug_mode(debug_mode)
        for i, iv in enumerate(debug_flag_1):
            emulator_set_debug_flag_1(i, iv)
        for j, jv in enumerate(debug_flag_2):
            emulator_set_debug_flag_2(j, jv)

        self.ground_engine_state = GroundEngineState(
            self.rom_data, self._print_callback_fn, inform_ground_engine_start_cb, self.parent.do_poll_emulator, ssb_file_manager,
            self.parent.context
        )
        self.ground_engine_state.logging_enabled = self._log_ground_engine_state
        self.ground_engine_state.watch()

    def disable(self):
        emulator_unregister_script_debug()
        emulator_unregister_debug_print()
        emulator_unregister_debug_flag()
        self.rom_data = None
        if self.ground_engine_state:
            self.ground_engine_state.remove_watches()
            self.ground_engine_state = None

    def log_operations(self, value: bool):
        self._log_operations = value

    def log_debug_print(self, value: bool):
        self._log_debug_print = value

    def log_printfs(self, value: bool):
        self._log_printfs = value

    def log_ground_engine_state(self, value: bool):
        self._log_ground_engine_state = value
        if self.ground_engine_state:
            self.ground_engine_state.logging_enabled = value

    def hook__breaking_point(
        self,
        break_state: Optional[BreakpointState],
        srs_mem: bytes,
        script_target_slot_id: u32,
        current_opcode: u32
    ):
        if not self._boost:
            assert self.rom_data is not None and self.ground_engine_state is not None
            if self._log_operations:
                srs = ScriptRuntimeStruct.from_data(
                    self.rom_data, u32(0), srs_mem, script_target_slot_id
                )
                current_opcode_obj = self.rom_data.script_data.op_codes__by_id[current_opcode]
                self._print_callback_fn(f"> {srs.target_type.name}({srs.script_target_slot_id}): {current_opcode_obj.name} @{srs.current_opcode_addr:0x}")
        if break_state:
            self.parent.break_pulled(break_state)

    def hook__log_msg(self, log_type: EmulatorLogType, msg: str):
        if log_type == EmulatorLogType.Printfs and not self._log_printfs:
            return
        if log_type == EmulatorLogType.DebugPrint and not self._log_debug_print:
            return
        self._print_callback_fn(msg)

    def hook__set_debug_flag(self, var_id: int, flag_id: int, value: int):
        self.parent.set_check_debug_flag(var_id, flag_id, value)

    def set_boost(self, state):
        self._boost = state
        if self.ground_engine_state:
            self.ground_engine_state.set_boost(state)

    def debug_dungeon_skip(self, value: bool):
        if self.rom_data:
            emulator_set_debug_dungeon_skip(self.rom_data.bin_sections.overlay29.data.DUNGEON_PTR.absolute_address, value)
