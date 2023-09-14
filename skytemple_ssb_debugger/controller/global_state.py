#  Copyright 2020-2023 Capypara and the SkyTemple Contributors
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
from __future__ import annotations
from enum import Enum
from typing import Optional, List, Callable

import gi
from skytemple_files.common.i18n_util import _

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_emulator import EmulatorMemTable, emulator_sync_tables

from skytemple_ssb_debugger.ui_util import builder_get_assert

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk


class MemAllocType(Enum):
    UNUSED = 0x00, _('Free')
    STATIC = 0x01, _('Static')
    BLOCK = 0x02, _('Block')
    TEMPORARY = 0x03, _('Temporary')
    SUBTABLE = 0x04, _('Sub Table')

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    # ignore the first param since it's already set by __new__
    def __init__(
            self, _: int, description: str
    ):
        self.description = description


class GlobalStateController:
    def __init__(self, builder: Gtk.Builder):
        super().__init__()
        self.builder = builder
        self.rom_data: Optional[Pmd2Data] = None
        self._tables: List[EmulatorMemTable] = []
        self._current_table = 0

    def change_current_table(self, current_table):
        self._current_table = max(0, min(current_table, len(self._tables)))
        self._apply_sync()

    def dump(self, file_id, cb: Callable[[bytes], None]):
        """Dump one file from the rom"""
        return self._tables[self._current_table].entries[file_id].dump(cb)

    def sync(self):
        """Manual force sync of global state"""
        self._current_table = 0
        def update(vals):
            self._tables = list(vals)
            self._apply_sync()

        assert self.rom_data is not None
        emulator_sync_tables(self.rom_data.bin_sections.itcm.data.MEMORY_ALLOCATION_TABLE.absolute_address, update)

    def _apply_sync(self):
        store = builder_get_assert(self.builder, Gtk.ListStore, 'global_state_alloc_store')
        store.clear()
        if self._current_table < len(self._tables):
            table = self._tables[self._current_table]
            for e in table.entries:
                line = [
                    MemAllocType(int(e.type_alloc)).description,  # type: ignore
                    e.unk1,
                    e.unk2,
                    hex(e.start_address),
                    hex(e.available),
                    hex(e.used)
                ]
                store.append(line)
            builder_get_assert(self.builder, Gtk.Label, 'lbl_alloc_table_header').set_text(
                f'{hex(table.start_address)} - {hex(table.start_address + 0x1c)}')
            builder_get_assert(self.builder, Gtk.Label, 'lbl_alloc_table_data').set_text(
                f'{hex(table.addr_data)} - {hex(table.addr_data + table.len_data)}')
            builder_get_assert(self.builder, Gtk.Label, 'lbl_alloc_table_entries').set_text(f'{len(table.entries)}/{table.max_entries}')
            parent = None
            for i, t in enumerate(self._tables):
                if table.parent_table == t.start_address:
                    parent = i
            builder_get_assert(self.builder, Gtk.Label, 'lbl_alloc_table_parent').set_text(f'{hex(table.parent_table)} ({parent})')
        alloc_table_nb = builder_get_assert(self.builder, Gtk.SpinButton, 'spin_alloc_table_nb')
        alloc_table_nb.set_text(str(self._current_table))
        alloc_table_nb.set_increments(1, 1)
        alloc_table_nb.set_range(0, len(self._tables) - 1)

    def init(self, rom_data: Pmd2Data):
        self.rom_data = rom_data

    def uninit(self):
        self.rom_data = None
