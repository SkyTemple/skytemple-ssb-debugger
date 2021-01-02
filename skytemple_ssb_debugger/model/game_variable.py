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
from typing import Tuple, Optional

from desmume.emulator import DeSmuME_Memory
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptGameVar, GameVariableType
from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct

START_OFFSET_LOCAL_VARIABLES = 108


def _get_value_pnt(static_data: Pmd2Data, srs: Optional[ScriptRuntimeStruct], var: Pmd2ScriptGameVar):
    if var.id >= 0x400:
        # LOCAL VARIABLE
        if not srs:
            raise ValueError("Local variable requested, but script runtime struct is not set.")
        return srs.pnt + START_OFFSET_LOCAL_VARIABLES + (var.memoffset * 8)
    else:
        # GLOBAL VARIABLE
        return static_data.binaries['arm9.bin'].blocks['GameVarsValues'].begin_absolute + var.memoffset


class GameVariable:
    @staticmethod
    def read(mem: DeSmuME_Memory, static_data: Pmd2Data,
             var_id: int, read_offset: int, srs: Optional[ScriptRuntimeStruct] = None) -> Tuple[Pmd2ScriptGameVar, int]:
        """
        Returns the info of the game variable passed in from the script info object and it's current value from memory.
        If the script runtime struct is not set, local variables can not be used!

        Partial reimplementation of
        GetScriptVariableValue, GetScriptVariableValueWithOffset and GetScriptVariableInfoAndPtr
        :return:
        """
        var: Pmd2ScriptGameVar = static_data.script_data.game_variables__by_id[var_id]
        value_pnt = _get_value_pnt(static_data, srs, var)
        value = 0
        if var.type == GameVariableType.BIT:
            # TODO: BRKEN!
            # Bit
            # if read_offset == 0:
            #    value_raw = mem.unsigned.read_byte(value_pnt)
            #    value = 0 if value_raw & ((1 << var.bitshift) & 0xFF) else 1
            # else:
            offs = var.bitshift + read_offset
            value_raw = mem.unsigned.read_byte(value_pnt + (offs >> 3))  # offset by higher 13 bits [removes the bit]
            val_offs = (1 << (offs & 7))  # offset by lower three bits
            value = 1 if value_raw & val_offs else 0
        elif var.type == GameVariableType.STRING:
            # uint8? Probably special purpose.
            value = mem.unsigned.read_byte(value_pnt + read_offset)
        elif var.type == GameVariableType.UINT8:
            # uint8
            value = mem.unsigned.read_byte(value_pnt + read_offset)
        elif var.type == GameVariableType.INT8:
            # int8
            value = mem.signed.read_byte(value_pnt + read_offset)
        elif var.type == GameVariableType.UINT16:
            # uint16
            value = mem.unsigned.read_short(value_pnt + (read_offset * 2))
        elif var.type == GameVariableType.INT16:
            # int16
            value = mem.signed.read_short(value_pnt + (read_offset * 2))
        elif var.type == GameVariableType.UINT32:
            # uint32
            value = mem.unsigned.read_long(value_pnt + (read_offset * 4))
        elif var.type == GameVariableType.INT32:
            # int32
            value = mem.signed.read_long(value_pnt + (read_offset * 4))
        elif var.type == GameVariableType.SPECIAL:
            # Special cases (offset is ignored for these)
            if var.id == 0x3A:  # FRIEND_SUM
                value = 1
            elif var.id == 0x3B:  # UNIT_SUM
                pass  # TODO - Possibly unusued but definitely relatively complicated, so not implemented for now.
            elif var.id == 0x3C:  # CARRY_GOLD
                misc_data_begin = mem.unsigned.read_long(static_data.binaries['arm9.bin'].pointers['GameStateValues'].begin_absolute)
                # Possibly who the money belongs to? Main team, Special episode team, etc.
                some_sort_of_offset = mem.unsigned.read_byte(
                    misc_data_begin + 0x388
                )
                address_carry_gold = misc_data_begin + (some_sort_of_offset * 4) + 0x1394
                value = mem.unsigned.read_long(address_carry_gold)
            elif var.id == 0x3D:  # BANK_GOLD
                misc_data_begin = mem.unsigned.read_long(static_data.binaries['arm9.bin'].pointers['GameStateValues'].begin_absolute)
                address_bank_gold = misc_data_begin + 0x13a0
                value = mem.unsigned.read_long(address_bank_gold)
            elif var.id == 0x47:  # LANGUAGE_TYPE
                value = mem.signed.read_byte(static_data.binaries['arm9.bin'].pointers['LanguageInfoData'].begin_absolute + 1)
            elif var.id == 0x48:  # GAME_MODE
                value = mem.unsigned.read_byte(static_data.binaries['arm9.bin'].pointers['GameMode'].begin_absolute)
            elif var.id == 0x49:  # EXECUTE_SPECIAL_EPISODE_TYPE
                game_mode = mem.unsigned.read_byte(static_data.binaries['arm9.bin'].pointers['GameMode'].begin_absolute)
                if game_mode == 1:
                    value = mem.unsigned.read_long(static_data.binaries['arm9.bin'].pointers['DebugSpecialEpisodeType'].begin_absolute)
                elif game_mode == 3:
                    value = GameVariable.read(mem, static_data, 0x4a, 0)
                else:
                    value = 0
            elif var.id == 0x70:  # NOTE_MODIFY_FLAG
                value = mem.unsigned.read_byte(static_data.binaries['arm9.bin'].pointers['NotifyNote'].begin_absolute)

        return var, value

    @staticmethod
    def write(mem: DeSmuME_Memory, static_data: Pmd2Data, var_id: int,
              read_offset: int, value: int, srs: Optional[ScriptRuntimeStruct] = None):
        """
        Saves a game variable.
        If the script runtime struct is not set, local variables can not be used!

        Partial reimplementation of
        SaveScriptVariableValue and SaveScriptVariableValueWithOffset
        """
        var: Pmd2ScriptGameVar = static_data.script_data.game_variables__by_id[var_id]
        value_pnt = _get_value_pnt(static_data, srs, var)

        # TODO: Enum?
        if var.type == GameVariableType.BIT:
            # TODO: BROKEN
            # Bit
            offs = var.bitshift + read_offset
            value_pnt = value_pnt + (offs >> 3)
            old_value = mem.unsigned.read_byte(value_pnt)  # offset by higher 13 bits [removes the bit]
            val_offs = 1 << (offs & 7)  # offset by lower three bits
            if value == 0:
                value = val_offs ^ (old_value | val_offs)
            else:
                value = old_value | val_offs
            mem.write_byte(value_pnt, value)
            """
            r4: value, r5: offset, r0: address
            0x0204bd24 f600d1e1       ldrsh r0, [r1, 6]          //R0 = ScriptGlobalInfoUnk2 | bitshift
            0x0204bd28 0110a0e3       mov r1, 1                  //R1 = 1
            0x0204bd2c 04209de5       ldr r2, [sp, 4]            //R2 = AddressScriptGlobalValue
            0x0204bd30 000085e0       add r0, r5, r0             //R0 = R5 + R0
            0x0204bd34 0008a0e1       lsl r0, r0, 0x10           //R0 = R0 << 0x10
            0x0204bd38 2038a0e1       lsr r3, r0, 0x10           //R3 = R0 >> 0x10
            0x0204bd3c 070003e2       and r0, r3, 7              //R0 = R3 & 0x07
            0x0204bd40 1100a0e1       lsl r0, r1, r0             //R0 = 1 << R0
            0x0204bd44 ff1000e2       and r1, r0, 0xff           //R1 = R0 & 0xFF
            0x0204bd48 a301d2e7       ldrb r0, [r2, r3, lsr 3]   //R0 = *[R2 + (R3 >> 3)]
            0x0204bd4c 000054e3       cmp r4, 0
            
            0x0204bd50 01008011       orrne r0, r0, r1
            0x0204bd54 a301c217       strbne r0, [r2, r3, lsr 3]
            
            0x0204bd58 01008001       orreq r0, r0, r1
            0x0204bd5c 00002100       eoreq r0, r1, r0
            0x0204bd60 a301c207       strbeq r0, [r2, r3, lsr 3]
            """
        elif var.type == GameVariableType.STRING:
            # uint8? Probably special purpose.
            mem.write_byte(value_pnt + read_offset, value)
        elif var.type == GameVariableType.UINT8:
            # uint8
            mem.write_byte(value_pnt + read_offset, value)
        elif var.type == GameVariableType.INT8:
            # int8
            mem.write_byte(value_pnt + read_offset, value)
        elif var.type == GameVariableType.UINT16:
            # uint16
            mem.write_short(value_pnt + (read_offset * 2), value)
        elif var.type == GameVariableType.INT16:
            # int16
            mem.write_short(value_pnt + (read_offset * 2), value)
        elif var.type == GameVariableType.UINT32:
            # uint32
            mem.write_long(value_pnt + (read_offset * 4), value)
        elif var.type == GameVariableType.INT32:
            # int32
            mem.write_long(value_pnt + (read_offset * 4), value)
        elif var.type == GameVariableType.SPECIAL:
            # Special cases (offset is ignored for these)
            # TODO: These are just reverses of the getters, I didn't really look at the ASM yet.
            if var.id == 0x3A:  # FRIEND_SUM
                pass  # TODO: Is this correct? the getter also doesn't really do anything.
            elif var.id == 0x3B:  # UNIT_SUM
                pass  # TODO: TBD
            elif var.id == 0x3C:  # CARRY_GOLD
                misc_data_begin = mem.unsigned.read_long(static_data.binaries['arm9.bin'].pointers['GameStateValues'].begin_absolute)
                # Possibly who the money belongs to? Main team, Special episode team, etc.
                some_sort_of_offset = mem.unsigned.read_byte(
                    misc_data_begin + 0x388
                )
                address_carry_gold = misc_data_begin + (some_sort_of_offset * 4) + 0x1394
                mem.write_long(address_carry_gold, value)
            elif var.id == 0x3D:  # BANK_GOLD
                misc_data_begin = mem.unsigned.read_long(static_data.binaries['arm9.bin'].pointers['GameStateValues'].begin_absolute)
                address_bank_gold = misc_data_begin + 0x13a0
                mem.write_long(address_bank_gold, value)
            elif var.id == 0x47:  # LANGUAGE_TYPE
                mem.write_byte(static_data.binaries['arm9.bin'].pointers['LanguageInfoData'].begin_absolute + 1, value)
            elif var.id == 0x48:  # GAME_MODE
                mem.write_byte(static_data.binaries['arm9.bin'].pointers['GameMode'].begin_absolute, value)
            elif var.id == 0x49:  # EXECUTE_SPECIAL_EPISODE_TYPE
                game_mode = mem.unsigned.read_byte(static_data.binaries['arm9.bin'].pointers['GameMode'].begin_absolute)
                if game_mode == 1:
                    mem.write_long(static_data.binaries['arm9.bin'].pointers['DebugSpecialEpisodeType'].begin_absolute, value)
            elif var.id == 0x70:  # NOTE_MODIFY_FLAG
                mem.write_byte(static_data.binaries['arm9.bin'].pointers['NotifyNote'].begin_absolute, value)
