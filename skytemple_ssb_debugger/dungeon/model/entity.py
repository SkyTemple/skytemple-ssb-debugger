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
from enum import Enum
from typing import Generic, TypeVar, Union, Optional

from skytemple_files.common.util import read_uintle
from skytemple_ssb_debugger.dungeon.model.entity_ext.item import EntityExtItem
from skytemple_ssb_debugger.dungeon.model.entity_ext.monster import EntityExtMonster
from skytemple_ssb_debugger.dungeon.model.entity_ext.trap import EntityExtTrap
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.threadsafe import threadsafe_emu, wrap_threadsafe_emu

T = TypeVar('T')
ENTITY_BYTELEN = 184


class DungeonEntityType(Enum):
    NOTHING = 0
    MONSTER = 1
    TRAP = 2
    ITEM = 3
    UNK4 = 4
    HIDDEN_STAIRS = 5


class DungeonEntity(Generic[T]):
    def __init__(self, emu_thread: EmulatorThread, begin: int, cached_entitydata: Union[memoryview, bytes]=None):
        self.emu_thread = emu_thread
        self.begin = begin
        if not cached_entitydata:
            cached_entitydata = memoryview(threadsafe_emu(
                emu_thread, lambda: emu_thread.emu.memory.unsigned[begin:begin + ENTITY_BYTELEN]
            ))
        self.cached_entitydata = cached_entitydata

    @property
    def entity_type(self) -> DungeonEntityType:
        return DungeonEntityType(read_uintle(self.cached_entitydata, 0, 4))

    @entity_type.setter
    @wrap_threadsafe_emu()
    def entity_type(self, value: DungeonEntityType):
        raise NotImplementedError()  # todo

    @property
    def x_pos(self) -> int:
        return read_uintle(self.cached_entitydata, 4, 2)

    @x_pos.setter
    @wrap_threadsafe_emu()
    def x_pos(self, value: int):
        raise NotImplementedError()  # todo

    @property
    def y_pos(self) -> int:
        return read_uintle(self.cached_entitydata, 6, 2)

    @y_pos.setter
    @wrap_threadsafe_emu()
    def y_pos(self, value: int):
        raise NotImplementedError()  # todo

    @property
    def visible(self) -> bool:
        return bool(read_uintle(self.cached_entitydata, 0x20))

    @visible.setter
    @wrap_threadsafe_emu()
    def visible(self, value: bool):
        raise NotImplementedError()  # todo

    def load_extended_data(self) -> Optional[T]:
        # TODO: Caching?
        start_pnt = read_uintle(self.cached_entitydata, 0xB4, 4)
        if self.entity_type == DungeonEntityType.MONSTER:
            return EntityExtMonster(self.emu_thread, start_pnt)
        if self.entity_type == DungeonEntityType.ITEM:
            return EntityExtItem(self.emu_thread, start_pnt)
        if self.entity_type == DungeonEntityType.TRAP:
            return EntityExtTrap(self.emu_thread, start_pnt)
        return None

    def __eq__(self, other):
        if not isinstance(other, DungeonEntity):
            return False
        return self.begin == other.begin
