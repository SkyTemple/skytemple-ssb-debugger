"""Script to play around with the dungeon data in RAM."""
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
import os
import time
from collections import Iterable
from enum import Enum
from functools import partial
from typing import Union

from PIL import Image, ImageDraw
from ndspy.rom import NintendoDSRom

from desmume.emulator import DeSmuME
from skytemple_files.common.types.file_types import FileType
from skytemple_files.common.util import get_ppmdu_config_for_rom
from skytemple_files.data.md.model import MdEntry
from skytemple_files.dungeon_data.mappa_bin.floor import MappaFloor
from skytemple_files.graphics.dpc.model import Dpc
from skytemple_files.graphics.dpci.model import Dpci
from skytemple_files.graphics.dpl.model import Dpl
from skytemple_files.graphics.dpla.model import Dpla
from skytemple_files.graphics.wan_wat.model import Wan

MAP_OUT_DIR = '/tmp/maps'
DUNGEON_TILEDATA__ENTRYLEN = 20
DUNGEON_TILEDATA__WIDTH = 56
DUNGEON_TILEDATA__HEIGHT = 32
DUNGEON_ENTITIES__ENTRYLEN = 184
DUNGEON_ENTITIES__LEN_MONSTER = 40
DUNGEON_ENTITIES__LEN_ITEMS = 64
DUNGEON_ENTITIES__LEN_TRAPS = 64
DUNGEON_ENTITIES__LEN_HIDDEN_STAIRS = 1
DUNGEON_ENTITIES__EXTRA_MONSTERS_ENTRYLEN = 576
DUNGEON_ENTITIES__EXTRA_ITEMS_ENTRYLEN = 6
DUNGEON_ENTITIES__EXTRA_TRAPS_ENTRYLEN = 4
CHUNK_DIM = 8 * 3


rom = NintendoDSRom.fromFile("../../../skyworkcopy_us.nds")
pmd2data = get_ppmdu_config_for_rom(rom)
blk_dungeon_current_id = pmd2data.binaries['arm9.bin'].blocks["DungeonCurrentId"]
pnt_dungeon_data = pmd2data.binaries['arm9.bin'].pointers["DungeonData"]
addr_current_id = blk_dungeon_current_id.begin_absolute                   # uin16

dungeon_bin = FileType.DUNGEON_BIN.deserialize(rom.getFileByName('DUNGEON/dungeon.bin'), pmd2data)
mappa_s = FileType.MAPPA_BIN.deserialize(rom.getFileByName('BALANCE/mappa_s.bin'))
monster_md = FileType.MD.deserialize(rom.getFileByName('BALANCE/monster.md'))
monster_bin = FileType.BIN_PACK.deserialize(rom.getFileByName('MONSTER/monster.bin'))


class DungeonRamEntityType(Enum):
    NOTHING = 0
    MONSTER = 1
    TRAP = 2
    ITEM = 3


class DungeonRamTileType(Enum):
    WALL = 0
    FLOOR = 1
    WATER_LAVA = 2
    VOID = 3


class DungeonRamStairType(Enum):
    NONE = 0
    STAIRS = 2
    WARP_ZONE = 3


class DungeonRamMapVisibilityType(Enum):
    NOT_VISITED = 0
    REVEALED = 1
    VISITED_UNREVEALED = 2
    VISITED = 3


def print_generic_entity_data(addr_entities, index):
    pnt = index * 4 + addr_entities
    addr = emu.memory.unsigned.read_long(pnt)
    try:
        enttype = DungeonRamEntityType(emu.memory.unsigned.read_long(addr + 0x00))
        if enttype == DungeonRamEntityType.NOTHING:
            return None
        print("  <Entity>")
        print("    Type:", enttype.name)
        print("    X:", emu.memory.unsigned.read_short(addr + 0x04))
        print("    Y:", emu.memory.unsigned.read_short(addr + 0x06))
        print("    Visibility:", emu.memory.unsigned.read_byte(addr + 0x20))
        return emu.memory.unsigned.read_long(addr + 0xB4)
    except ValueError:
        print("  <Entity>")
        print("    -ERROR-")
    return None


def print_monster_data(epnt):
    print("    Species:", emu.memory.unsigned.read_short(epnt + 0x02))
    print("    Species2:", emu.memory.unsigned.read_short(epnt + 0x04))
    print("    Enemy Flag:", emu.memory.signed.read_byte(epnt + 0x06))
    print("    Team Leader Flag:", emu.memory.signed.read_byte(epnt + 0x07))
    print("    Ally Flag:", emu.memory.signed.read_byte(epnt + 0x08))
    print("    Kecleon Flag:", emu.memory.signed.read_byte(epnt + 0x09))
    print("    Level:", emu.memory.unsigned.read_byte(epnt + 0x0A))
    print("    Name Type:", emu.memory.unsigned.read_short(epnt + 0x0C))
    print("    IQ:", emu.memory.signed.read_short(epnt + 0x0E))
    print("    HP:", emu.memory.signed.read_short(epnt + 0x10))
    print("    Max HP:", emu.memory.signed.read_short(epnt + 0x12))
    print("    Max HP boost:", emu.memory.signed.read_short(epnt + 0x16))
    print("    Atk.:", emu.memory.unsigned.read_byte(epnt + 0x1A))
    print("    Sp.Atk.:", emu.memory.unsigned.read_byte(epnt + 0x1B))
    print("    Def.:", emu.memory.unsigned.read_byte(epnt + 0x1C))
    print("    Sp.Def.:", emu.memory.unsigned.read_byte(epnt + 0x1D))
    print("    Exp.Points:", emu.memory.unsigned.read_long(epnt + 0x20))
    # 0x24 - 0x43: Stat boosts
    dir_id = emu.memory.unsigned.read_byte(epnt + 0x4C)
    if dir_id > 1:
        print("    Direction:", pmd2data.script_data.directions__by_id[dir_id - 1])
    print("    Type 1:", emu.memory.signed.read_byte(epnt + 0x5E))
    print("    Type 2:", emu.memory.signed.read_byte(epnt + 0x5F))
    print("    Ability 1:", emu.memory.signed.read_byte(epnt + 0x60))
    print("    Ability 2:", emu.memory.signed.read_byte(epnt + 0x61))
    print("    Holding item?:", emu.memory.signed.read_byte(epnt + 0x62))
    print("    Holding item2?:", emu.memory.signed.read_byte(epnt + 0x63))
    print("    Held item qty:", emu.memory.signed.read_short(epnt + 0x64))
    print("    Held item ID:", emu.memory.signed.read_short(epnt + 0x66))
    print("    Held item ID2:", emu.memory.signed.read_short(epnt + 0x68))
    # 0x0A9 - 0x11E: Statuses
    # 0x124... move infos, belly, etc.


def print_item_data(epnt):
    bitfield = emu.memory.unsigned.read_byte(epnt + 0x00)
    bitflags = [bool(bitfield >> i & 1) for i in range(4)]
    print("    Exists:", bitflags[0])
    print("    In a shop:", bitflags[1])
    print("    Sticky:", bitflags[2])
    print("    Is set:", bitflags[3])
    print("    Held by:", emu.memory.signed.read_byte(epnt + 0x01))
    print("    Amount:", emu.memory.signed.read_short(epnt + 0x02))
    print("    Item ID:", emu.memory.signed.read_short(epnt + 0x04))


def print_trap_data(epnt):
    print("    Trap ID:", emu.memory.signed.read_byte(epnt + 0x00))
    print("    Active:", emu.memory.signed.read_byte(epnt + 0x01))


class DungeonRamTile:
    def __init__(self, start: int):
        val0 = emu.memory.unsigned.read_byte(start + 0x00)
        self.terrain_type = DungeonRamTileType(val0 & 0b011)
        bitflags = [bool(val0 >> i & 1) for i in range(3, 8)]
        self.natural_junction = bitflags[0]
        self.impassable_wall = bitflags[1]
        self.kecleon_shop = bitflags[2]
        self.monster_house = bitflags[3]
        self.stairs = DungeonRamStairType(emu.memory.unsigned.read_byte(start + 0x01))
        self.visibility = DungeonRamMapVisibilityType(emu.memory.unsigned.read_byte(start + 0x02))
        self.dpc_index = emu.memory.unsigned.read_short(start + 0x04)
        self.room_index = emu.memory.unsigned.read_byte(start + 0x07)
        self.pnt_monster = emu.memory.unsigned.read_long(start + 0x0C)
        self.pnt_floor_entity = emu.memory.unsigned.read_long(start + 0x10)


def draw_small_map(addr_entities, img, x, y, tile):
    if tile.terrain_type == DungeonRamTileType.FLOOR:
        # Floor
        color = (255, 255, 255)
        if tile.natural_junction:
            color = (112, 112, 112)
        if tile.kecleon_shop:
            color = (0, 139, 12)
        if tile.monster_house:
            color = (180, 94, 0)
        if tile.stairs == DungeonRamStairType.STAIRS:
            color = (163, 170, 0)
        if tile.stairs == DungeonRamStairType.WARP_ZONE:
            color = (90, 94, 0)
    elif tile.terrain_type == DungeonRamTileType.WATER_LAVA:
        # Water / Lava
        color = (23, 143, 239)
    elif tile.terrain_type == DungeonRamTileType.VOID:
        # Water / Lava
        color = (57, 36, 36)
    else:
        # Wall
        color = (30, 30, 30)
        if tile.impassable_wall:
            color = (0, 0, 0)
    if tile.pnt_monster != 0:
        color = (255, 0, 0)
    if tile.pnt_floor_entity:
        pnt = tile.pnt_floor_entity
        enttype = DungeonRamEntityType(emu.memory.unsigned.read_long(pnt))
        if enttype == DungeonRamEntityType.ITEM:
            color = (0, 241, 255)
        elif enttype == DungeonRamEntityType.TRAP:
            color = (0, 255, 22)
    img.putpixel((x, y), color)


def draw_full_map(addr_entities, img, x, y, tile, chunks: Image.Image):
    chunk_index = tile.dpc_index
    img.paste(
        chunks.crop((0, chunk_index * CHUNK_DIM, CHUNK_DIM, chunk_index * CHUNK_DIM + CHUNK_DIM)),
        (x * CHUNK_DIM, y * CHUNK_DIM)
    )
    if tile.pnt_monster > 0:
        pnt = tile.pnt_monster
        epnt = emu.memory.unsigned.read_long(pnt + 0xB4)
        entity_id = emu.memory.unsigned.read_short(epnt + 0x02)
        direction = emu.memory.unsigned.read_byte(epnt + 0x4C)
        md_entry: MdEntry = monster_md.get_by_index(entity_id)
        sprite = FileType.WAN.deserialize(
            FileType.PKDPX.deserialize(monster_bin[md_entry.sprite_index]).decompress()
        )
        ani_group = sprite.get_animations_for_group(sprite.anim_groups[0])
        mfg_id = ani_group[direction].frames[0].frame_id
        sprite_img, (cx, cy) = sprite.render_frame_group(sprite.frame_groups[mfg_id])
        render_x = x * CHUNK_DIM
        render_y = y * CHUNK_DIM
        img.paste(sprite_img, (render_x, render_y), sprite_img)
    if tile.pnt_floor_entity > 0:
        pnt = tile.pnt_floor_entity
        enttype = DungeonRamEntityType(emu.memory.unsigned.read_long(pnt))
        if enttype == DungeonRamEntityType.ITEM:
            color = (0, 241, 255, 100)
            txt = "ITM"
        else:
            color = (0, 200, 22, 100)
            txt = "TRP"
        draw: ImageDraw.ImageDraw = ImageDraw.Draw(img, 'RGBA')
        pos = (x * CHUNK_DIM, y * CHUNK_DIM, (x+1) * CHUNK_DIM, (y+1) * CHUNK_DIM)
        draw.rectangle(pos, color)
        draw.text((pos[0] + 4, pos[1] + 8), txt, (0, 0, 0, 255))
    if tile.stairs == DungeonRamStairType.STAIRS:
        color = (163, 170, 0, 100)
        txt = "STR"
        draw: ImageDraw.ImageDraw = ImageDraw.Draw(img, 'RGBA')
        pos = (x * CHUNK_DIM, y * CHUNK_DIM, (x+1) * CHUNK_DIM, (y+1) * CHUNK_DIM)
        draw.rectangle(pos, color)
        draw.text((pos[0] + 4, pos[1] + 8), txt, (0, 0, 0, 255))


def print_and_output_tiledata(addr_entities, addr_tiledata):
    t = time.time()
    filename_small = os.path.join(MAP_OUT_DIR, f'{t}_mini.png')
    filename_full = os.path.join(MAP_OUT_DIR, f'{t}_full.png')
    os.makedirs(MAP_OUT_DIR, exist_ok=True)
    img_mini = Image.new('RGB', (DUNGEON_TILEDATA__WIDTH, DUNGEON_TILEDATA__HEIGHT), (0, 0, 0))
    img_full = Image.new('RGB', (CHUNK_DIM * DUNGEON_TILEDATA__WIDTH, CHUNK_DIM * DUNGEON_TILEDATA__HEIGHT), (0, 0, 0))

    # TODO: To render the actual correct tileset we would need to know the actual mappa floor list index
    #       by looking it up in the arm9 dungeon list
    mappa_entry: MappaFloor = mappa_s.floor_lists[1][0]
    tileset_id = mappa_entry.layout.tileset_id
    dpl: Dpl = dungeon_bin.get(f'dungeon{tileset_id}.dpl')
    dpci: Dpci = dungeon_bin.get(f'dungeon{tileset_id}.dpci')
    dpc: Dpc = dungeon_bin.get(f'dungeon{tileset_id}.dpc')
    chunks = dpc.chunks_to_pil(dpci, dpl.palettes, 1)

    try:
        for y in range(0, DUNGEON_TILEDATA__HEIGHT):
            for x in range(0, DUNGEON_TILEDATA__WIDTH):
                i = y * DUNGEON_TILEDATA__WIDTH + x % DUNGEON_TILEDATA__WIDTH
                tile = DungeonRamTile(addr_tiledata + i * DUNGEON_TILEDATA__ENTRYLEN)
                draw_small_map(addr_entities, img_mini, x, y, tile)
                draw_full_map(addr_entities, img_full, x, y, tile, chunks)
        img_mini.save(filename_small)
        img_full.save(filename_full)
    except BaseException as ex:
        print(f"Error drawing map: {ex}")


def find_pointers(to: Union[int, Iterable]):
    if not isinstance(to, Iterable):
        to = [to]
    min = 0x2000000
    max = 0x2300000
    for i in range(min, max):
        addr = emu.memory.unsigned.read_long(i)
        for to_addr in to:
            if addr == to_addr:
                print(f'0x{i:0x} > 0x{to_addr:0x}')


def debug_dungeon():
    current_dungeon_id = emu.memory.signed.read_short(addr_current_id)
    print("=============================")
    if current_dungeon_id < 1:
        print("Not in dungeon", current_dungeon_id)
        return

    # These point to 0x21b9f14  - 0x21BA47D−0x21b9f14 = 569 before current floor
    #print(">> Pointers to 0x21b9cf4")
    #find_pointers(0x21b9cf4)
    #print(">> Pointers to 0x22482f8")
    #find_pointers(0x22482f8)
    #print(">> Pointers to 0x2248334")
    #find_pointers(0x2248334)
    #print(">> Pointers to dungeondata")
    #dd = 0x021BA47D
    #find_pointers(range(dd - 4 * 500, dd))

    start_dungeon_data = emu.memory.unsigned.read_long(pnt_dungeon_data.begin_absolute)
    addr_current_floor = start_dungeon_data + 0x569
    addr_tiledata = start_dungeon_data + 0x3f00
    addr_entities = start_dungeon_data + 0x12948
    addr_stole_from_kecleon = start_dungeon_data + 0x5b0  # 2int8 / bool?
    addr_stole_from_kecleon_event_flag = start_dungeon_data + 0x5b1  # 2int8 / bool?
    addr_weather_id = start_dungeon_data + 0xcb58  # uint8
    addr_natural_weather_id = addr_weather_id + 1  # uint8
    addr_weather_turns_left = addr_weather_id + 2  #
    addr_weather_flags = addr_weather_id + 18  #
    addr_weather_damage_counter = addr_weather_id + 34  # uint8?
    addr_mud_sport_counter = addr_weather_id + 35  # uint8?
    addr_water_sport_counter = addr_weather_id + 36  # uint8?
    addr_weather_nullify = addr_weather_id + 37  # uint8 / bool?
    addr_spawn_counter = start_dungeon_data + 0x5a2  # sint16
    addr_wind_counter = start_dungeon_data + 0x5a4  # sint16

    current_floor = emu.memory.signed.read_byte(addr_current_floor)
    stole_from_kecleon = emu.memory.signed.read_byte(addr_stole_from_kecleon)
    stole_from_kecleon_event_flag = emu.memory.signed.read_byte(addr_stole_from_kecleon_event_flag)
    weather_id = emu.memory.signed.read_byte(addr_weather_id)
    natural_weather_id = emu.memory.signed.read_byte(addr_natural_weather_id)

    print("Current dungeon:", current_dungeon_id)
    print("Current floor:", current_floor)
    print("Stole from Kecleon:", stole_from_kecleon)
    print("Stole from Kecleon, event flag:", stole_from_kecleon_event_flag)
    print("Weather:", weather_id)
    print("Natural Weather:", natural_weather_id)

    # Entity data
    # Monsters
    print("Monsters:")
    for i in range(0, DUNGEON_ENTITIES__LEN_MONSTER):
        epnt = print_generic_entity_data(addr_entities, i)
        if epnt is not None:
            print_monster_data(epnt)
    # Items
    print("Items:")
    start = DUNGEON_ENTITIES__LEN_MONSTER
    for i in range(start, start + DUNGEON_ENTITIES__LEN_ITEMS):
        epnt = print_generic_entity_data(addr_entities, i)
        if epnt is not None:
            print_item_data(epnt)
    # Traps
    print("Traps:")
    start += DUNGEON_ENTITIES__LEN_ITEMS
    for i in range(start, start + DUNGEON_ENTITIES__LEN_TRAPS):
        epnt = print_generic_entity_data(addr_entities, i)
        if epnt is not None:
            print_trap_data(epnt)

    print_and_output_tiledata(addr_entities, addr_tiledata)


def hook__debug_enable_branch(emu, address, size):
    emu.memory.register_arm9.r0 = 1 if emu.memory.register_arm9.r0 == 0 else 0


if __name__ == '__main__':
    emu = DeSmuME()

    emu.open("../../../skyworkcopy_us.nds")
    win = emu.create_sdl_window()

    emu.volume_set(0)

    emu.memory.register_exec(pmd2data.binaries['overlay/overlay_0011.bin'].functions['ScriptCommandParsing'].begin_absolute + 0x15C8, partial(hook__debug_enable_branch, emu))

    fc = 0
    while not win.has_quit():
        fc += 1
        win.process_input()
        emu.cycle()
        win.draw()
        if fc % 600 == 0:
            debug_dungeon()
            fc = 0
