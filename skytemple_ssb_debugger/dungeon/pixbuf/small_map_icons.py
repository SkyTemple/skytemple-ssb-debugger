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
import math
from typing import Dict

import cairo
from gi.repository import Gdk
from gi.repository.GdkPixbuf import Pixbuf

from skytemple_ssb_debugger.dungeon.model.field import DungeonFieldTerrainType
from skytemple_ssb_debugger.dungeon.pixbuf import PixbufProviderTerrainType, PixbufProviderFloorType, \
    PixbufProviderMonsterType

DIM_SMALL_TILE = 8

COLOR_SOLID_CYAN = (0, 1, 1)
COLOR_SOLID_RED = (1, 0, 0)
COLOR_SOLID_ORANGE = (0.75, 0.5, 0)

COLOR_FLOOR = (1, 1, 1)
COLOR_IMPASSABLE_WALL = (0, 0, 0)
COLOR_WALL = (0.2, 0.2, 0.2)
COLOR_WATER = (0, 0, 1)
COLOR_JUNCTION = (0.8, 0.8, 0.8)
COLOR_KECLEON_SHOP = (0.8, 1, 1)
COLOR_MONSTER_HOUSE = (1, 0.8, 0.8)
COLOR_ITEM = COLOR_SOLID_CYAN
COLOR_STAIRS = COLOR_SOLID_CYAN
COLOR_HIDDEN_STAIRS = COLOR_SOLID_ORANGE
COLOR_WONDER_TILE = COLOR_SOLID_CYAN
COLOR_TRAP = COLOR_SOLID_RED
COLOR_ENEMY = COLOR_SOLID_RED
COLOR_ALLY = (1, 1, 0)
COLOR_ALLY_ENEMY = COLOR_SOLID_ORANGE
COLOR_TERAM_LEADER = COLOR_ALLY


class SmallMapPixbufProvider:
    """
    Caches pixbufs for the small map.
    The cache object has the following structure: {
        PixbufProviderTerrainType: {
            PixbufProviderFloorType: {
                PixbufProviderMonsterType: Pixbuf
            }
        }
    }
    """
    cache: Dict[DungeonFieldTerrainType, Dict[PixbufProviderFloorType, Dict[PixbufProviderMonsterType, Pixbuf]]] = {}

    @classmethod
    def get(
            cls, terrain: PixbufProviderTerrainType, floor: PixbufProviderFloorType, monster: PixbufProviderMonsterType
    ):
        if terrain not in cls.cache:
            cls.cache[terrain] = {}
        if floor not in cls.cache[terrain]:
            cls.cache[terrain][floor] = {}
        if monster not in cls.cache[terrain][floor]:
            cls.cache[terrain][floor][monster] = cls._generate(terrain, floor, monster)
        return cls.cache[terrain][floor][monster]

    @classmethod
    def _generate(
            cls, terrain: PixbufProviderTerrainType, floor: PixbufProviderFloorType, monster: PixbufProviderMonsterType
    ):
        if terrain == PixbufProviderTerrainType.FLOOR:
            surface, ctx = create_colored_tile(COLOR_FLOOR)
        elif terrain == PixbufProviderTerrainType.WATER_LAVA:
            surface, ctx = create_colored_tile(COLOR_WATER)
        elif terrain == PixbufProviderTerrainType.JUNCTION:
            surface, ctx = create_colored_tile(COLOR_JUNCTION)
        elif terrain == PixbufProviderTerrainType.KECLEON_SHOP:
            surface, ctx = create_colored_tile(COLOR_KECLEON_SHOP)
        elif terrain == PixbufProviderTerrainType.MONSTER_HOUSE:
            surface, ctx = create_colored_tile(COLOR_MONSTER_HOUSE)
        elif terrain == PixbufProviderTerrainType.WALL:
            surface, ctx = create_colored_tile(COLOR_WALL)
        else:  # terrain == PixbufProviderTerrainType.IMPASSABLE_WALL:
            surface, ctx = create_colored_tile(COLOR_IMPASSABLE_WALL)

        # Floor entity
        if floor == PixbufProviderFloorType.ITEM:
            draw_circle(ctx, COLOR_ITEM)
        elif floor == PixbufProviderFloorType.STAIRS:
            draw_rect_outline(ctx, COLOR_STAIRS)
        elif floor == PixbufProviderFloorType.HIDDEN_STAIRS:
            draw_rect_outline(ctx, COLOR_HIDDEN_STAIRS)
        elif floor == PixbufProviderFloorType.WONDER_TILE:
            draw_small_rect(ctx, COLOR_WONDER_TILE)
        elif floor == PixbufProviderFloorType.OTHER_TRAP:
            draw_cross(ctx, COLOR_TRAP)

        # Monster
        if monster == PixbufProviderMonsterType.ENEMY:
            draw_circle(ctx, COLOR_ENEMY)
        elif monster == PixbufProviderMonsterType.ALLY:
            draw_circle(ctx, COLOR_ALLY)
        elif monster == PixbufProviderMonsterType.ALLY_ENEMY:
            draw_circle(ctx, COLOR_ALLY_ENEMY)
        elif monster == PixbufProviderMonsterType.TEAM_LEADER:
            draw_circle(ctx, COLOR_TERAM_LEADER)

        return Gdk.pixbuf_get_from_surface(surface, 0, 0, DIM_SMALL_TILE, DIM_SMALL_TILE)


def create_colored_tile(color):
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, DIM_SMALL_TILE, DIM_SMALL_TILE)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*color)
    ctx.rectangle(0, 0, DIM_SMALL_TILE, DIM_SMALL_TILE)
    ctx.fill()
    ctx.set_line_width(1)
    return surface, ctx


def draw_circle(ctx: cairo.Context, color, dim=DIM_SMALL_TILE):
    ctx.set_source_rgb(*color)
    ctx.arc(dim / 2, dim / 2, dim / 2, 0, 2 * math.pi)
    ctx.fill()


def draw_rect_outline(ctx: cairo.Context, color, dim=DIM_SMALL_TILE):
    ctx.set_source_rgb(*color)
    ctx.rectangle(1, 1, dim - 2, dim - 2)
    ctx.stroke()


def draw_small_rect(ctx: cairo.Context, color, dim=DIM_SMALL_TILE, padding=2):
    ctx.set_source_rgb(*color)
    ctx.rectangle(padding, padding, dim - padding*2, dim - padding*2)
    ctx.fill()


def draw_cross(ctx: cairo.Context, color, dim=DIM_SMALL_TILE):
    ctx.set_source_rgb(*color)
    ctx.move_to(0, 0)
    ctx.line_to(dim, dim)
    ctx.stroke()
    ctx.move_to(dim, 0)
    ctx.line_to(0, dim)
    ctx.stroke()
