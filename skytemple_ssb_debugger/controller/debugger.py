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

from functools import partial
from typing import Optional

from desmume.emulator import DeSmuME
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_debugger.model.game_variable import GameVariable
from skytemple_ssb_debugger.model.ground_engine_state import GroundEngineState
from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct
from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager
from skytemple_ssb_debugger.sandbox.sandbox import read_ssb_str_mem


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


class DebuggerController:
    def __init__(self, emu: DeSmuME, print_callback):
        self.emu = emu
        self.is_active = False
        self.rom_data = None
        self.print_callback = print_callback
        self.ground_engine_state: Optional[GroundEngineState] = None

        self._log_operations = False
        self._log_debug_print = False
        self._log_printfs = False
        self._debug_mode = False
        self._log_ground_engine_state = False

    def enable(self, rom_data: Pmd2Data, ssb_file_manager: SsbFileManager):
        self.rom_data = rom_data

        arm9 = self.rom_data.binaries['arm9.bin']
        ov11 = self.rom_data.binaries['overlay/overlay_0011.bin']
        self.emu.memory.register_exec(ov11.functions['FuncThatCallsCommandParsing'].begin_absolute + 0x58, self.hook__log_operations)
        self.emu.memory.register_exec(arm9.functions['DebugPrint'].begin_absolute, partial(self.hook__log_printfs, 1))
        self.emu.memory.register_exec(arm9.functions['DebugPrint2'].begin_absolute, partial(self.hook__log_printfs, 0))
        self.emu.memory.register_exec(ov11.functions['ScriptCommandParsing'].begin_absolute + 0x3C40, self.hook__log_debug_print)
        self.emu.memory.register_exec(ov11.functions['ScriptCommandParsing'].begin_absolute + 0x15C8, self.hook__debug_mode)

        self.ground_engine_state = GroundEngineState(self.emu, self.rom_data, self.print_callback, ssb_file_manager)
        self.ground_engine_state.logging_enabled = self._log_ground_engine_state
        self.ground_engine_state.watch()

    def disable(self):
        arm9 = self.rom_data.binaries['arm9.bin']
        ov11 = self.rom_data.binaries['overlay/overlay_0011.bin']
        self.emu.memory.register_exec(ov11.functions['FuncThatCallsCommandParsing'].begin_absolute + 0x58, None)
        self.emu.memory.register_exec(arm9.functions['DebugPrint'].begin_absolute, None)
        self.emu.memory.register_exec(arm9.functions['DebugPrint2'].begin_absolute, None)
        self.emu.memory.register_exec(ov11.functions['ScriptCommandParsing'].begin_absolute + 0x3C40, None)
        self.emu.memory.register_exec(ov11.functions['ScriptCommandParsing'].begin_absolute + 0x15C8, None)
        self.is_active = False
        self.rom_data = None
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

    def debug_mode(self, value: bool):
        self._debug_mode = value

    def hook__log_operations(self, address, size):
        if self._log_operations:
            srs = ScriptRuntimeStruct(self.emu, self.rom_data, self.emu.memory.register_arm9.r6)

            self.print_callback(f"> {srs.target_type.name}({srs.target_id}): {srs.current_opcode.name} @{srs.current_opcode_addr:0x}")

    def hook__log_printfs(self, register_offset, address, size):
        if not self._log_printfs:
            return
        emu = self.emu
        dbg_string = str(NdsStrPnt(emu, emu.memory.register_arm9[register_offset]))

        # TODO: There's got to be a better way!(tm)
        dbg_string = dbg_string.replace('%p', '%x').rstrip('\n')
        args_count = dbg_string.count('%')

        if args_count == 0:
            self.print_callback(dbg_string)
        elif args_count == 1:
            self.print_callback(dbg_string % (
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1])
            ))
        elif args_count == 2:
            self.print_callback(dbg_string % (
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2])
            ))
        elif args_count == 3:
            self.print_callback(dbg_string % (
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3])
            ))
        elif args_count == 4:
            self.print_callback(dbg_string % (
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 4])
            ))
        elif args_count == 5:
            self.print_callback(dbg_string % (
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 4]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 5])
            ))
        elif args_count == 6:
            self.print_callback(dbg_string % (
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 4]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 5]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 6])
            ))
        elif args_count == 7:
            self.print_callback(dbg_string % (
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 4]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 5]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 6]),
                NdsStrPnt(emu, emu.memory.register_arm9.r8)
            ))
        elif args_count == 8:
            self.print_callback(dbg_string % (
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 4]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 5]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 6]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 7]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 8])
            ))
        elif args_count == 9:
            self.print_callback(dbg_string % (
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 4]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 5]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 6]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 7]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 8]),
                NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 9])
            ))

    def hook__log_debug_print(self, address, size):
        if not self._log_debug_print:
            return
        emu = self.emu

        ssb_str_table_pointer = emu.memory.unsigned.read_long(emu.memory.register_arm9.r4 + 0x20)
        current_op_pnt = emu.memory.register_arm9.r5
        current_op = emu.memory.register_arm9.r6
        if current_op == 0x6B:
            # debug_Print
            const_string = read_ssb_str_mem(emu.memory, ssb_str_table_pointer,
                                            emu.memory.unsigned.read_short(current_op_pnt + 2))
            self.print_callback(f"debug_Print: {const_string}")
        elif current_op == 0x6C:
            # debug_PrintFlag
            game_var_name, game_var_value = GameVariable.read(self.rom_data, emu.memory, emu.memory.unsigned.read_short(current_op_pnt + 2), 0)
            const_string = read_ssb_str_mem(emu.memory, ssb_str_table_pointer,
                                            emu.memory.unsigned.read_short(current_op_pnt + 4))
            self.print_callback(f"debug_PrintFlag: {const_string} - {game_var_name.name} = {game_var_value}")
        elif current_op == 0x6D:
            # debug_PrintScenario
            var_id = emu.memory.unsigned.read_short(current_op_pnt + 2)
            game_var_name, game_var_value = GameVariable.read(self.rom_data, emu.memory, var_id, 0)
            _, level_value = GameVariable.read(self.rom_data, emu.memory, var_id, 1)
            const_string = read_ssb_str_mem(emu.memory, ssb_str_table_pointer,
                                            emu.memory.unsigned.read_short(current_op_pnt + 4))
            self.print_callback(f"debug_PrintScenario: {const_string} - {game_var_name.name} = "
                                f"scenario:{game_var_value}, level:{game_var_value}")

    def hook__debug_mode(self, address, size):
        if self._debug_mode:
            self.emu.memory.register_arm9.r0 = 1 if self.emu.memory.register_arm9.r0 == 0 else 0
