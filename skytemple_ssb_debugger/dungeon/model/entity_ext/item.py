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

EXTRA_ITEMS_BYTELEN = 6


class EntityExtItem:
    def __init__(self, emu_thread: EmulatorThread, begin: int, cached: Union[memoryview, bytes]=None):
        self.emu_thread = emu_thread
        self.begin = begin
        if not cached:
            cached = memoryview(threadsafe_emu(
                emu_thread, lambda: emu_thread.emu.memory.unsigned[begin:begin + EXTRA_ITEMS_BYTELEN]
            ))
        self.cached = cached

    @property
    def exists(self) -> bool:
        bitfield = read_uintle(self.cached, 0)
        return bool(bitfield & 1)

    @exists.setter
    @wrap_threadsafe_emu()
    def exists(self, value: bool):
        pass  # todo

    @property
    def in_a_shop(self) -> bool:
        bitfield = read_uintle(self.cached, 0)
        return bool(bitfield >> 1 & 1)

    @in_a_shop.setter
    @wrap_threadsafe_emu()
    def in_a_shop(self, value: bool):
        pass  # todo

    @property
    def sticky(self) -> bool:
        bitfield = read_uintle(self.cached, 0)
        return bool(bitfield >> 2 & 1)

    @sticky.setter
    @wrap_threadsafe_emu()
    def sticky(self, value: bool):
        pass  # todo

    @property
    def is_set(self) -> bool:
        bitfield = read_uintle(self.cached, 0)
        return bool(bitfield >> 3 & 1)

    @is_set.setter
    @wrap_threadsafe_emu()
    def is_set(self, value: bool):
        pass  # todo

    @property
    def held_by_idx(self) -> int:
        return read_uintle(self.cached, 0x01, 1)

    @held_by_idx.setter
    @wrap_threadsafe_emu()
    def held_by_idx(self, value: int):
        pass  # todo

    @property
    def amount(self) -> int:
        return read_uintle(self.cached, 0x02, 2)

    @amount.setter
    @wrap_threadsafe_emu()
    def amount(self, value: int):
        pass  # todo

    @property
    def item_id(self) -> int:
        return read_uintle(self.cached, 0x04, 2)

    @item_id.setter
    @wrap_threadsafe_emu()
    def item_id(self, value: int):
        pass  # todo
