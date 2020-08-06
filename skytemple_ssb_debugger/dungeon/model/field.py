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
from typing import Optional, Union

from skytemple_files.common.util import read_uintle
from skytemple_ssb_debugger.dungeon.model.entity import DungeonEntity
from skytemple_ssb_debugger.dungeon.model.entity_ext.monster import EntityExtMonster
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.threadsafe import wrap_threadsafe_emu, threadsafe_emu

FIELD_BYTELEN = 20


class DungeonFieldTerrainType(Enum):
    WALL = 0
    FLOOR = 1
    WATER_LAVA = 2
    VOID = 3


class DungeonFieldStairType(Enum):
    NONE = 0
    STAIRS = 2
    WARP_ZONE = 3


class DungeonFieldVisibility(Enum):
    NOT_VISITED = 0
    REVEALED = 1
    VISITED_UNREVEALED = 2
    VISITED = 3


class DungeonField:
    def __init__(self, emu_thread: EmulatorThread, begin_tiledata: int, cached_tiledata: Union[memoryview, bytes]):
        self.emu_thread = emu_thread
        self.begin = begin_tiledata
        if not cached_tiledata:
            cached_tiledata = memoryview(threadsafe_emu(
                emu_thread, lambda: emu_thread.emu.memory.unsigned[begin_tiledata:begin_tiledata + FIELD_BYTELEN]
            ))
        self.cached_tiledata = cached_tiledata

    @property
    def terrain_type(self) -> DungeonFieldTerrainType:
        val0 = read_uintle(self.cached_tiledata, 0)
        return DungeonFieldTerrainType(val0 & 0b011)
    
    @terrain_type.setter
    @wrap_threadsafe_emu()
    def terrain_type(self, value: DungeonFieldTerrainType):
        pass  # todo

    @property
    def is_natural_junction(self) -> bool:
        val0 = read_uintle(self.cached_tiledata, 0)
        return bool(val0 >> 3 & 1)
    
    @is_natural_junction.setter
    @wrap_threadsafe_emu()
    def is_natural_junction(self, value: bool):
        pass  # todo

    @property
    def is_impassable_wall(self) -> bool:
        val0 = read_uintle(self.cached_tiledata, 0)
        return bool(val0 >> 4 & 1)

    @is_impassable_wall.setter
    @wrap_threadsafe_emu()
    def is_impassable_wall(self, value: bool):
        pass  # todo

    @property
    def is_in_kecleon_shop(self) -> bool:
        val0 = read_uintle(self.cached_tiledata, 0)
        return bool(val0 >> 5 & 1)
    
    @is_in_kecleon_shop.setter
    @wrap_threadsafe_emu()
    def is_in_kecleon_shop(self, value: bool):
        pass  # todo

    @property
    def is_in_monster_house(self) -> bool:
        val0 = read_uintle(self.cached_tiledata, 0)
        return bool(val0 >> 6 & 1)
    
    @is_in_monster_house.setter
    @wrap_threadsafe_emu()
    def is_in_monster_house(self, value: bool):
        pass  # todo

    @property
    def stair_type(self) -> DungeonFieldStairType:
        return DungeonFieldStairType(read_uintle(self.cached_tiledata, 1))
    
    @stair_type.setter
    @wrap_threadsafe_emu()
    def stair_type(self, value: DungeonFieldStairType):
        pass  # todo

    @property
    def visibility(self) -> DungeonFieldVisibility:
        return DungeonFieldVisibility(read_uintle(self.cached_tiledata, 2))
    
    @visibility.setter
    @wrap_threadsafe_emu()
    def visibility(self, value: DungeonFieldVisibility):
        pass  # todo

    @property
    def texture_index(self) -> int:
        return read_uintle(self.cached_tiledata, 4, 2)
    
    @texture_index.setter
    @wrap_threadsafe_emu()
    def texture_index(self, value: int):
        pass  # todo

    @property
    def room_index(self) -> int:
        return read_uintle(self.cached_tiledata, 7)
    
    @room_index.setter
    @wrap_threadsafe_emu()
    def room_index(self, value: int):
        pass  # todo

    @property
    def monster_on_tile(self) -> Optional[DungeonEntity[EntityExtMonster]]:
        pnt = read_uintle(self.cached_tiledata, 0x0C, 4)
        if pnt < 1:
            return None
        return DungeonEntity(self.emu_thread, pnt)
    
    @monster_on_tile.setter
    @wrap_threadsafe_emu()
    def monster_on_tile(self, value: Optional[DungeonEntity[EntityExtMonster]]):
        pass  # todo

    @property
    def entity_on_floor(self) -> Optional[DungeonEntity]:
        pnt = read_uintle(self.cached_tiledata, 0x10, 4)
        if pnt < 1:
            return None
        return DungeonEntity(self.emu_thread, pnt)
    
    @entity_on_floor.setter
    @wrap_threadsafe_emu()
    def entity_on_floor(self, value: Optional[DungeonEntity]):
        pass  # todo
