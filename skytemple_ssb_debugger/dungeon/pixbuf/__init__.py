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


class PixbufProviderTerrainType(Enum):
    IMPASSABLE_WALL = -1
    WALL = 0
    FLOOR = 1
    WATER_LAVA = 2
    VOID = 3
    JUNCTION = 4
    KECLEON_SHOP = 5
    MONSTER_HOUSE = 6


class PixbufProviderFloorType(Enum):
    NONE = -1
    WONDER_TILE = 0
    OTHER_TRAP = 1
    ITEM = 2
    STAIRS = 3
    HIDDEN_STAIRS = 4


class PixbufProviderMonsterType(Enum):
    NONE = -1
    ENEMY = 0
    ALLY = 1
    ALLY_ENEMY = 2
    TEAM_LEADER = 3