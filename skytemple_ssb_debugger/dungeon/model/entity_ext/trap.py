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
from typing import Union

from skytemple_files.common.util import read_uintle
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.threadsafe import threadsafe_emu, wrap_threadsafe_emu

EXTRA_TRAPS_BYTELEN = 4


class EntityExtTrap:
    def __init__(self, emu_thread: EmulatorThread, begin: int, cached: Union[memoryview, bytes]=None):
        self.emu_thread = emu_thread
        self.begin = begin
        if not cached:
            cached = memoryview(threadsafe_emu(
                emu_thread, lambda: emu_thread.emu.memory.unsigned[begin:begin + EXTRA_TRAPS_BYTELEN]
            ))
        self.cached = cached

    @property
    def trap_id(self) -> int:
        return read_uintle(self.cached, 0x00, 1)

    @trap_id.setter
    @wrap_threadsafe_emu()
    def trap_id(self, value: int):
        pass  # todo

    @property
    def active(self) -> bool:
        return bool(read_uintle(self.cached, 0x01, 1))

    @active.setter
    @wrap_threadsafe_emu()
    def active(self, value: bool):
        pass  # todo
