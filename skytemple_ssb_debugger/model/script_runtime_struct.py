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

from desmume.emulator import DeSmuME
from explorerscript.ssb_converting.ssb_data_types import SsbRoutineType
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptOpCode


class ScriptRuntimeStruct:
    def __init__(self, emu: DeSmuME, rom_data: Pmd2Data, pnt: int):
        self.emu = emu
        self.rom_data = rom_data
        self.pnt = pnt

    @property
    def current_opcode(self) -> Pmd2ScriptOpCode:
        address_current_opcode = self.current_opcode_addr
        return self.rom_data.script_data.op_codes__by_id[self.emu.memory.unsigned.read_short(address_current_opcode)]

    @property
    def current_opcode_addr(self) -> int:
        return self.emu.memory.unsigned.read_long(self.pnt + 0x1c)

    @property
    def target_type(self) -> SsbRoutineType:
        return SsbRoutineType(self.emu.memory.unsigned.read_short(self.pnt + 8))

    @property
    def hanger_ssb(self):
        # The number of the SSB script this operation is in!
        return self.emu.memory.unsigned.read_short(self.pnt + 0x10)

    @property
    def target_id(self) -> int:
        script_target_id = script_target_address = self.emu.memory.unsigned.read_long(self.pnt + 4)
        if script_target_address != 0:
            script_target_id = self.emu.memory.unsigned.read_short(script_target_address)
        return script_target_id
