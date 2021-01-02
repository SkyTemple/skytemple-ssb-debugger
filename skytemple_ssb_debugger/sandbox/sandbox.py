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

from functools import partial

from desmume.emulator import DeSmuME, DeSmuME_Memory
from skytemple_files.common import string_codec
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptOpCode
from skytemple_files.common.ppmdu_config.xml_reader import Pmd2XmlReader
from skytemple_ssb_debugger.model.game_variable import GameVariable

string_codec.init()


class ScriptStruct:
    def __init__(self, mem: DeSmuME_Memory, pnt: int):
        self.mem = mem
        self.pnt = pnt

    def __str__(self):
        # Points to another struct!!!
        unk0_address = self.mem.unsigned.read_long(self.pnt)
        script_target_id = script_target_address = self.mem.unsigned.read_long(self.pnt + 4)
        if script_target_address != 0:
            script_target_id = self.mem.unsigned.read_short(script_target_address)

        script_target_type = self.mem.unsigned.read_short(self.pnt + 8)
        unkC = self.mem.unsigned.read_short(self.pnt + 0xC)
        unkE = self.mem.unsigned.read_short(self.pnt + 0xE)
        hanger = self.mem.unsigned.read_short(self.pnt + 0x10)
        sector = self.mem.unsigned.read_short(self.pnt + 0x12)

        ssb_file_grp_addr = self.mem.unsigned.read_long(self.pnt + 0x14)
        ssb_file_opc_addr = self.mem.unsigned.read_long(self.pnt + 0x18)

        address_current_opcode = self.mem.unsigned.read_long(self.pnt + 0x1c)
        # TODO: not global
        op_code: Pmd2ScriptOpCode = static_data.script_data.op_codes__by_id[self.mem.unsigned.read_short(address_current_opcode)]

        ssb_file_str_table_addr = self.mem.unsigned.read_long(self.pnt + 0x20)
        stack_ssb_file_grp_addr = self.mem.unsigned.read_long(self.pnt + 0x24)  # Possibly has something to do with parent ssb file state -> we are in unionall!
        stack_ssb_file_opc_addr = self.mem.unsigned.read_long(self.pnt + 0x28)  # see above
        stack_address_opcode = self.mem.unsigned.read_long(self.pnt + 0x2c)  # see above
        stack_ssb_file_str_table_addr = self.mem.unsigned.read_long(self.pnt + 0x30)  # see above
        unk34 = self.mem.unsigned.read_long(self.pnt + 0x34)  # Previous opcode?
        unk38 = self.mem.unsigned.read_long(self.pnt + 0x38)  # Previous opcode + 2
        unk3c = self.mem.unsigned.read_short(self.pnt + 0x3c)
        unk40 = self.mem.unsigned.read_short(self.pnt + 0x40)
        unk42 = self.mem.unsigned.read_short(self.pnt + 0x42)
        unk44 = self.mem.unsigned.read_long(self.pnt + 0x44)
        unk48 = self.mem.unsigned.read_long(self.pnt + 0x48)
        unk4c = self.mem.unsigned.read_long(self.pnt + 0x4c)
        # 6c: Seems to be some sort of list of local variables here. uint8?
        unk6c = self.mem.unsigned.read_long(self.pnt + 0x6c)
        unk6d = self.mem.unsigned.read_long(self.pnt + 0x6d)
        unk6e = self.mem.unsigned.read_long(self.pnt + 0x6e)
        unk6f = self.mem.unsigned.read_long(self.pnt + 0x6f)
        # f0

        with open('/tmp/ops.bin', 'wb') as f:
            f.write(self.mem.unsigned[self.pnt:self.pnt + 0x60])

        str = f"AT 0x{self.pnt:>8x}: **script_target_id:{script_target_id} - script_target_type:{script_target_type} - " \
               f"unkC:{unkC} - unkE:{unkE} - hanger:{hanger} - sector:{sector} - ssb_file_grp_addr:0x{ssb_file_grp_addr:0x} " \
               f"- ssb_file_opc_addr:0x{ssb_file_opc_addr:0x} - *current_op_code:{op_code.name:<30} (@0x{address_current_opcode:>8x}) - " \
               f"ssb_file_str_table_addr:0x{ssb_file_str_table_addr:0x} - stack_ssb_file_grp_addr:0x{stack_ssb_file_grp_addr:>8x} - stack_ssb_file_opc_addr:0x{stack_ssb_file_opc_addr:>8x} - " \
               f"stack_address_opcode:0x{stack_address_opcode:>8x} - stack_ssb_file_str_table_addr:0x{stack_ssb_file_str_table_addr:>8x} - unk34:0x{unk34:>8x} - unk38:0x{unk38:>8x} - unk3c:{unk3c} - " \
               f"unk40:0x{unk40:>8x} - unk42:0x{unk42:>8x} - unk44:0x:{unk44:>8x} -unk48:0x{unk48:>8x} - " \
               f"unk4c:0x{unk4c:>8x} - unk6c-unk6f:0x {unk6c:0x} {unk6d:0x} {unk6e:0x} {unk6f:0x}"

        if unk0_address != 0:
            unk0_0 = self.mem.unsigned.read_long(unk0_address + 0x00)
            unk0_4 = self.mem.unsigned.read_long(unk0_address + 0x04)
            unk0_8 = self.mem.unsigned.read_long(unk0_address + 0x08)
            unk0_C = self.mem.unsigned.read_long(unk0_address + 0x0C)
            # ...?
        
            str += f'\n       ' \
                   f'AT unk0 (0x{unk0_address:>8x}): unk0_0:0x{unk0_0:>8x} - unk0_4:0x{unk0_4:>8x} - unk0_8:8x{unk0_8:>8x} - unk0_C:0x{unk0_C:>8x}'
            
            if unk0_4 != 0:
                unk0_4_0 = self.mem.unsigned.read_long(unk0_4 + 0x00)
                unk0_4_4 = self.mem.unsigned.read_long(unk0_4 + 0x04)
                unk0_4_8 = self.mem.unsigned.read_long(unk0_4 + 0x08)
                unk0_4_C = self.mem.unsigned.read_long(unk0_4 + 0x0C)
                str += f'\n       ' \
                       f'AT unk0_4 (0x{unk0_4:>8x}): unk0_4_0:0x{unk0_4_0:>8x} - unk0_4_4:0x{unk0_4_4:>8x} - unk0_4_8:8x{unk0_4_8:>8x} - unk0_4_C:0x{unk0_4_C:>8x}'

            if unk0_8 != 0:
                unk0_8_0 = self.mem.unsigned.read_long(unk0_8 + 0x00)
                unk0_8_4 = self.mem.unsigned.read_long(unk0_8 + 0x04)
                unk0_8_8 = self.mem.unsigned.read_long(unk0_8 + 0x08)
                unk0_8_C = self.mem.unsigned.read_long(unk0_8 + 0x0C)
                str += f'\n       ' \
                       f'AT unk0_8 (0x{unk0_8:>8x}): unk0_8_0:0x{unk0_8_0:>8x} - unk0_8_4:0x{unk0_8_4:>8x} - unk0_8_8:8x{unk0_8_8:>8x} - unk0_8_C:0x{unk0_8_C:>8x}'

            if unk0_C != 0:
                unk0_C_0 = self.mem.unsigned.read_long(unk0_C + 0x00)
                unk0_C_4 = self.mem.unsigned.read_long(unk0_C + 0x04)
                unk0_C_8 = self.mem.unsigned.read_long(unk0_C + 0x08)
                unk0_C_C = self.mem.unsigned.read_long(unk0_C + 0x0C)
                str += f'\n       ' \
                       f'AT unk0_C (0x{unk0_C:>8x}): unk0_C_0:0x{unk0_C_0:>8x} - unk0_C_4:0x{unk0_C_4:>8x} - unk0_C_8:8x{unk0_C_8:>8x} - unk0_C_C:0x{unk0_C_C:>8x}'

        return str


def hook__primary_opcode_parsing(emu, address, size):
    address_of_struct = emu.memory.register_arm9.r6
    print("MAIN - " + str(ScriptStruct(emu.memory, address_of_struct)))


def hook__secondary_opcode_parsing(emu, address, size):
    address_of_struct = emu.memory.register_arm9.r9
    #print("SEC  - " + str(ScriptStruct(emu.memory, address_of_struct)))


def hook__beginning_script_loop(emu, address, size):
    #print(f"LAST RETURN CODE: {emu.memory.register_arm9.r0}")
    pass


class NdsStrPnt(int):
    """(Potential) pointer to a string. TODO: Move to py-desmume."""
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


def hook__debug_print(register_offset, emu, address, size):
    dbg_string = str(NdsStrPnt(emu, emu.memory.register_arm9[register_offset]))

    # TODO: There's got to be a better way!(tm)
    dbg_string = dbg_string.replace('%p', '%x').rstrip('\n')
    args_count = dbg_string.count('%')

    if args_count == 0:
        print(dbg_string)
    elif args_count == 1:
        print(dbg_string % (
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1])
        ))
    elif args_count == 2:
        print(dbg_string % (
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2])
        ))
    elif args_count == 3:
        print(dbg_string % (
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3])
        ))
    elif args_count == 4:
        print(dbg_string % (
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 4])
        ))
    elif args_count == 5:
        print(dbg_string % (
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 4]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 5])
        ))
    elif args_count == 6:
        print(dbg_string % (
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 4]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 5]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 6])
        ))
    elif args_count == 7:
        print(dbg_string % (
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 1]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 2]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 3]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 4]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 5]),
            NdsStrPnt(emu, emu.memory.register_arm9[register_offset + 6]),
            NdsStrPnt(emu, emu.memory.register_arm9.r8)
        ))
    elif args_count == 8:
        print(dbg_string % (
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
        print(dbg_string % (
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


def read_ssb_str_mem(mem, str_table_pointer, index):
    rel_pointer_to_const_str = mem.unsigned.read_short(str_table_pointer + (index * 2))
    abs_pointer_to_const_str = str_table_pointer + rel_pointer_to_const_str
    return mem.read_string(abs_pointer_to_const_str, string_codec.PMD2_STR_ENCODER)


def read_game_var(mem: DeSmuME_Memory, var_id: int, read_offset: int):
    return GameVariable.read(mem, static_data, var_id, read_offset)


def write_game_var(mem: DeSmuME_Memory, var_id: int, value, read_offset: int):
    return GameVariable.write(mem, static_data, var_id, value, read_offset)


def hook__debug_print_script_engine(emu, address, size):
    ssb_str_table_pointer = emu.memory.unsigned.read_long(emu.memory.register_arm9.r4 + 0x20)
    current_op_pnt = emu.memory.register_arm9.r5
    current_op = emu.memory.register_arm9.r6
    if current_op == 0x6B:
        # debug_Print
        const_string = read_ssb_str_mem(emu.memory, ssb_str_table_pointer, emu.memory.unsigned.read_short(current_op_pnt + 2))
        print(f"debug_Print: {const_string}")
    elif current_op == 0x6C:
        # debug_PrintFlag
        game_var_name, game_var_value = read_game_var(emu.memory, emu.memory.unsigned.read_short(current_op_pnt + 2), 0)
        const_string = read_ssb_str_mem(emu.memory, ssb_str_table_pointer, emu.memory.unsigned.read_short(current_op_pnt + 4))
        print(f"debug_PrintFlag: {const_string} - {game_var_name.name}={game_var_value}")
    elif current_op == 0x6D:
        # debug_PrintScenario
        # todo: better output
        game_var_name, game_var_value = read_game_var(emu.memory, emu.memory.unsigned.read_short(current_op_pnt + 2), 0)
        const_string = read_ssb_str_mem(emu.memory, ssb_str_table_pointer, emu.memory.unsigned.read_short(current_op_pnt + 4))
        print(f"debug_PrintScenario: {const_string} - {game_var_name.name}={game_var_value}")


def hook__debug_enable_branch(emu, address, size):
    emu.memory.register_arm9.r0 = 1 if emu.memory.register_arm9.r0 == 0 else 0


def hook_get_script_variable_value(emu, with_offset, address, size):
    unk_6c = emu.memory.unsigned.read_long(emu.memory.register_arm9.r1)
    var_id = emu.memory.register_arm9.r2

    read_offset = 0
    if with_offset:
        read_offset = emu.memory.register_arm9.r4

    # TESTING.
    #for i in range(0, 8):
    #    write_game_var(emu.memory, static_data.script_data.game_variables__by_name['SPECIAL_EPISODE_OPEN_OLD'].id, i, 1)
    #    write_game_var(emu.memory, static_data.script_data.game_variables__by_name['SPECIAL_EPISODE_OPEN'].id, i, 1)
    #write_game_var(emu.memory, static_data.script_data.game_variables__by_name['GAME_MODE'].id, 0, 1)
    #write_game_var(emu.memory, static_data.script_data.game_variables__by_name['SPECIAL_EPISODE_TYPE'].id, 0, 0)
    #write_game_var(emu.memory, static_data.script_data.game_variables__by_name['PERFORMANCE_PROGRESS_LIST'].id, 7, 1)

    # Enable debug mode
    # SCENARIO_MAIN = 0x35 + SCENARIO_SELECT = 0x00 switch it
    # SCENARIO_SELECT = 0x35 also switch it.
    # + SCENARIO_MAIN[1] == 0x00
    #write_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_SELECT'].id, 0, 0x35)
    # label 42
    # -> label 37
    ###write_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN'].id, 0, 0x35)
    #write_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN'].id, 1, 0)

    # Test EVENT_DIVIDE
    # TODO: Bitflag reading/writing atm
    #XXXfor i in range(0, 8):
    #XXX    print(str(i) + " : " + str(read_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, i)[1]))
    #XXXwrite_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_SELECT'].id, 0, 0)
    #XXXwrite_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, 0, 1)
    #XXXwrite_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, 1, 1)
    #XXXwrite_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, 2, 1)
    #XXXwrite_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, 3, 1)
    #XXXwrite_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, 4, 1)
    #XXXwrite_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, 5, 1)
    #XXXwrite_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, 6, 1)
    #XXXwrite_game_var(emu.memory, static_data.script_data.game_variables__by_name['COMPULSORY_SAVE_POINT'].id, 0, 4)
    #XXXwrite_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, 7, 0)
    #XXXfor i in range(0, 8):
    #XXX    print(str(i) + " : " + str(read_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, i)[1]))
    #for i in range(0, 10):
    #    write_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN_BIT_FLAG'].id, i, 0)
    #write_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_SELECT'].id, 1, 0)
    #write_game_var(emu.memory, static_data.script_data.game_variables__by_name['SCENARIO_MAIN'].id, 0, 0x28)

    # END TESTING.

    var, value = read_game_var(emu.memory, var_id, read_offset)

    print(f"GET VAR VALUE: var:{var.name} + offset {read_offset}: {value}")


def hook__script_entry_point_determine(emu, address, size):
    #print(f"hook__script_entry_point_determine: {address}")
    pass


def hook_print_lr(emu, address, size):
    print(f"CALL {address}: LR 0x{emu.memory.register_arm9.lr:0x}")


def hook__get_script_id_name(emu: 'DeSmuME', address, size):
    id = emu.memory.register_arm9.r0
    print(f"GetScriptIDName({id}) -> {emu.memory.read_string(emu.memory.unsigned.read_long(table_script_files + (id * 12)))}")


static_data = Pmd2XmlReader.load_default()


# Below tests only works with EU PMD EoS:
start_of_arm_ov11_eu = 0x22DCB80
start_of_arm_ov11_us = 0x22DD8E0
start_of_arm_ov11 = start_of_arm_ov11_eu

# Fun_022DD164 [US] (Fun_22DDAA4 [EU])
start_of_loop_fn = start_of_arm_ov11 + 0xF24
assert static_data.binaries['overlay/overlay_0011.bin'].functions['FuncThatCallsCommandParsing'].begin_absolute == start_of_loop_fn
start_of_loop_fn_loop = start_of_loop_fn + 0x2C
start_of_switch_last_return_code = start_of_loop_fn + 0x34
start_of_call_to_opcode_parsing = start_of_loop_fn + 0x5C - 4

# For US: 0x200C240
debug_print_start = 0x0200c2c8
assert static_data.binaries['arm9.bin'].functions['DebugPrint'].begin_absolute == debug_print_start
# Another one! For US: 0x0200C30C
debug_print2_start = 0x0200c284
assert static_data.binaries['arm9.bin'].functions['DebugPrint2'].begin_absolute == debug_print2_start

# For US: start_of_arm_ov11_us + 0x40C4      [ + 0x3C40 after FN start]
point_to_print_print_debug = start_of_arm_ov11 + 0x5764
assert static_data.binaries['overlay/overlay_0011.bin'].functions['ScriptCommandParsing'].begin_absolute == point_to_print_print_debug - 0x3C40

# For US: start_of_arm_ov11_us + 0x1A4C      [ + 0x15C8 after FN start]
point_where_branch_debug_decides = start_of_arm_ov11 + 0x30EC
assert static_data.binaries['overlay/overlay_0011.bin'].functions['ScriptCommandParsing'].begin_absolute == point_where_branch_debug_decides - 0x15C8

# For US: start_of_arm_ov11_us + 0x4BAC
start_of_other_opcode_read_in_parsing = start_of_arm_ov11 + 0x624C

# GetScriptVariableInfoAndPtr
# For US: 0x0204B49C
start_of_get_script_variable_info_and_ptr = 0x204B7D4
"""
Call [EU] to GetScriptVariableInfoAndPtr
    109 0x204b844   | fn 0x0204b824  GetScriptVariableValue
    388 0x204b9d4   | fn 0x0204b9b0  GetScriptVariableValueWithOffset
     97 0x204bb7c   | fn 0x0204bb58  SaveScriptVariableValue
  12884 0x204bce8   | fn 0x0204bcc0  SaveScriptVariableValueWithOffset
      1 0x204c784   | fn 0x0204c768  (? Some init function?)
"""
# GetScriptVariableValue
# For US:
start_of_get_script_variable_value = 0x0204b824
# GetScriptVariableValue with offset?
# For US: TODO
start_of_get_script_variable_with_offset_value = 0x0204b9b0
# SaveScriptVariableValue
# For US: TODO
start_of_set_script_variable_value = 0x0204bb58
# SaveScriptVariableValue with offset?
# For US: TODO
start_of_set_script_variable_with_offset_value = 0x0204bcc0

# For US: 0x02064FFC
start_of_get_script_id_name = 0x02065378

# For US: 0x209D870
table_variable_info = 0x0209ddf4
# For US: 0x22AB0AC
table_variable_values = 0x022ab9ec
assert static_data.binaries['arm9.bin'].blocks['GameVarsValues'].begin_absolute == table_variable_values
# For US: 0x20A5490
table_script_files = 0x020a5be0

# For US: TODO
misc_game_data_pointer = 0x020aff70
assert static_data.binaries['arm9.bin'].pointers['GameStateValues'].begin_absolute == misc_game_data_pointer

# For US: TODO
language_info_data_pointer = 0x020b05a8
assert static_data.binaries['arm9.bin'].pointers['LanguageInfoData'].begin_absolute == language_info_data_pointer

# For US: TODO
game_mode_data_pointer = 0x020b088c
assert static_data.binaries['arm9.bin'].pointers['GameMode'].begin_absolute == game_mode_data_pointer

# For US: TODO
execute_special_episode_type__game_mode_1_pointer = 0x022abdec
assert static_data.binaries['arm9.bin'].pointers['DebugSpecialEpisodeType'].begin_absolute == execute_special_episode_type__game_mode_1_pointer

# For US: TODO
notify_note_flag_data_pointer = 0x020b0814
assert static_data.binaries['arm9.bin'].pointers['NotifyNote'].begin_absolute == notify_note_flag_data_pointer

# Points that call the Fun_022DD164 [US] (Fun_22DDAA4 [EU])
# [EU 0x22f8534] Possibly handling global script:
fun_loop_call_pnt1 = start_of_arm_ov11 + 0x1B9B4  # US: + TODO
# [EU 0x22fb890] Possibly handling actors:
fun_loop_call_pnt2 = start_of_arm_ov11 + 0x1ED10  # US: + TODO
# [EU 0x22fde4c] Possibly handling objects:
fun_loop_call_pnt3 = start_of_arm_ov11 + 0x212CC  # US: + TODO
# [EU 0x22ff208] Possibly handling performers:
fun_loop_call_pnt4 = start_of_arm_ov11 + 0x22688  # US: + TODO

# TODO: Find actor, object, performer etc. information and general acting / supervision data.


if __name__ == '__main__':
    emu = DeSmuME("../../../../desmume/desmume/src/frontend/interface/.libs/libdesmume.so")
    # emu = DeSmuME("Y:\\dev\\desmume\\desmume\\src\\frontend\\interface\\windows\\__bins\\DeSmuME Interface-VS2019-Debug.dll")

    emu.open("../../../skyworkcopy_edit.nds")
    #emu.savestate.load_file("/home/marco/.config/skytemple/debugger/skyworkcopy_edit.nds.save.3.ds")
    # emu.open("..\\skyworkcopy.nds")
    win = emu.create_sdl_window(use_opengl_if_possible=True)

    emu.volume_set(0)

    emu.memory.register_exec(start_of_call_to_opcode_parsing, partial(hook__primary_opcode_parsing, emu))
    #emu.memory.register_exec(start_of_switch_last_return_code, partial(hook__beginning_script_loop, emu))
    #emu.memory.register_exec(start_of_other_opcode_read_in_parsing, partial(hook__secondary_opcode_parsing, emu))
    #emu.memory.register_exec(debug_print_start, partial(hook__debug_print, 1, emu))
    #emu.memory.register_exec(debug_print2_start, partial(hook__debug_print, 0, emu))
    #emu.memory.register_exec(point_to_print_print_debug, partial(hook__debug_print_script_engine, emu))
    emu.memory.register_exec(point_where_branch_debug_decides, partial(hook__debug_enable_branch, emu))
    #emu.memory.register_exec(start_of_get_script_id_name, partial(hook__get_script_id_name, emu))

    #emu.memory.register_exec(start_of_get_script_variable_info_and_ptr, hook_print_lr)
    #emu.memory.register_exec(start_of_get_script_variable_value + 0x1C, partial(hook_get_script_variable_value, emu, False))
    #emu.memory.register_exec(start_of_get_script_variable_with_offset_value + 0x20, partial(hook_get_script_variable_value, emu, True))
    # TODO:
    #emu.memory.register_exec(start_of_get_script_variable_value + 0x1C, partial(hook_set_script_variable_value, False))
    #emu.memory.register_exec(start_of_get_script_variable_value + 0x1C, partial(hook_set_script_variable_value, True))

    #emu.memory.register_exec(fun_loop_call_pnt1, partial(hook__script_entry_point_determine, emu))
    #emu.memory.register_exec(fun_loop_call_pnt2, partial(hook__script_entry_point_determine, emu))
    #emu.memory.register_exec(fun_loop_call_pnt3, partial(hook__script_entry_point_determine, emu))
    #emu.memory.register_exec(fun_loop_call_pnt4, partial(hook__script_entry_point_determine, emu))

    while not win.has_quit():
        win.process_input()
        emu.cycle()
        win.draw()
