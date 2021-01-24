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
import threading
from functools import partial
from typing import Optional, TYPE_CHECKING

from desmume.emulator import DeSmuME
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.model.breakpoint_manager import BreakpointManager
from skytemple_ssb_debugger.model.breakpoint_state import BreakpointState, BreakpointStateType
from skytemple_ssb_debugger.model.game_variable import GameVariable
from skytemple_ssb_debugger.model.ground_engine_state import GroundEngineState
from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct
from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager
from skytemple_ssb_debugger.sandbox.sandbox import read_ssb_str_mem
from skytemple_ssb_debugger.threadsafe import threadsafe_gtk_nonblocking, threadsafe_emu, synchronized

if TYPE_CHECKING:
    from skytemple_ssb_debugger.controller.main import MainController


class NdsStrPnt(int):
    """(Potential) pointer to a string. TODO: Move to py-desmume?"""

    def __new__(cls, emu: DeSmuME, pnt: int, *args):
        return super().__new__(NdsStrPnt, pnt)

    def __init__(self, emu: DeSmuME, pnt: int):
        super().__init__()
        self.mem = emu.memory
        self.pnt = pnt

    def __int__(self):
        return self.pnt

    def __str__(self):
        return self.mem.read_string(self.pnt)


debugger_state_lock = threading.Lock()

NB_DEBUG_FLAGS_1 = 0xC
NB_DEBUG_FLAGS_2 = 0x10

class DebuggerController:
    def __init__(self, emu_thread: EmulatorThread, print_callback, parent: 'MainController'):
        self.emu_thread = emu_thread
        self.is_active = False
        self.rom_data = None
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

        self._debug_flags_1 = [0]*NB_DEBUG_FLAGS_1
        self._debug_flags_2 = [0]*NB_DEBUG_FLAGS_2
        self._debug_flag_temp_input = 0
        
        self._log_operations = False
        self._log_debug_print = False
        self._log_printfs = False
        self._debug_mode = False
        # TODO: Move this to the dungeon debugger when implemented! And also all it's functionality and UI code!
        self._debug_dungeon_skip = False
        self._debug_dungeon_skip_pointer = None
        self._log_ground_engine_state = False
        self._boost = False

    @property
    def breakpoints_disabled(self):
        return self._breakpoints_disabled

    @breakpoints_disabled.setter
    def breakpoints_disabled(self, val):
        self._breakpoints_disabled = val

    def enable(self, rom_data: Pmd2Data, ssb_file_manager: SsbFileManager,
               breakpoint_manager: BreakpointManager, inform_ground_engine_start_cb):
        self.rom_data = rom_data
        self.breakpoint_manager = breakpoint_manager

        arm9 = self.rom_data.binaries['arm9.bin']
        ov11 = self.rom_data.binaries['overlay/overlay_0011.bin']
        self.register_exec(ov11.functions['FuncThatCallsCommandParsing'].begin_absolute + 0x58, self.hook__breaking_point)
        self.register_exec(arm9.functions['GetDebugFlag1'].begin_absolute, self.hook__get_debug_flag_get_input)
        self.register_exec(arm9.functions['GetDebugFlag2'].begin_absolute, self.hook__get_debug_flag_get_input)
        self.register_exec(arm9.functions['GetDebugFlag1'].begin_absolute+0x4, self.hook__get_debug_flag_1)
        self.register_exec(arm9.functions['GetDebugFlag2'].begin_absolute+0x4, self.hook__get_debug_flag_2)
        self.register_exec(arm9.functions['SetDebugFlag1'].begin_absolute, self.hook__set_debug_flag_1)
        self.register_exec(arm9.functions['SetDebugFlag2'].begin_absolute, self.hook__set_debug_flag_2)
        self.register_exec(arm9.functions['DebugPrint0'].begin_absolute, partial(self.hook__log_printfs, 0))
        self.register_exec(arm9.functions['DebugPrint'].begin_absolute, partial(self.hook__log_printfs, 1))
        self.register_exec(arm9.functions['DebugPrint2'].begin_absolute, partial(self.hook__log_printfs, 0))
        self.register_exec(ov11.functions['ScriptCommandParsing'].begin_absolute + 0x3C40, self.hook__log_debug_print)
        self.register_exec(ov11.functions['ScriptCommandParsing'].begin_absolute + 0x15C8, self.hook__debug_mode)
        self.register_write(arm9.pointers['DungeonData'].begin_absolute, self.hook__write__debug_dungeon_skip)

        self.ground_engine_state = GroundEngineState(
            self.emu_thread, self.rom_data, self.print_callback, inform_ground_engine_start_cb, ssb_file_manager,
            self.parent.context
        )
        self.ground_engine_state.logging_enabled = self._log_ground_engine_state
        self.ground_engine_state.watch()

    def disable(self):
        arm9 = self.rom_data.binaries['arm9.bin']
        ov11 = self.rom_data.binaries['overlay/overlay_0011.bin']
        self.register_exec(ov11.functions['FuncThatCallsCommandParsing'].begin_absolute + 0x58, None)
        self.register_exec(arm9.functions['GetDebugFlag1'].begin_absolute, None)
        self.register_exec(arm9.functions['GetDebugFlag2'].begin_absolute, None)
        self.register_exec(arm9.functions['GetDebugFlag1'].begin_absolute+0x4, None)
        self.register_exec(arm9.functions['GetDebugFlag2'].begin_absolute+0x4, None)
        self.register_exec(arm9.functions['SetDebugFlag1'].begin_absolute, None)
        self.register_exec(arm9.functions['SetDebugFlag2'].begin_absolute, None)
        self.register_exec(arm9.functions['DebugPrint0'].begin_absolute, None)
        self.register_exec(arm9.functions['DebugPrint'].begin_absolute, None)
        self.register_exec(arm9.functions['DebugPrint2'].begin_absolute, None)
        self.register_exec(ov11.functions['ScriptCommandParsing'].begin_absolute + 0x3C40, None)
        self.register_exec(ov11.functions['ScriptCommandParsing'].begin_absolute + 0x15C8, None)
        self.register_write(arm9.pointers['DungeonData'].begin_absolute, None)
        self.is_active = False
        self.rom_data = None
        self.ground_engine_state.remove_watches()
        self.ground_engine_state = None

    def register_exec(self, pnt, cb):
        threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.memory.register_exec(pnt, cb))

    def register_write(self, pnt, cb):
        threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.memory.register_write(pnt, cb))

    @synchronized(debugger_state_lock)
    def log_operations(self, value: bool):
        self._log_operations = value

    @synchronized(debugger_state_lock)
    def log_debug_print(self, value: bool):
        self._log_debug_print = value

    @synchronized(debugger_state_lock)
    def log_printfs(self, value: bool):
        self._log_printfs = value

    @synchronized(debugger_state_lock)
    def log_ground_engine_state(self, value: bool):
        self._log_ground_engine_state = value
        if self.ground_engine_state:
            self.ground_engine_state.logging_enabled = value

    @synchronized(debugger_state_lock)
    def debug_mode(self, value: bool):
        self._debug_mode = value

    @synchronized(debugger_state_lock)
    def debug_dungeon_skip(self, value: bool):
        self._debug_dungeon_skip = value
        if self.rom_data and (not self.ground_engine_state or not self.ground_engine_state.running):
            threadsafe_emu(self.emu_thread, lambda: self._set_dungeon_debug_skip())

    # >>> ALL CALLBACKS BELOW ARE RUNNING IN THE EMULATOR THREAD <<<

    def hook__breaking_point(self, address, size):
        """MAIN DEBUGGER HOOK. The emulator thread pauses here and publishes it's state via BreakpointState."""
        if self._boost:
            return
        debugger_state_lock.acquire()
        srs = ScriptRuntimeStruct(
            self.emu_thread.emu.memory, self.rom_data,
            self.emu_thread.emu.memory.register_arm9.r6, self.ground_engine_state.unionall_load_addr
        )
        if self._log_operations:
            self.print_callback(f"> {srs.target_type.name}({srs.target_id}): {srs.current_opcode.name} @{srs.current_opcode_addr:0x}")

        if self.breakpoint_manager:
            if not self._breakpoints_disabled and self._breakpoints_disabled_for_tick != self.emu_thread.current_frame_id:
                debugger_state_lock.release()
                self._breakpoints_disabled_for_tick = -1

                ssb = self.ground_engine_state.loaded_ssb_files[srs.hanger_ssb]
                if ssb is not None and (self._breakpoint_force or self.breakpoint_manager.has(
                    ssb.file_name, srs.current_opcode_addr_relative, srs.is_in_unionall,
                        srs.script_target_type, srs.script_target_slot_id
                )):
                    self.breakpoint_manager.reset_temporary()
                    self._breakpoint_force = False
                    state = BreakpointState(srs.hanger_ssb, srs)
                    state.acquire()
                    threadsafe_gtk_nonblocking(lambda: self.parent.break_pulled(state))
                    while not state.wait(0.0005) and state.state == BreakpointStateType.STOPPED:
                        # We haven't gotten the signal to resume yet, process pending events.
                        self.emu_thread.run_one_pending_task()
                    state.release()
                    if state.state == BreakpointStateType.FAIL_HARD:
                        # Ok, we won't pause again this tick.
                        self._breakpoints_disabled_for_tick = self.emu_thread.current_frame_id
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
            else:
                debugger_state_lock.release()
        else:
            debugger_state_lock.release()

    @synchronized(debugger_state_lock)
    def hook__get_debug_flag_get_input(self, address, size):
        self._debug_flag_temp_input = self.emu_thread.emu.memory.register_arm9.r0
    
    @synchronized(debugger_state_lock)
    def hook__get_debug_flag_1(self, address, size):
        self.emu_thread.emu.memory.register_arm9.r0 = self._debug_flags_1[self._debug_flag_temp_input]
        
    @synchronized(debugger_state_lock)
    def hook__get_debug_flag_2(self, address, size):
        self.emu_thread.emu.memory.register_arm9.r0 = self._debug_flags_2[self._debug_flag_temp_input]
        
    @synchronized(debugger_state_lock)
    def hook__set_debug_flag_1(self, address, size):
        flag_id = self.emu_thread.emu.memory.register_arm9.r0
        value = self.emu_thread.emu.memory.register_arm9.r1
        threadsafe_gtk_nonblocking(lambda: self.parent.set_check_debug_flag_1(flag_id, value))
    
    @synchronized(debugger_state_lock)
    def hook__set_debug_flag_2(self, address, size):
        flag_id = self.emu_thread.emu.memory.register_arm9.r0
        value = self.emu_thread.emu.memory.register_arm9.r1
        threadsafe_gtk_nonblocking(lambda: self.parent.set_check_debug_flag_2(flag_id, value))

    @synchronized(debugger_state_lock)
    def set_debug_flag_1(self, flag_id, value):
        self._debug_flags_1[flag_id] = value
        
    @synchronized(debugger_state_lock)
    def set_debug_flag_2(self, flag_id, value):
        self._debug_flags_2[flag_id] = value
    
    @synchronized(debugger_state_lock)
    def hook__log_printfs(self, register_offset, address, size):
        if not self._log_printfs or self._boost:
            return
        emu = self.emu_thread.emu
        dbg_string = str(NdsStrPnt(emu, emu.memory.register_arm9[register_offset]))

        # TODO: There's got to be a better way!(tm)
        dbg_string = dbg_string.replace('%p', '%x').rstrip('\n')
        args_count = dbg_string.count('%')
        self.print_callback(dbg_string % tuple([NdsStrPnt(emu, emu.memory.register_arm9[register_offset + i + 1]) for i in range(args_count)]))

    @synchronized(debugger_state_lock)
    def hook__log_debug_print(self, address, size):
        if not self._log_debug_print or self._boost:
            return
        emu = self.emu_thread.emu

        srs = ScriptRuntimeStruct(self.emu_thread, self.rom_data,
                                  emu.memory.register_arm9.r4, self.ground_engine_state.unionall_load_addr)

        ssb_str_table_pointer = srs.start_addr_str_table
        current_op_pnt = emu.memory.register_arm9.r5
        current_op = emu.memory.register_arm9.r6
        if current_op == 0x6B:
            # debug_Print
            const_string = read_ssb_str_mem(emu.memory, ssb_str_table_pointer,
                                            emu.memory.unsigned.read_short(current_op_pnt + 2))
            self.print_callback(f"debug_Print: {const_string}")
        elif current_op == 0x6C:
            # debug_PrintFlag
            game_var_name, game_var_value = GameVariable.read(
                emu.memory, self.rom_data, emu.memory.unsigned.read_short(current_op_pnt + 2), 0, srs
            )
            const_string = read_ssb_str_mem(emu.memory, ssb_str_table_pointer,
                                            emu.memory.unsigned.read_short(current_op_pnt + 4))
            self.print_callback(f"debug_PrintFlag: {const_string} - {game_var_name.name} = {game_var_value}")
        elif current_op == 0x6D:
            # debug_PrintScenario
            var_id = emu.memory.unsigned.read_short(current_op_pnt + 2)
            game_var_name, game_var_value = GameVariable.read(emu.memory, self.rom_data, var_id, 0, srs)
            _, level_value = GameVariable.read(emu.memory, self.rom_data, var_id, 1, srs)
            const_string = read_ssb_str_mem(emu.memory, ssb_str_table_pointer,
                                            emu.memory.unsigned.read_short(current_op_pnt + 4))
            self.print_callback(f"debug_PrintScenario: {const_string} - {game_var_name.name} = "
                                f"scenario:{game_var_value}, level:{game_var_value}")

    @synchronized(debugger_state_lock)
    def hook__debug_mode(self, address, size):
        if self._debug_mode:
            self.emu_thread.emu.memory.register_arm9.r0 = 1 if self.emu_thread.emu.memory.register_arm9.r0 == 0 else 0

    @synchronized(debugger_state_lock)
    def hook__write__debug_dungeon_skip(self, address, size):
        if not self.ground_engine_state or not self.ground_engine_state.running:
            self._set_dungeon_debug_skip()

    def hook__read__debug_dungeon_skip(self, address, size):
        if self._debug_dungeon_skip and (not self.ground_engine_state or not self.ground_engine_state.running):
            self.emu_thread.emu.memory.write_byte(address, 1)

    def print_callback(self, text: str):
        threadsafe_gtk_nonblocking(lambda: self._print_callback_fn(text))

    def _get_next_opcode_addr(self, current_opcode_addr: int, current_opcode_addr_relative: int):
        """ Returns current_opcode_addr_relative + the length of the current opcode. """
        current_opcode = self.rom_data.script_data.op_codes__by_id[
            self.emu_thread.emu.memory.unsigned.read_short(current_opcode_addr)
        ]
        # the length is at least 2 (for the opcode itself
        len = 2
        if current_opcode.params == -1:
            # if the opcode is var length, the first parameter contains that length
            len += 2 + self.emu_thread.emu.memory.unsigned.read_short(current_opcode_addr + 0x02)
        else:
            len += 2 * current_opcode.params
        return current_opcode_addr_relative + len

    def _set_dungeon_debug_skip(self):
        pointer = self.emu_thread.emu.memory.unsigned.read_long(self.rom_data.binaries['arm9.bin'].pointers['DungeonData'].begin_absolute)
        if pointer != 0:
            self.emu_thread.emu.memory.write_byte(pointer + 6, 1 if self._debug_dungeon_skip else 0)
            self.emu_thread.emu.memory.write_byte(pointer + 8, 1 if self._debug_dungeon_skip else 0)
            if self._debug_dungeon_skip_pointer is not None and self._debug_dungeon_skip_pointer != pointer:
                self.emu_thread.emu.memory.register_read(self._debug_dungeon_skip_pointer + 6, None)
                self.emu_thread.emu.memory.register_read(self._debug_dungeon_skip_pointer + 8, None)
            self._debug_dungeon_skip_pointer = pointer
            self.emu_thread.emu.memory.register_read(pointer + 6, self.hook__read__debug_dungeon_skip)
            self.emu_thread.emu.memory.register_read(pointer + 8, self.hook__read__debug_dungeon_skip)

    @synchronized(debugger_state_lock)
    def set_boost(self, state):
        self._boost = state
        self.ground_engine_state.set_boost(state)
