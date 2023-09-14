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
import json
import logging
import math
import os
import sys
from functools import partial
from typing import Optional, List, Dict, Mapping, Sequence, cast

import gi

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptGameVar, GameVariableType
from skytemple_files.common.util import open_utf8
from skytemple_ssb_emulator import emulator_register_script_variable_set, emulator_unregister_script_variable_set, \
    emulator_write_game_variable, emulator_sync_vars

from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_files.common.i18n_util import f, _

from skytemple_ssb_debugger.ui_util import builder_get_assert

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk

logger = logging.getLogger(__name__)


class VariableController:
    CATEGORIES = {
        _('Scenario'): ['SCENARIO_MAIN', 'SCENARIO_MAIN_BIT_FLAG', 'SCENARIO_TALK_BIT_FLAG', 'SCENARIO_SIDE',
                        'SCENARIO_SUB1', 'SCENARIO_SUB2', 'SCENARIO_SUB3', 'SCENARIO_SUB4', 'SCENARIO_SUB5',
                        'SCENARIO_SUB6', 'SCENARIO_SUB7', 'SCENARIO_SUB8', 'SCENARIO_BALANCE_FLAG',
                        'COMPULSORY_SAVE_POINT', 'COMPULSORY_SAVE_POINT_SIDE', 'PERFORMANCE_PROGRESS_LIST',
                        'SCENARIO_BALANCE_DEBUG'],
        _('Init'): ['SCENARIO_SELECT', 'GROUND_ENTER', 'GROUND_ENTER_LINK', 'GROUND_GETOUT', 'GROUND_MAP',
                    'GROUND_PLACE', 'GROUND_START_MODE'],
        _('Dungeon Progress'): ['DUNGEON_OPEN_LIST', 'DUNGEON_ENTER_LIST', 'DUNGEON_ARRIVE_LIST',
                                'DUNGEON_CONQUEST_LIST',
                                'DUNGEON_PRESENT_LIST', 'DUNGEON_REQUEST_LIST'],
        _('Dungeon Init'): ['DUNGEON_SELECT', 'DUNGEON_ENTER', 'DUNGEON_ENTER_MODE', 'DUNGEON_ENTER_INDEX',
                            'DUNGEON_ENTER_FREQUENCY', 'DUNGEON_RESULT'],
        _('World Map'): ['WORLD_MAP_MARK_LIST_NORMAL', 'WORLD_MAP_MARK_LIST_SPECIAL', 'WORLD_MAP_LEVEL'],
        _('Specific'): ['SIDE02_TALK', 'SIDE06_ROOM', 'SIDE08_BOSS2ND', 'SIDE01_BOSS2ND',
                        'CRYSTAL_COLOR_01', 'CRYSTAL_COLOR_02', 'CRYSTAL_COLOR_03', 'EVENT_LOCAL',
                        'DUNGEON_EVENT_LOCAL',
                        'BIT_FUWARANTE_LOCAL', 'LOTTERY_RESULT', 'SUB30_TREASURE_DISCOVER', 'SUB30_SPOT_DISCOVER',
                        'SUB30_SPOT_LEVEL', 'SUB30_PROJECTP'],
        _('Player'): ['PLAYER_KIND', 'ATTENDANT1_KIND', 'ATTENDANT2_KIND', 'CARRY_GOLD', 'BANK_GOLD',
                      'HERO_FIRST_KIND', 'HERO_FIRST_NAME', 'PARTNER_FIRST_KIND', 'PARTNER_FIRST_NAME',
                      'HERO_TALK_KIND', 'PARTNER_TALK_KIND', 'RANDOM_REQUEST_NPC03_KIND', 'CONFIG_COLOR_KIND',
                      ],
        _('Mode'): ['GAME_MODE', 'EXECUTE_SPECIAL_EPISODE_TYPE', 'SPECIAL_EPISODE_TYPE', 'SPECIAL_EPISODE_OPEN',
                    'SPECIAL_EPISODE_OPEN_OLD', 'SPECIAL_EPISODE_CONQUEST'],
        _('Backup'): ['SCENARIO_SELECT_BACKUP', 'SCENARIO_MAIN_BIT_FLAG_BACKUP', 'GROUND_ENTER_BACKUP',
                      'GROUND_ENTER_LINK_BACKUP', 'GROUND_GETOUT_BACKUP', 'GROUND_MAP_BACKUP', 'GROUND_PLACE_BACKUP',
                      'DUNGEON_ENTER_BACKUP', 'DUNGEON_ENTER_MODE_BACKUP', 'DUNGEON_ENTER_INDEX_BACKUP',
                      'DUNGEON_ENTER_FREQUENCY_BACKUP', 'DUNGEON_RESULT_BACKUP', 'GROUND_START_MODE_BACKUP',
                      'PLAYER_KIND_BACKUP', 'ATTENDANT1_KIND_BACKUP', 'ATTENDANT2_KIND_BACKUP',
                      'ITEM_BACKUP', 'ITEM_BACKUP_KUREKURE', 'ITEM_BACKUP_TAKE', 'ITEM_BACKUP_GET'],
        _('Misc'): ['VERSION', 'CONDITION', 'ROM_VARIATION', 'LANGUAGE_TYPE',
                    'FRIEND_SUM', 'UNIT_SUM',
                    'POSITION_X', 'POSITION_Y', 'POSITION_HEIGHT', 'POSITION_DIRECTION',
                    'STATION_ITEM_STATIC', 'STATION_ITEM_TEMP', 'DELIVER_ITEM_STATIC', 'DELIVER_ITEM_TEMP',
                    'REQUEST_CLEAR_COUNT', 'REQUEST_THANKS_RESULT_KIND', 'REQUEST_THANKS_RESULT_VARIATION',
                    'RECYCLE_COUNT', 'TEAM_RANK_EVENT_LEVEL', 'PLAY_OLD_GAME', 'NOTE_MODIFY_FLAG'],
    }

    def __init__(self, builder: Gtk.Builder, context: AbstractDebuggerControlContext):
        super().__init__()
        self.builder = builder
        self.context = context
        self.rom_data: Optional[Pmd2Data] = None
        self.var_form_elements: Optional[List[Optional[List[Optional[Gtk.Widget]]]]] = None
        self._suppress_events = False
        self._boost = False
        # Cached variable values
        self._variable_cache: Dict[Pmd2ScriptGameVar, List[int]] = {}
        self._pending_sync = False

        self.variables_changed_but_not_saved = False

    def sync(self):
        """Manual force sync of all variables"""

        def update(vals: Mapping[int, Sequence[int]]):
            self._pending_sync = False
            assert self.rom_data is not None
            self._variable_cache = {
                self.rom_data.script_data.game_variables__by_id[k]: list(v) for k, v in vals.items()
            }
            self._apply_sync()

        self._pending_sync = True
        notebook = builder_get_assert(self.builder, Gtk.Notebook, 'variables_notebook')
        notebook.set_sensitive(False)
        emulator_sync_vars(update)

    def _apply_sync(self):
        self._suppress_events = True
        assert self.var_form_elements is not None and self.rom_data is not None
        for i, sub in enumerate(self.var_form_elements):
            if sub is not None:
                for offset, el in enumerate(sub):
                    if el is not None:
                        val = self._variable_cache[self.rom_data.script_data.game_variables__by_id[i]][offset]
                        if isinstance(el, Gtk.Entry):
                            el.set_text(str(val))
                        else:
                            cast(Gtk.Switch, el).set_active(bool(val))
        builder_get_assert(self.builder, Gtk.Notebook, 'variables_notebook').set_sensitive(True)
        self._suppress_events = False

    def init(self, rom_data: Pmd2Data):
        self.rom_data = rom_data
        self.var_form_elements = [None for _ in range(0, len(rom_data.script_data.game_variables))]
        notebook = builder_get_assert(self.builder, Gtk.Notebook, 'variables_notebook')

        # Build the GTK form
        for category, items in self.CATEGORIES.items():
            tab_label = Gtk.Label.new(category)
            tab_label.show()
            sw: Gtk.ScrolledWindow = Gtk.ScrolledWindow.new()
            page_grid: Gtk.Grid = Gtk.Grid.new()
            page_grid.set_margin_bottom(5)
            page_grid.set_margin_left(5)
            page_grid.set_margin_top(5)
            page_grid.set_margin_right(5)
            sw.add(page_grid)
            notebook.append_page(sw, tab_label)
            row = 0
            for item in items:
                var: Pmd2ScriptGameVar = rom_data.script_data.game_variables__by_name[item]
                self.var_form_elements[var.id] = [None for _ in range(0, var.nbvalues)]
                label: Gtk.Label = Gtk.Label.new(item)
                label.set_valign(Gtk.Align.START)
                label.set_markup(f'<b>{item}</b>')
                label.set_halign(Gtk.Align.START)
                label.set_margin_top(8)
                label.set_margin_bottom(4)
                page_grid.attach(label, 0, row, 1, 1)
                if var.nbvalues == 1:
                    page_grid.attach(self.create_var_form_element(var, 0, no_label=True), 0, row + 1, 1, 1)
                elif var.name.startswith('SCENARIO_') and var.nbvalues == 2 and var.type == GameVariableType.UINT8:
                    sub_box: Gtk.Box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)
                    sub_box.set_margin_bottom(2)
                    page_grid.attach(sub_box, 0, row + 1, 1, 1)
                    sub_box.pack_start(self.create_var_form_element(var, 0, label='Scenario'), True, True, 0)
                    sub_box.pack_start(self.create_var_form_element(var, 1, label='Level'), True, True, 0)
                elif var.type == GameVariableType.BIT:
                    sub_grid: Gtk.Grid = Gtk.Grid.new()
                    sub_grid.set_margin_bottom(2)
                    page_grid.attach(sub_grid, 0, row + 1, 1, 1)
                    for i in range(0, var.nbvalues):
                        x = i % 3
                        y = math.floor(i / 3)
                        sub_grid.attach(self.create_var_form_element(var, i), x, y, 1, 1)
                else:
                    sub_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
                    sub_box.set_margin_bottom(2)
                    page_grid.attach(sub_box, 0, row + 1, 1, 1)
                    for i in range(0, var.nbvalues):
                        sub_box.pack_start(self.create_var_form_element(var, i), True, True, 0)
                row += 2

        notebook.show_all()
        self.sync()

        emulator_register_script_variable_set(
            self.rom_data.bin_sections.arm9.functions.SaveScriptVariableValue.absolute_addresses,
            self.rom_data.bin_sections.arm9.functions.SaveScriptVariableValueAtIndex.absolute_addresses,
            self.hook__variable_set
        )

    def uninit(self):
        notebook = builder_get_assert(self.builder, Gtk.Notebook, 'variables_notebook')
        for _ in range(0, notebook.get_n_pages()):
            # TODO: Do the children need to be destroyed?
            notebook.remove_page(0)

        emulator_unregister_script_variable_set()

    def create_var_form_element(self, var: Pmd2ScriptGameVar, offset: int, label: Optional[str] = None, no_label=False):
        box: Gtk.ButtonBox = Gtk.ButtonBox.new(Gtk.Orientation.HORIZONTAL)
        box.set_margin_bottom(2)
        box.set_halign(Gtk.Align.END)
        if not no_label:
            if not label:
                label = f'{offset}'
            else:
                label = f'{offset} ({label})'
            # For bit fields, don't add extra labels.
            if var.type != GameVariableType.BIT:
                label_obj: Gtk.Label = Gtk.Label.new(label)
                label_obj.set_halign(Gtk.Align.END)
                label_obj.set_margin_right(5)
                box.pack_start(label_obj, False, True, 0)
        else:
            label = ''
        wdg: Gtk.Widget
        if var.type == GameVariableType.BIT:
            wgd1 = Gtk.CheckButton.new()
            wgd1.set_label(label)
            wgd1.connect('toggled', partial(self.on_var_changed_check, var, offset))
            wdg = wgd1
        else:
            wgd2 = Gtk.Entry.new()
            if var.type == GameVariableType.UINT32 or var.type == GameVariableType.INT32:
                wgd2.set_width_chars(11)
            elif var.type == GameVariableType.UINT16 or var.type == GameVariableType.INT16:
                wgd2.set_width_chars(6)
            else:
                wgd2.set_width_chars(4)
            wgd2.connect('focus-out-event', partial(self.on_var_changed_entry, var, offset))
            wdg = wgd2

        wdg.set_halign(Gtk.Align.END)
        box.pack_start(wdg, True, True, 0)
        self.var_form_elements[var.id][offset] = wdg  # type: ignore
        return box

    def on_var_changed_entry(self, var: Pmd2ScriptGameVar, offset: int, wdg: Gtk.Entry, *args):
        if self._suppress_events:
            return
        self.variables_changed_but_not_saved = True
        try:
            try:
                value = int(wdg.get_text())
            except ValueError as err:
                raise ValueError(_("The variable must have a number as value.")) from err
            if var.type == GameVariableType.BIT:
                if value < 0 or value > 1:
                    raise ValueError("This variable must have one of these values: 0, 1.")
            elif var.type == GameVariableType.UINT8:
                if value < 0 or value > 255:
                    raise ValueError("This variable must have a value between: 0 and 255.")
            elif var.type == GameVariableType.INT8:
                if value < -128 or value > 127:
                    raise ValueError("This variable must have a value between: -128 and 127.")
            elif var.type == GameVariableType.UINT16:
                if value < 0 or value > 65535:
                    raise ValueError("This variable must have a value between: 0 and 65535.")
            elif var.type == GameVariableType.INT16:
                if value < -32768 or value > 32767:
                    raise ValueError("This variable must have a value between: -32768 and 32767.")
            elif var.type == GameVariableType.UINT32:
                if value < 0 or value > 4294967295:
                    raise ValueError("This variable must have a value between: 0 and 4294967295.")
            elif var.type == GameVariableType.INT32:
                if value < -2147483648 or value > 2147483647:
                    raise ValueError("This variable must have a value between: -2147483648 and 2147483647.")
        except ValueError as err:
            md = self.context.message_dialog(
                builder_get_assert(self.builder, Gtk.Window, 'main_window'),
                Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                Gtk.ButtonsType.OK,
                f(_("Invalid variable value:\n{err}\nThe value was not written to RAM.")),
                title=_("Error!")
            )
            md.set_position(Gtk.WindowPosition.CENTER)
            md.run()
            md.destroy()
            return True
        self._queue_variable_write(var.id, offset, value)
        return True

    def on_var_changed_check(self, var: Pmd2ScriptGameVar, offset: int, wdg: Gtk.CheckButton, *args):
        if self._suppress_events:
            return
        self.variables_changed_but_not_saved = True
        self._queue_variable_write(var.id, offset, 1 if wdg.get_active() else 0)
        return True

    def load(self, index: int, config_dir: str):
        # TODO: Not very efficient at the moment but ok.
        self.variables_changed_but_not_saved = False
        path = os.path.join(config_dir, f'vars.{index}.json')
        if not os.path.exists(path):
            return
        try:
            with open_utf8(path, 'r') as f:
                vars = json.load(f)
            for name, values in vars.items():
                assert self.rom_data is not None
                var_id = self.rom_data.script_data.game_variables__by_name[name].id
                for i, value in enumerate(values):
                    self._queue_variable_write(var_id, i, value)
        except BaseException as err:
            self.context.display_error(
                sys.exc_info(),
                str(err),
                _("Unable to load variables!")
            )
            return

    def save(self, index: int, config_dir: str):
        self.variables_changed_but_not_saved = False
        vars = {k.name: v for k, v in self._variable_cache.items()}
        with open_utf8(os.path.join(config_dir, f'vars.{index}.json'), 'w') as f:
            json.dump(vars, f)

    def _queue_variable_write(self, var_id: int, offset: int, value: int):
        try:
            emulator_write_game_variable(var_id, offset, value)
        except:
            logger.error(f"failed writing game var: {var_id}@{offset} = {value}")
            raise

        # Also update the cached values
        for var in self._variable_cache.keys():
            if var.id == var_id:
                self._variable_cache[var][offset] = value
                break

    def hook__variable_set(self, var_id, var_offset, value):
        assert self.rom_data is not None and self.var_form_elements is not None
        var = self.rom_data.script_data.game_variables__by_id[var_id]
        if var not in self._variable_cache:
            if not self._pending_sync:
                self.sync()
            return
        self._suppress_events = True
        entry_list = self.var_form_elements[var_id]
        if entry_list is not None:
            entry = self.var_form_elements[var_id][var_offset]
            if entry is not None:
                if isinstance(entry, Gtk.Entry):
                    entry.set_text(str(value))
                else:
                    entry.set_active(bool(value))
        self._suppress_events = False

    def set_boost(self, state):
        boost_before = self._boost
        self._boost = state

        if not state and boost_before:
            self.sync()
