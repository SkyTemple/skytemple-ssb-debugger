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
import json
import math
import os
import sys
from functools import partial
from threading import Lock
from typing import Optional, List, Dict

import gi

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptGameVar, GameVariableType
from skytemple_files.common.util import open_utf8
from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.threadsafe import threadsafe_emu_nonblocking, threadsafe_gtk_nonblocking, synchronized, \
    threadsafe_emu

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk


global_state_lock = Lock()

class GlobalStateController:

    def __init__(self, emu_thread: Optional[EmulatorThread], builder: Gtk.Builder):
        super().__init__()
        self.emu_thread = emu_thread
        self.builder = builder
        self.rom_data: Pmd2Data = None
        self._files = []

    def dump(self, file_id) -> bytes:
        """Dump one file from the rom"""
        start = self._files[file_id][3]
        length = self._files[file_id][4]
        return self.emu_thread.emu.memory.unsigned[start:start+length]
        
    def sync(self):
        """Manual force sync of global state"""
        if not self.emu_thread:
            return
        threadsafe_emu_nonblocking(self.emu_thread, self._do_sync)

    # RUNNING IN EMULATOR THREAD:
    @synchronized(global_state_lock)
    def _do_sync(self):
        self._files = []
        if self.rom_data:
            address_table_head = self.rom_data.binaries['arm9.bin'].pointers['MemoryAllocTable'].begin_absolute
            accessor = self.emu_thread.emu.memory.unsigned
            addr_table = accessor.read_long(address_table_head+0xc)
            entries = accessor.read_long(address_table_head+0x10)
            for x in range(entries):
                entry_start = addr_table+0x18*x
                ent_type = accessor.read_long(entry_start)
                unk1 = accessor.read_long(entry_start+0x4)
                unk2 = accessor.read_long(entry_start+0x8)
                start_addr = accessor.read_long(entry_start+0xc)
                available = accessor.read_long(entry_start+0x10)
                used = accessor.read_long(entry_start+0x14)
                self._files.append([ent_type, unk1, unk2, start_addr, available, used])
        threadsafe_gtk_nonblocking(self._do_sync_gtk)

    @synchronized(global_state_lock)
    def _do_sync_gtk(self):
        store = self.builder.get_object('global_state_alloc_store')
        store.clear()
        for f in self._files:
            line = [f[0], f[1], f[2], hex(f[3]), hex(f[4]), hex(f[5])]
            store.append(line)

    def init(self, rom_data: Pmd2Data):
        if not self.emu_thread:
            return
        self.rom_data = rom_data
    
    def uninit(self):
        if not self.emu_thread:
            return
        self.rom_data = None
