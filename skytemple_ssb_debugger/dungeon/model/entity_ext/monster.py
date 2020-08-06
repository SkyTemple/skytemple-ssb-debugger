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

from skytemple_files.common.util import read_uintle, read_sintle
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.threadsafe import threadsafe_emu, wrap_threadsafe_emu

EXTRA_MONSTERS_BYTELEN = 576


class EntityExtMonster:
    def __init__(self, emu_thread: EmulatorThread, begin: int, cached: Union[memoryview, bytes]=None):
        self.emu_thread = emu_thread
        self.begin = begin
        if not cached:
            cached = memoryview(threadsafe_emu(
                emu_thread, lambda: emu_thread.emu.memory.unsigned[begin:begin + EXTRA_MONSTERS_BYTELEN]
            ))
        self.cached = cached

    @property
    def md_index(self) -> int:
        return read_uintle(self.cached, 0x02, 2)

    @md_index.setter
    @wrap_threadsafe_emu()
    def md_index(self, value: int):
        pass  # todo

    @property
    def md_index2(self) -> int:
        return read_uintle(self.cached, 0x04, 2)

    @md_index2.setter
    @wrap_threadsafe_emu()
    def md_index2(self, value: int):
        pass  # todo

    @property
    def enemy_flag(self) -> int:
        # 0 for non-enemy, 1 for real enemies,
        # when nonzero, name turns cyan and the gender is displayed by the name
        return read_uintle(self.cached, 0x06, 1)

    @enemy_flag.setter
    @wrap_threadsafe_emu()
    def enemy_flag(self, value: int):
        pass  # todo

    @property
    def teamleader_flag(self) -> bool:
        # TODO: Really bool?
        return bool(read_uintle(self.cached, 0x07, 1))

    @teamleader_flag.setter
    @wrap_threadsafe_emu()
    def teamleader_flag(self, value: bool):
        pass  # todo

    @property
    def ally_flag(self) -> bool:
        # TODO: Really bool?
        return bool(read_uintle(self.cached, 0x08, 1))

    @ally_flag.setter
    @wrap_threadsafe_emu()
    def ally_flag(self, value: bool):
        pass  # todo

    @property
    def kecleon_flag(self) -> bool:
        # TODO: Really bool?
        return bool(read_uintle(self.cached, 0x09, 1))

    @kecleon_flag.setter
    @wrap_threadsafe_emu()
    def kecleon_flag(self, value: bool):
        pass  # todo

#     print("    Level:", emu.memory.unsigned.read_byte(epnt + 0x0A))

    @property
    def level(self) -> int:
        return read_uintle(self.cached, 0x0A, 1)

    @level.setter
    @wrap_threadsafe_emu()
    def level(self, value: int):
        pass  # todo

    @property
    def name_type(self) -> int:
        return read_uintle(self.cached, 0x0C, 2)

    @name_type.setter
    @wrap_threadsafe_emu()
    def name_type(self, value: int):
        pass  # todo

    @property
    def iq(self) -> int:
        return read_uintle(self.cached, 0x0E, 2)

    @iq.setter
    @wrap_threadsafe_emu()
    def iq(self, value: int):
        pass  # todo
    
    @property
    def hp(self) -> int:
        return read_uintle(self.cached, 0x10, 2)

    @hp.setter
    @wrap_threadsafe_emu()
    def hp(self, value: int):
        pass  # todo

    @property
    def max_hp(self) -> int:
        return read_sintle(self.cached, 0x12, 2)

    @max_hp.setter
    @wrap_threadsafe_emu()
    def max_hp(self, value: int):
        pass  # todo

    @property
    def max_hp_boost(self) -> int:
        return read_sintle(self.cached, 0x16, 2)

    @max_hp_boost.setter
    @wrap_threadsafe_emu()
    def max_hp_boost(self, value: int):
        pass  # todo
    
    @property
    def attack(self) -> int:
        return read_uintle(self.cached, 0x1A, 2)

    @attack.setter
    @wrap_threadsafe_emu()
    def attack(self, value: int):
        pass  # todo
    
    @property
    def special_attack(self) -> int:
        return read_uintle(self.cached, 0x1B, 2)

    @special_attack.setter
    @wrap_threadsafe_emu()
    def special_attack(self, value: int):
        pass  # todo
    
    @property
    def defense(self) -> int:
        return read_uintle(self.cached, 0x1C, 2)

    @defense.setter
    @wrap_threadsafe_emu()
    def defense(self, value: int):
        pass  # todo
    
    @property
    def special_defense(self) -> int:
        return read_uintle(self.cached, 0x1D, 2)

    @special_defense.setter
    @wrap_threadsafe_emu()
    def special_defense(self, value: int):
        pass  # todo

    @property
    def experience_points(self) -> int:
        return read_sintle(self.cached, 0x20, 4)

    @experience_points.setter
    @wrap_threadsafe_emu()
    def experience_points(self, value: int):
        pass  # todo

#     TODO: 0x24 - 0x43: Stat boosts

    @property
    def direction_id(self) -> int:
        return read_uintle(self.cached, 0x4C, 1)

    @direction_id.setter
    @wrap_threadsafe_emu()
    def direction_id(self, value: int):
        pass  # todo

    @property
    def type1_id(self) -> int:
        return read_uintle(self.cached, 0x5E, 1)

    @type1_id.setter
    @wrap_threadsafe_emu()
    def type1_id(self, value: int):
        pass  # todo

    @property
    def type2_id(self) -> int:
        return read_uintle(self.cached, 0x5F, 1)

    @type2_id.setter
    @wrap_threadsafe_emu()
    def type2_id(self, value: int):
        pass  # todo

    @property
    def ability1_id(self) -> int:
        return read_uintle(self.cached, 0x60, 1)

    @ability1_id.setter
    @wrap_threadsafe_emu()
    def ability1_id(self, value: int):
        pass  # todo

    @property
    def ability2_id(self) -> int:
        return read_uintle(self.cached, 0x61, 1)

    @ability2_id.setter
    @wrap_threadsafe_emu()
    def ability2_id(self, value: int):
        pass  # todo

#     TODO: print("    Holding item?:", emu.memory.signed.read_byte(epnt + 0x62))
#     TODO: print("    Holding item2?:", emu.memory.signed.read_byte(epnt + 0x63))
#     TODO: print("    Held item qty:", emu.memory.signed.read_short(epnt + 0x64))
#     TODO: print("    Held item ID:", emu.memory.signed.read_short(epnt + 0x66))
#     TODO: print("    Held item ID2:", emu.memory.signed.read_short(epnt + 0x68))
