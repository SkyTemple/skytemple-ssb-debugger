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
from threading import Lock
from typing import List

from skytemple_ssb_debugger.dungeon.model.entity import DungeonEntity
from skytemple_ssb_debugger.dungeon.model.entity_ext.item import EntityExtItem
from skytemple_ssb_debugger.dungeon.model.entity_ext.monster import EntityExtMonster
from skytemple_ssb_debugger.dungeon.model.entity_ext.trap import EntityExtTrap
from skytemple_ssb_debugger.dungeon.model.floor_data import DungeonFloorData
from skytemple_ssb_debugger.dungeon.model.map import DungeonMap
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.threadsafe import wrap_threadsafe_emu

dungeon_state_lock = Lock()
OFFSET_MAP_DATA = 0x3f00


class DungeonState:
    def __init__(self, emu_thread: EmulatorThread, pnt_dungeon_data: int, addr_current_dungeon_id: int):
        self.emu_thread = emu_thread
        self.pnt_dungeon_data = pnt_dungeon_data
        self.addr_current_dungeon_id = addr_current_dungeon_id

    @property
    def valid(self) -> bool:
        """
        Checks if the current dungeon ID is > 0 and smaller than 200.
        TODO: What is the actual max dungeon ID?
        """
        return 0 < self.dungeon_id < 200

    @property
    @wrap_threadsafe_emu()
    def dungeon_id(self) -> int:
        return self.emu_thread.emu.memory.signed.read_short(self.addr_current_dungeon_id)

    def load_map(self) -> DungeonMap:
        return DungeonMap(self.emu_thread, self.start_dungeon_data + OFFSET_MAP_DATA)

    @property
    @wrap_threadsafe_emu()
    def start_dungeon_data(self):
        return self.emu_thread.emu.memory.unsigned.read_long(self.pnt_dungeon_data)

    @property
    def floor_data(self) -> DungeonFloorData:
        return None  # todo

    @property
    def monsters(self) -> List[DungeonEntity[EntityExtMonster]]:
        return None  # todo

    @property
    def items(self) -> List[DungeonEntity[EntityExtItem]]:
        return None  # todo

    @property
    def bag_items(self) -> List[DungeonEntity[EntityExtItem]]:
        return None  # todo

    @property
    def traps(self) -> List[DungeonEntity[EntityExtTrap]]:
        return None  # todo
