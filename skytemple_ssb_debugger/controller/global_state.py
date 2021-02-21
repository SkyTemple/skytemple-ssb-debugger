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
import json
import math
import os
import sys
from functools import partial
from threading import Lock
from typing import Optional, List, Dict
from enum import Enum

import gi

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptGameVar, GameVariableType
from skytemple_files.common.util import open_utf8
from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.threadsafe import threadsafe_emu_nonblocking, threadsafe_gtk_nonblocking, synchronized, \
    threadsafe_emu
from skytemple_files.common.i18n_util import f, _

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk


global_state_lock = Lock()

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

class MemTableEntry:
    def __init__(self, type_alloc: MemAllocType, unk1: int, unk2: int, start_address: int, available: int, used: int):
        self.type_alloc = type_alloc
        self.unk1 = unk1
        self.unk2 = unk2
        self.start_address = start_address
        self.available = available
        self.used = used
        
class MemTable:
    def __init__(self, entries: List[MemTableEntry], start_address: int, parent_table: int, addr_table: int, max_entries: int, addr_data: int, len_data: int):
        self.entries = entries
        self.start_address = start_address
        self.parent_table = parent_table
        self.addr_table = addr_table
        self.max_entries = max_entries
        self.addr_data = addr_data
        self.len_data = len_data

class GlobalStateController:

    def __init__(self, emu_thread: Optional[EmulatorThread], builder: Gtk.Builder):
        super().__init__()
        self.emu_thread = emu_thread
        self.builder = builder
        self.rom_data: Pmd2Data = None
        self._tables = []
        self._current_table = 0

    def change_current_table(self, current_table) -> bytes:
        self._current_table = max(0, min(current_table, len(self._tables)))
        threadsafe_gtk_nonblocking(self._do_sync_gtk)
    
    def dump(self, file_id) -> bytes:
        """Dump one file from the rom"""
        start = self._tables[self._current_table].entries[file_id].start_address
        length = self._tables[self._current_table].entries[file_id].available
        return self.emu_thread.emu.memory.unsigned[start:start+length]
        
    def sync(self):
        """Manual force sync of global state"""
        if not self.emu_thread:
            return
        threadsafe_emu_nonblocking(self.emu_thread, self._do_sync)

    # RUNNING IN EMULATOR THREAD:
    @synchronized(global_state_lock)
    def _do_sync(self):
        self._tables = []
        self._current_table = 0
        if self.rom_data:
            address_table_head = self.rom_data.binaries['arm9.bin'].pointers['MemoryAllocTable'].begin_absolute
            accessor = self.emu_thread.emu.memory.unsigned
            for x in range(accessor.read_long(address_table_head)):
                address_table = address_table_head+0x20+0x4*x
                self._tables.append(self._read_table(accessor.read_long(address_table)))
        threadsafe_gtk_nonblocking(self._do_sync_gtk)

    @synchronized(global_state_lock)
    def _do_sync_gtk(self):
        store = self.builder.get_object('global_state_alloc_store')
        store.clear()
        if self._current_table<len(self._tables):
            table = self._tables[self._current_table]
            for e in table.entries:
                line = [e.type_alloc.description, e.unk1, e.unk2, hex(e.start_address), hex(e.available), hex(e.used)]
                store.append(line)
            self.builder.get_object('lbl_alloc_table_header').set_text(f'{hex(table.start_address)} - {hex(table.start_address+0x1c)}')
            self.builder.get_object('lbl_alloc_table_data').set_text(f'{hex(table.addr_data)} - {hex(table.addr_data+table.len_data)}')
            self.builder.get_object('lbl_alloc_table_entries').set_text(f'{len(table.entries)}/{table.max_entries}')
            parent = None
            for i, t in enumerate(self._tables):
                if table.parent_table==t.start_address:
                    parent = i
            self.builder.get_object('lbl_alloc_table_parent').set_text(f'{hex(table.parent_table)} ({parent})')
        alloc_table_nb = self.builder.get_object('spin_alloc_table_nb')
        self.builder.get_object('spin_alloc_table_nb').set_text(str(self._current_table))
        self.builder.get_object('spin_alloc_table_nb').set_increments(1,1)
        self.builder.get_object('spin_alloc_table_nb').set_range(0, len(self._tables)-1)

    def _read_table(self, start_address) -> MemTable:
        accessor = self.emu_thread.emu.memory.unsigned
        parent_table = accessor.read_long(start_address+0x4)
        addr_table = accessor.read_long(start_address+0x8)
        entries = accessor.read_long(start_address+0xc)
        max_entries = accessor.read_long(start_address+0x10)
        addr_data = accessor.read_long(start_address+0x14)
        len_data = accessor.read_long(start_address+0x18)
        blocks = []
        for x in range(entries):
            entry_start = addr_table+0x18*x
            ent_type = MemAllocType(accessor.read_long(entry_start))
            unk1 = accessor.read_long(entry_start+0x4)
            unk2 = accessor.read_long(entry_start+0x8)
            start_addr = accessor.read_long(entry_start+0xc)
            available = accessor.read_long(entry_start+0x10)
            used = accessor.read_long(entry_start+0x14)
            blocks.append(MemTableEntry(ent_type, unk1, unk2, start_addr, available, used))
        return MemTable(blocks, start_address, parent_table, addr_table, max_entries, addr_data, len_data)
        
    def init(self, rom_data: Pmd2Data):
        if not self.emu_thread:
            return
        self.rom_data = rom_data
    
    def uninit(self):
        if not self.emu_thread:
            return
        self.rom_data = None
