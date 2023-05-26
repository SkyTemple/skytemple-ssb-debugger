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
    emulator_tick, EmulatorLogType, emulator_unregister_script_debug, \
    emulator_unregister_debug_print, emulator_unregister_debug_flag

from skytemple_ssb_debugger.model.breakpoint_manager import BreakpointManager
from skytemple_ssb_debugger.model.breakpoint_state import BreakpointState, BreakpointStateType
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
        self.breakpoint_manager: Optional[BreakpointManager] = None

        # Flag to completely disable breaking
        self._breakpoints_disabled = False
        # Flag to disable breaking for one single tick. This is reset to -1 if the tick number changes.
        self._breakpoints_disabled_for_tick = -1
        # Force a halt at the breakpoint hook
        self._breakpoint_force = False
        self._breakpoint_state: Optional[BreakpointState] = None

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
        return self._breakpoints_disabled

    @breakpoints_disabled.setter
    def breakpoints_disabled(self, val):
        self._breakpoints_disabled = val

    def enable(
            self, rom_data: Pmd2Data, ssb_file_manager: SsbFileManager,
            breakpoint_manager: BreakpointManager, inform_ground_engine_start_cb,
            *, debug_mode: bool, debug_flag_1: Iterable[bool], debug_flag_2: Iterable[bool]
    ):
        self.rom_data = rom_data
        self.breakpoint_manager = breakpoint_manager

        arm9 = self.rom_data.bin_sections.arm9
        ov11 = self.rom_data.bin_sections.overlay11
        emulator_register_script_debug(
            [ov11.functions.FuncThatCallsCommandParsing.absolute_address + 0x58],
            self.hook__breaking_point__start,
            self.hook__breaking_point__resume
        )
        emulator_register_debug_print(
            arm9.functions.DebugPrint0.absolute_addresses,  # register offset = 0: -> registers[register_offset + i + 1]
            arm9.functions.DebugPrint.absolute_addresses,   # register offset = 1
            [ov11.functions.ScriptCommandParsing.absolute_address + 0x3C40],
            self.hook__log_msg
        )
        emulator_register_debug_flag(
            arm9.functions.GetDebugFlag1.absolute_address,
            arm9.functions.GetDebugFlag2.absolute_address,
            arm9.functions.SetDebugFlag1.absolute_address,
            arm9.functions.SetDebugFlag2.absolute_address,
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
            self.rom_data, self._print_callback_fn, self.parent.do_poll_emulator, inform_ground_engine_start_cb, ssb_file_manager,
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

    def hook__breaking_point__start(self, script_runtime_struct_mem: bytes, script_target_slot_id: u32, current_opcode: u32):
        """MAIN DEBUGGER HOOK. The emulator pauses here and publishes its state via BreakpointState."""
        if self._boost:
            return
        assert self.rom_data is not None and self.ground_engine_state is not None
        srs = ScriptRuntimeStruct.from_data(
            self.rom_data, script_runtime_struct_mem, script_target_slot_id
        )
        if self._log_operations:
            current_opcode_obj = self.rom_data.script_data.op_codes__by_id[current_opcode]
            self._print_callback_fn(f"> {srs.target_type.name}({srs.script_target_slot_id}): {current_opcode_obj.name} @{srs.current_opcode_addr:0x}")

        if self.breakpoint_manager:
            if not self._breakpoints_disabled and self._breakpoints_disabled_for_tick != emulator_tick():
                self._breakpoints_disabled_for_tick = -1

                ssb = self.ground_engine_state.loaded_ssb_files[srs.hanger_ssb]
                if ssb is not None and (self._breakpoint_force or self.breakpoint_manager.has(
                    ssb.file_name, srs.current_opcode_addr_relative, srs.is_in_unionall,
                        srs.script_target_type, srs.script_target_slot_id
                )):
                    self.breakpoint_manager.reset_temporary()
                    self._breakpoint_force = False
                    self._breakpoint_state = BreakpointState(srs.hanger_ssb, srs)
                    if TYPE_CHECKING:
                        assert self._breakpoint_state is not None
                    self.parent.break_pulled(self._breakpoint_state)

    def hook__breaking_point__resume(self):
        assert self._breakpoint_state is not None and self.breakpoint_manager is not None
        state = self._breakpoint_state
        srs = state.script_struct

        if state.state == BreakpointStateType.FAIL_HARD:
            # Ok, we won't pause again this tick.
            self._breakpoints_disabled_for_tick = emulator_tick()
        elif state.state == BreakpointStateType.RESUME:
            # We just resume, this is easy :)
            pass
        elif state.state == BreakpointStateType.STEP_NEXT:
            # We force a break at the next run of this hook.
            self._breakpoint_force = True
        elif state.state == BreakpointStateType.STEP_INTO:
            # We break at whatever is executed next for the current script target.
            self.breakpoint_manager.add_temporary(
                srs.script_target_type, srs.script_target_slot_id
            )
        elif state.state == BreakpointStateType.STEP_OVER:
            # We break at the next opcode in the current script file
            self.breakpoint_manager.add_temporary(
                srs.script_target_type, srs.script_target_slot_id,
                is_in_unionall=srs.is_in_unionall
            )
            # If the current op is the last one (we will step out next) this will lead to issues.
            # We need to alternatively break at the current stack opcode (see STEP_OUT).
            if srs.has_call_stack:
                self.breakpoint_manager.add_temporary(
                    srs.script_target_type, srs.script_target_slot_id,
                    opcode_addr=srs.call_stack__current_opcode_addr_relative
                )
        elif state.state == BreakpointStateType.STEP_OUT:
            if srs.has_call_stack:
                # We break at the opcode address stored on the call stack position.
                self.breakpoint_manager.add_temporary(
                    srs.script_target_type, srs.script_target_slot_id,
                    opcode_addr=srs.call_stack__current_opcode_addr_relative
                )
            else:
                # We just resume
                pass
        elif state.state == BreakpointStateType.STEP_MANUAL:
            # We break at the requested opcode offset in the current hanger.
            self.breakpoint_manager.add_temporary(
                srs.script_target_type, srs.script_target_slot_id,
                is_in_unionall=srs.is_in_unionall,
                opcode_addr=state.manual_step_opcode_offset
            )

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
