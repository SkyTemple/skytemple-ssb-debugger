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
from skytemple_ssb_debugger.dungeon.model.field import DungeonField, FIELD_BYTELEN
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.threadsafe import threadsafe_emu

MAP_WIDTH = 56
MAP_HEIGHT = 32


class DungeonMap:
    def __init__(self, emu_thread: EmulatorThread, begin_mapdata: int):
        self.emu_thread = emu_thread
        self.begin_mapdata = begin_mapdata
        self.cached_tiledata = memoryview(threadsafe_emu(
            emu_thread, lambda: emu_thread.emu.memory.unsigned[
                                    begin_mapdata:begin_mapdata+(FIELD_BYTELEN * MAP_WIDTH * MAP_HEIGHT)
                                ]
        ))

    def __iter__(self):
        for y in range(0, MAP_HEIGHT):
            for x in range(0, MAP_WIDTH):
                yield self.get(x, y)

    def get(self, x: int, y: int) -> DungeonField:
        i = y * MAP_WIDTH + x % MAP_WIDTH
        cache_start = i * FIELD_BYTELEN
        return DungeonField(
            self.emu_thread, self.begin_mapdata + i * FIELD_BYTELEN,
            self.cached_tiledata[cache_start:cache_start+FIELD_BYTELEN]
        )
