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
from typing import Optional, Dict

import cairo
from gi.repository import Gdk

from skytemple_files.common.types.file_types import FileType
from skytemple_files.container.bin_pack.model import BinPack
from skytemple_files.data.md.model import Md, MdEntry
from skytemple_ssb_debugger.dungeon.model import pil_to_cairo_surface
from skytemple_ssb_debugger.dungeon.model.entity import DungeonEntity
from skytemple_ssb_debugger.dungeon.model.entity_ext.monster import EntityExtMonster
from skytemple_ssb_debugger.dungeon.pixbuf import PixbufProviderFloorType, PixbufProviderMonsterType
from skytemple_ssb_debugger.dungeon.pixbuf.small_map_icons import draw_circle, draw_rect_outline, draw_small_rect, \
    draw_cross, COLOR_ITEM, COLOR_STAIRS, COLOR_HIDDEN_STAIRS, COLOR_WONDER_TILE, COLOR_TRAP

DIM_CHUNK = 8 * 3


class FullMapPixbufProvider:
    def __init__(self, chunks: cairo.Surface, monster_bin: BinPack, monster_md: Md):
        self.chunks = chunks
        self.monster_bin = monster_bin
        self.monster_md = monster_md
        # Dict -> texture_index : Surface
        self.cache: Dict[int, cairo.Surface] = {}
        # Dict -> sprite id: Wan
        self.sprite_cache = {}

    def get(
            self,
            texture_index: int,
            floor_type: PixbufProviderFloorType,
            monster_type: PixbufProviderMonsterType,
            entity_on_floor: Optional[DungeonEntity],
            monster: Optional[DungeonEntity]
    ):
        # TODO: Fix caching
        if True or texture_index not in self.cache:
            self.cache[texture_index] = cairo.ImageSurface(cairo.FORMAT_RGB24, DIM_CHUNK, DIM_CHUNK)
            # Insert floor tile
            ctx = cairo.Context(self.cache[texture_index])
            ctx.set_source_surface(self.chunks, 0, -texture_index * DIM_CHUNK)
            ctx.paint()
        surface = self.cache[texture_index]
        ctx = cairo.Context(self.cache[texture_index])

        # Floor entity
        if floor_type == PixbufProviderFloorType.ITEM:
            draw_circle(ctx, COLOR_ITEM, DIM_CHUNK)
        elif floor_type == PixbufProviderFloorType.STAIRS:
            draw_rect_outline(ctx, COLOR_STAIRS, DIM_CHUNK)
        elif floor_type == PixbufProviderFloorType.HIDDEN_STAIRS:
            draw_rect_outline(ctx, COLOR_HIDDEN_STAIRS, DIM_CHUNK)
        elif floor_type == PixbufProviderFloorType.WONDER_TILE:
            draw_small_rect(ctx, COLOR_WONDER_TILE, DIM_CHUNK, 4)
        elif floor_type == PixbufProviderFloorType.OTHER_TRAP:
            draw_cross(ctx, COLOR_TRAP, DIM_CHUNK)

        # Monster
        if monster_type != PixbufProviderMonsterType.NONE:
            ext: EntityExtMonster = monster.load_extended_data()
            entity_id = ext.md_index
            direction = ext.direction_id
            md_entry: MdEntry = self.monster_md.get_by_index(entity_id)
            if md_entry.sprite_index not in self.sprite_cache:
                self.sprite_cache[md_entry.sprite_index] = FileType.WAN.deserialize(
                    FileType.PKDPX.deserialize(self.monster_bin[md_entry.sprite_index]).decompress()
                )
            sprite = self.sprite_cache[md_entry.sprite_index]
            ani_group = sprite.get_animations_for_group(sprite.anim_groups[0])
            mfg_id = ani_group[direction].frames[0].frame_id
            sprite_img, (cx, cy) = sprite.render_frame_group(sprite.frame_groups[mfg_id])
            # TODO: the exact height to draw at is probably based on the shadow size.
            ctx.set_source_surface(pil_to_cairo_surface(sprite_img), -cx + DIM_CHUNK / 2, -cy + DIM_CHUNK * 0.75)
            ctx.paint()

        return Gdk.pixbuf_get_from_surface(surface, 0, 0, DIM_CHUNK, DIM_CHUNK)
