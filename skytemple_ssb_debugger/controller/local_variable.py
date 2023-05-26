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
from typing import Optional, List, Sequence

from gi.overrides.Gtk import TreeViewColumn
from gi.repository import Gtk

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptGameVar
from skytemple_ssb_emulator import emulator_sync_local_vars

from skytemple_ssb_debugger.controller.debugger import DebuggerController
from skytemple_ssb_debugger.controller.ground_state import resizable
from skytemple_ssb_debugger.model.breakpoint_file_state import BreakpointFileState
from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct
from skytemple_files.common.i18n_util import _


class LocalVariableController:
    """Controller for showing both local and macro variables"""
    def __init__(self, builder: Gtk.Builder, debugger: Optional[DebuggerController]):
        self.builder = builder
        self.debugger = debugger

        self._local__sw: Gtk.ScrolledWindow = builder.get_object('local_variables_sw')
        self._macro__sw: Gtk.ScrolledWindow = builder.get_object('macro_variables_sw')

        self._local__not_loaded: Gtk.Viewport = builder.get_object('local_vars_ges_not_loaded')
        self._macro__not_loaded: Gtk.Viewport = builder.get_object('macro_vars_ges_not_loaded')

        self._local__list_store: Gtk.ListStore = builder.get_object('local_variables_store')
        self._macro__list_store: Gtk.ListStore = builder.get_object('macro_variables_store')

        self._local__tree: Gtk.TreeView = builder.get_object('local_variables_list')
        self._local__tree.append_column(resizable(TreeViewColumn(_("Name"), Gtk.CellRendererText(), text=0)))
        self._local__tree.append_column(resizable(TreeViewColumn(_("Value"), Gtk.CellRendererText(), text=1)))

        self._macro__tree: Gtk.TreeView = builder.get_object('macro_variables_list')
        self._macro__tree.append_column(resizable(TreeViewColumn(_("Name"), Gtk.CellRendererText(), text=0)))
        self._macro__tree.append_column(resizable(TreeViewColumn(_("Value"), Gtk.CellRendererText(), text=1)))

        self._local_vars_specs: Optional[List[Pmd2ScriptGameVar]] = None
        self._local_vars_values: Sequence[int] = []
        self._rom_data: Optional[Pmd2Data] = None
        self._was_disabled = True

    def init(self, rom_data: Pmd2Data):
        self._local_vars_specs = []
        self._rom_data = rom_data
        for var in rom_data.script_data.game_variables:
            if var.is_local:
                self._local_vars_specs.append(var)

    def sync(self, breaked_for: ScriptRuntimeStruct, file_state: Optional[BreakpointFileState] = None):
        if not self.debugger or not self.debugger.ground_engine_state or not self._local_vars_specs:
            return self.disable()

        if self._was_disabled:
            self._local__sw.remove(self._local__not_loaded)
            self._macro__sw.remove(self._macro__not_loaded)
            self._local__sw.add(self._local__tree)
            self._macro__sw.add(self._macro__tree)
            self._was_disabled = False

        # Local variables
        self._local__list_store.clear()
        self._local_vars_values = emulator_sync_local_vars(breaked_for.pnt_to_block_start)

        # Macro variables
        self._macro__list_store.clear()
        if file_state and file_state.current_macro_variables:
            for name, value in file_state.current_macro_variables.items():
                self._macro__list_store.append([name, str(value)])

    def _do_sync_gtk(self):
        if self._local_vars_specs is not None:
            for i, var in enumerate(self._local_vars_specs):
                value = self._local_vars_values[i]
                self._local__list_store.append([var.name, value])

    def disable(self):
        if not self._was_disabled:
            self._local__sw.remove(self._local__tree)
            self._macro__sw.remove(self._macro__tree)
            self._local__sw.add(self._local__not_loaded)
            self._macro__sw.add(self._macro__not_loaded)
            self._was_disabled = True
