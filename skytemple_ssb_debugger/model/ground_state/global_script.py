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
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.model.address_container import AddressContainer
from skytemple_ssb_debugger.model.ground_state import AbstractEntityWithScriptStruct


class GlobalScript(AbstractEntityWithScriptStruct):
    def __init__(self, emu_thread: EmulatorThread, rom_data: Pmd2Data, pnt_to_block_start: int, unionall_load_addr: AddressContainer):
        super().__init__(emu_thread, pnt_to_block_start, rom_data, unionall_load_addr)

    @property
    def _script_struct_offset(self):
        return 0
