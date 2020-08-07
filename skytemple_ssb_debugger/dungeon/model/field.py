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

from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptDirection
from skytemple_files.common.util import read_uintle, read_sintle
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


class DungeonFieldVisibility(Enum):
    NOT_VISITED = 0
    REVEALED = 1
    VISITED_UNREVEALED = 2
    VISITED = 3


class DungeonFieldMovement(Enum):
    def __init__(self, allowed: int):
        self.allowed = allowed

    def is_allowed(self, dir: Pmd2ScriptDirection) -> bool:
        return bool(self.allowed >> dir.id & 1)

    def set_allowed(self, dir: Pmd2ScriptDirection, val: bool):
        raise NotImplementedError()  # todo


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
        raise NotImplementedError()  # todo

    @property
    def is_natural_junction(self) -> bool:
        val0 = read_uintle(self.cached_tiledata, 0)
        return bool(val0 >> 3 & 1)
    
    @is_natural_junction.setter
    @wrap_threadsafe_emu()
    def is_natural_junction(self, value: bool):
        raise NotImplementedError()  # todo

    @property
    def is_impassable_wall(self) -> bool:
        val0 = read_uintle(self.cached_tiledata, 0)
        return bool(val0 >> 4 & 1)

    @is_impassable_wall.setter
    @wrap_threadsafe_emu()
    def is_impassable_wall(self, value: bool):
        raise NotImplementedError()  # todo

    @property
    def is_in_kecleon_shop(self) -> bool:
        val0 = read_uintle(self.cached_tiledata, 0)
        return bool(val0 >> 5 & 1)
    
    @is_in_kecleon_shop.setter
    @wrap_threadsafe_emu()
    def is_in_kecleon_shop(self, value: bool):
        raise NotImplementedError()  # todo

    @property
    def is_in_monster_house(self) -> bool:
        val0 = read_uintle(self.cached_tiledata, 0)
        return bool(val0 >> 6 & 1)
    
    @is_in_monster_house.setter
    @wrap_threadsafe_emu()
    def is_in_monster_house(self, value: bool):
        raise NotImplementedError()  # todo

    @property
    def cannot_be_broken_by_absolute_mover(self) -> bool:
        val1 = read_uintle(self.cached_tiledata, 1)
        return bool(val1 & 1)

    @cannot_be_broken_by_absolute_mover.setter
    @wrap_threadsafe_emu()
    def cannot_be_broken_by_absolute_mover(self, value: bool):
        raise NotImplementedError()  # todo

    @property
    def is_stairs(self) -> bool:
        val1 = read_uintle(self.cached_tiledata, 1)
        return bool(val1 >> 1 & 1)
    
    @is_stairs.setter
    @wrap_threadsafe_emu()
    def is_stairs(self, value: bool):
        raise NotImplementedError()  # todo

    @property
    def is_key_door(self) -> bool:
        val1 = read_uintle(self.cached_tiledata, 1)
        return bool(val1 >> 3 & 1)

    @is_key_door.setter
    @wrap_threadsafe_emu()
    def is_key_door(self, value: bool):
        raise NotImplementedError()  # todo

    @property
    def is_key_door_open(self) -> bool:
        val1 = read_uintle(self.cached_tiledata, 1)
        return bool(val1 >> 4 & 1)

    @is_key_door_open.setter
    @wrap_threadsafe_emu()
    def is_key_door_open(self, value: bool):
        raise NotImplementedError()  # todo

    @property
    def visibility(self) -> DungeonFieldVisibility:
        return DungeonFieldVisibility(read_uintle(self.cached_tiledata, 2))
    
    @visibility.setter
    @wrap_threadsafe_emu()
    def visibility(self, value: DungeonFieldVisibility):
        raise NotImplementedError()  # todo

    @property
    def texture_index(self) -> int:
        return read_uintle(self.cached_tiledata, 4, 2)
    
    @texture_index.setter
    @wrap_threadsafe_emu()
    def texture_index(self, value: int):
        raise NotImplementedError()  # todo

    @property
    def room_index(self) -> int:
        # Hallways have -1, Crossroads -2
        return read_sintle(self.cached_tiledata, 7)
    
    @room_index.setter
    @wrap_threadsafe_emu()
    def room_index(self, value: int):
        raise NotImplementedError()  # todo

    @property
    def movement_normal(self) -> DungeonFieldMovement:
        return DungeonFieldMovement(read_uintle(self.cached_tiledata, 0x8))
    
    @movement_normal.setter
    @wrap_threadsafe_emu()
    def movement_normal(self, value: DungeonFieldMovement):
        raise NotImplementedError()  # todo

    @property
    def movement_water_lava(self) -> DungeonFieldMovement:
        return DungeonFieldMovement(read_uintle(self.cached_tiledata, 0x9))
    
    @movement_water_lava.setter
    @wrap_threadsafe_emu()
    def movement_water_lava(self, value: DungeonFieldMovement):
        raise NotImplementedError()  # todo

    @property
    def movement_void(self) -> DungeonFieldMovement:
        return DungeonFieldMovement(read_uintle(self.cached_tiledata, 0xA))

    @movement_void.setter
    @wrap_threadsafe_emu()
    def movement_void(self, value: DungeonFieldMovement):
        raise NotImplementedError()  # todo

    @property
    def movement_wall(self) -> DungeonFieldMovement:
        return DungeonFieldMovement(read_uintle(self.cached_tiledata, 0xB))

    @movement_wall.setter
    @wrap_threadsafe_emu()
    def movement_wall(self, value: DungeonFieldMovement):
        raise NotImplementedError()  # todo

    @property
    def monster_on_tile(self) -> Optional[DungeonEntity[EntityExtMonster]]:
        pnt = read_uintle(self.cached_tiledata, 0x0C, 4)
        if pnt < 1:
            return None
        return DungeonEntity(self.emu_thread, pnt)
    
    @monster_on_tile.setter
    @wrap_threadsafe_emu()
    def monster_on_tile(self, value: Optional[DungeonEntity[EntityExtMonster]]):
        raise NotImplementedError()  # todo

    @property
    def entity_on_floor(self) -> Optional[DungeonEntity]:
        pnt = read_uintle(self.cached_tiledata, 0x10, 4)
        if pnt < 1:
            return None
        return DungeonEntity(self.emu_thread, pnt)
    
    @entity_on_floor.setter
    @wrap_threadsafe_emu()
    def entity_on_floor(self, value: Optional[DungeonEntity]):
        raise NotImplementedError()  # todo
