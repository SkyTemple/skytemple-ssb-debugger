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
from typing import Optional, Dict

import gi
from gi.repository.Gtk import TreeViewColumn

from explorerscript.ssb_converting.ssb_data_types import SsbRoutineType
from skytemple_ssb_debugger.model.constants import ICON_GLOBAL_SCRIPT, ICON_ACTOR, ICON_OBJECT, ICON_PERFORMER, \
    ICON_POSITION_MARKER, ICON_EVENTS
from skytemple_ssb_debugger.model.ground_engine_state import TALK_HANGER_OFFSET
from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct
from skytemple_files.common.i18n_util import f, _

GE_FILE_STORE_SCRIPT = _('Script')

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk

from desmume.emulator import DeSmuME
from skytemple_ssb_debugger.controller.debugger import DebuggerController


def resizable(column):
    column.set_resizable(True)
    return column


class GroundStateController:
    def __init__(self, emu: Optional[DeSmuME], debugger_controller: DebuggerController, builder: Gtk.Builder):
        self.emu = emu
        self.debugger = debugger_controller
        self.builder = builder

        self._was_running_last_sync = False

        self._files__sw: Gtk.ScrolledWindow = builder.get_object('ground_state_files_tree_sw')
        self._entities__sw: Gtk.ScrolledWindow = builder.get_object('ground_state_entities_tree_sw')

        self._files__not_loaded: Gtk.Viewport = builder.get_object('ground_state_files_tree_engine_not_loaded')
        self._entities__not_loaded: Gtk.Viewport = builder.get_object('ground_state_entities_tree_engine_not_loaded')

        self._ssb_tree_store_iters: Dict[int, Gtk.TreeIter] = {}

        self._files__tree: Gtk.TreeView = builder.get_object('ground_state_files_tree')
        icon = Gtk.CellRendererPixbuf()
        path = Gtk.CellRendererText()
        column = TreeViewColumn(_("Path"))
        column.pack_start(icon, True)
        column.pack_start(path, True)
        column.add_attribute(icon, "icon_name", 0)
        column.add_attribute(path, "text", 1)
        self._files__tree.append_column(resizable(column))
        self._files__tree.append_column(resizable(TreeViewColumn(_("Hanger"), Gtk.CellRendererText(), text=3)))  # TRANSLATOR: Special context of a loaded script... the weird is engrish.
        self._files__tree.append_column(resizable(TreeViewColumn(_("Type"), Gtk.CellRendererText(), text=2)))

        self._entities__tree: Gtk.TreeView = builder.get_object('ground_state_entities_tree')
        #self._files__tree.append_column(resizable(TreeViewColumn("Preview", Gtk.CellRendererPixbuf(), xxx=4)))
        icon = Gtk.CellRendererPixbuf()
        debug_icon = Gtk.CellRendererPixbuf()
        slot_id = Gtk.CellRendererText()
        column = TreeViewColumn(_("ID"))
        column.pack_start(icon, True)
        column.pack_start(debug_icon, True)
        column.pack_start(slot_id, True)
        column.add_attribute(debug_icon, "icon_name", 6)
        column.add_attribute(icon, "icon_name", 7)
        column.add_attribute(slot_id, "text", 0)
        self._entities__tree.append_column(resizable(column))
        self._entities__tree.append_column(resizable(TreeViewColumn(_("Kind"), Gtk.CellRendererText(), text=5)))
        self._entities__tree.append_column(resizable(TreeViewColumn(_("Hanger"), Gtk.CellRendererText(), text=1)))  # TRANSLATOR: Special context of a loaded script... the weird is engris
        self._entities__tree.append_column(resizable(TreeViewColumn(_("X"), Gtk.CellRendererText(), text=8)))
        self._entities__tree.append_column(resizable(TreeViewColumn(_("Y"), Gtk.CellRendererText(), text=9)))
        self._entities__tree.append_column(resizable(TreeViewColumn(_("Sector"), Gtk.CellRendererText(), text=2)))  # TRANSLATOR: Engrish for 'Layer'
        self._entities__tree.append_column(resizable(TreeViewColumn(_("Script"), Gtk.CellRendererText(), text=3)))

        self._files__tree_store: Gtk.TreeStore = builder.get_object('ground_state_files_tree_store')
        self._entities__tree_store: Gtk.TreeStore = builder.get_object('ground_state_entities_store')

    def sync_break_hanger(self):
        """
        Only sync the "breaked" property of all loaded SSB files and update them in the views.
        The views must be built already.
        """
        ground_state = self.debugger.ground_engine_state
        for ssb in ground_state.loaded_ssb_files:
            if ssb is not None and ssb.hanger in self._ssb_tree_store_iters:
                if ssb.breaked:
                    self._entities__tree_store[self._ssb_tree_store_iters[ssb.hanger]][6] = 'media-playback-pause'
                else:
                    self._entities__tree_store[self._ssb_tree_store_iters[ssb.hanger]][6] = ''

    def sync(self, code_editor=None, breaked_for: ScriptRuntimeStruct = None):
        """
        Synchronize the ground engine state to the UI. If code_editor is set, send the opcodes that currently being
        run by the engine to the editor.
        """
        if self.debugger and self.debugger.ground_engine_state:
            ground_state = self.debugger.ground_engine_state
            if ground_state.running and not self._was_running_last_sync:
                # Is now running
                self._files__sw.remove(self._files__not_loaded)
                self._entities__sw.remove(self._entities__not_loaded)
                self._files__sw.add(self._files__tree)
                self._entities__sw.add(self._entities__tree)
            elif not ground_state.running and self._was_running_last_sync:
                # Is now no longer running
                self._files__sw.remove(self._files__tree)
                self._entities__sw.remove(self._entities__tree)
                self._files__sw.add(self._files__not_loaded)
                self._entities__sw.add(self._entities__not_loaded)

            self._was_running_last_sync = ground_state.running

            if ground_state.running:
                # Is runningues
                global_script, ssb, ssx, actors, objects, performers, events = ground_state.collect()

                if code_editor:
                    # Sync the code editor execution lines
                    files = {}
                    try:
                        if global_script.script_struct.hanger_ssb > -1 and ssb[global_script.script_struct.hanger_ssb] is not None:
                            if ssb[global_script.script_struct.hanger_ssb].file_name not in files:
                                files[ssb[global_script.script_struct.hanger_ssb].file_name] = []
                            files[ssb[global_script.script_struct.hanger_ssb].file_name].append((
                                SsbRoutineType.GENERIC, 0, global_script.script_struct.current_opcode_addr_relative
                            ))
                    except IndexError:
                        pass
                    for i, actor in enumerate(actors):
                        try:
                            if actor is not None and actor.script_struct.hanger_ssb > -1:
                                if ssb[actor.script_struct.hanger_ssb]:
                                    if ssb[actor.script_struct.hanger_ssb].file_name not in files:
                                        files[ssb[actor.script_struct.hanger_ssb].file_name] = []
                                    files[ssb[actor.script_struct.hanger_ssb].file_name].append((
                                        SsbRoutineType.ACTOR, i, actor.script_struct.current_opcode_addr_relative
                                    ))
                        except IndexError:
                            pass
                    for i, object in enumerate(objects):
                        try:
                            if object is not None and object.script_struct.hanger_ssb > -1:
                                if ssb[object.script_struct.hanger_ssb]:
                                    if ssb[object.script_struct.hanger_ssb].file_name not in files:
                                        files[ssb[object.script_struct.hanger_ssb].file_name] = []
                                    files[ssb[object.script_struct.hanger_ssb].file_name].append((
                                        SsbRoutineType.OBJECT, i, object.script_struct.current_opcode_addr_relative
                                    ))
                        except IndexError:
                            pass
                    for i, performer in enumerate(performers):
                        try:
                            if performer is not None and performer.script_struct.hanger_ssb > -1:
                                if ssb[performer.script_struct.hanger_ssb]:
                                    if ssb[performer.script_struct.hanger_ssb].file_name not in files:
                                        files[ssb[performer.script_struct.hanger_ssb].file_name] = []
                                    files[ssb[performer.script_struct.hanger_ssb].file_name].append((
                                        SsbRoutineType.PERFORMER, i, performer.script_struct.current_opcode_addr_relative
                                    ))
                        except IndexError:
                            pass
                    code_editor.insert_hanger_halt_lines(files)

                # File tree store
                self._files__tree_store.clear()
                if ssb[0]:
                    self._files__tree_store.append(None, [
                        'skytemple-e-script-symbolic', self.short_fname(ssb[0].file_name), GE_FILE_STORE_SCRIPT, _('0 (Global)')
                    ])
                else:
                    self._files__tree_store.append(None, [
                        'skytemple-action-unavailable-symbolic', _('<Empty>'), '', _('0 (Global)')
                    ])
                for i in range(1, 4):
                    # Build the three main hanger slots
                    hanger_str = _('1 (Enter)')
                    type_str = 'SSE'
                    if i == 2:
                        hanger_str = _('2 (Sub)')
                        type_str = 'SSS'
                    elif i == 3:
                        hanger_str = _('3 (Acting)')
                        type_str = 'SSA'

                    if ssx[i]:
                        # Slot is filled
                        ssx_root = self._files__tree_store.append(None, [
                            'skytemple-e-ground-symbolic', self.short_fname(ssx[i].file_name), type_str, hanger_str
                        ])
                    else:
                        # Slot is not filled
                        ssx_root = self._files__tree_store.append(None, [
                            'skytemple-action-unavailable-symbolic', _('<Empty>'), '', hanger_str
                        ])

                    if ssb[i]:
                        # SSB Slot for this is filled
                        self._files__tree_store.append(ssx_root, [
                            'skytemple-e-script-symbolic', self.short_fname(ssb[i].file_name), GE_FILE_STORE_SCRIPT, hanger_str
                        ])
                    if ssb[i + TALK_HANGER_OFFSET]:
                        # SSB Talk slot for this is filled
                        self._files__tree_store.append(ssx_root, [
                            'skytemple-e-script-symbolic', self.short_fname(ssb[i+TALK_HANGER_OFFSET].file_name), GE_FILE_STORE_SCRIPT, f'{i + TALK_HANGER_OFFSET} (Talk)'
                        ])

                # Entities store
                self._entities__tree_store.clear()
                breaked = False
                try:
                    if global_script.script_struct.hanger_ssb > -1 and ssb[global_script.script_struct.hanger_ssb] is not None:
                        breaked = ssb[global_script.script_struct.hanger_ssb].breaked and global_script.script_struct == breaked_for
                except (IndexError, AttributeError):
                    pass
                self._entities__tree_store.append(None, [
                    _('<Global>'), '0', '',
                    self.get_short_sname(ssb, breaked, global_script.script_struct.hanger_ssb), None, '',
                    'skytemple-media-playback-pause-symbolic' if breaked else '', ICON_GLOBAL_SCRIPT, '', '', SsbRoutineType.GENERIC.value
                ])
                actors_node = self._entities__tree_store.append(None, [
                    _('Actors'), '', '', '', None, '', '', ICON_ACTOR, '', '', -1
                ])
                for actor in actors:
                    breaked = False
                    try:
                        if actor.script_struct.hanger_ssb > -1:
                            breaked = ssb[actor.script_struct.hanger_ssb].breaked and actor.script_struct == breaked_for
                    except (IndexError, AttributeError):
                        pass
                    self._entities__tree_store.append(actors_node, [
                        f'{actor.id}', f'{actor.hanger}', f'{actor.sector}',
                        self.get_short_sname(ssb, breaked, actor.script_struct.hanger_ssb), None, f'{actor.kind.name}',
                        'skytemple-media-playback-pause-symbolic' if breaked else '', '',
                        f'{actor.x_map}', f'{actor.y_map}', SsbRoutineType.ACTOR.value
                    ])
                objects_node = self._entities__tree_store.append(None, [
                    _('Objects'), '', '', '', None, '', '', ICON_OBJECT, '', '', -1
                ])
                for object in objects:
                    kind_name = object.kind.name
                    if kind_name == 'NULL':
                        kind_name = f'{object.kind.name} ({object.kind.id})'
                    breaked = False
                    try:
                        if object.script_struct.hanger_ssb > -1:
                            breaked = ssb[object.script_struct.hanger_ssb].breaked and object.script_struct == breaked_for
                    except (IndexError, AttributeError):
                        pass
                    self._entities__tree_store.append(objects_node, [
                        f'{object.id}', f'{object.hanger}', f'{object.sector}',
                        self.get_short_sname(ssb, breaked, object.script_struct.hanger_ssb), None, kind_name,
                        'skytemple-media-playback-pause-symbolic' if breaked else '', '',
                        f'{object.x_map}', f'{object.y_map}', SsbRoutineType.OBJECT.value
                    ])
                performers_node = self._entities__tree_store.append(None, [
                    _('Performers'), '', '', '', None, '', '', ICON_PERFORMER, '', '', -1
                ])
                for performer in performers:
                    breaked = False
                    try:
                        if performer.script_struct.hanger_ssb > -1:
                            breaked = ssb[performer.script_struct.hanger_ssb].breaked and performer.script_struct == breaked_for
                    except (IndexError, AttributeError):
                        pass
                    self._entities__tree_store.append(performers_node, [
                        f'{performer.id}', f'{performer.hanger}', f'{performer.sector}',
                        self.get_short_sname(ssb, breaked, performer.script_struct.hanger_ssb), None, f'{performer.kind}',
                        'skytemple-media-playback-pause-symbolic' if breaked else '', '',
                        f'{performer.x_map}', f'{performer.y_map}', SsbRoutineType.PERFORMER.value
                    ])
                events_node = self._entities__tree_store.append(None, [
                    _('Triggers'), '', '', '', None, '', '', ICON_EVENTS, '', '', -1
                ])
                for event in events:
                    self._entities__tree_store.append(events_node, [
                        f'{event.id}', f'{event.hanger}', f'{event.sector}',
                        '', None, f'{event.kind}', '', '', '', '', -1
                    ])

                pos_marks_node = self._entities__tree_store.append(None, [
                    _('Pos. Marks'), '', '', '', None, '', '', ICON_POSITION_MARKER, '', '', -1  # TRANSLATORS: Position Marks
                ])
                for ssb in ground_state.loaded_ssb_files:
                    if ssb is not None:
                        for mark in ground_state.ssb_file_manager.get(ssb.file_name).position_markers:
                            self._entities__tree_store.append(pos_marks_node, [
                                f'{mark.name}', '', '',
                                ssb.file_name.split('/')[-1], None,
                                '', '', '',
                                f'{mark.x_with_offset}', f'{mark.y_with_offset}', -1
                            ])

                self._files__tree.expand_all()
                self._entities__tree.expand_all()

    @staticmethod
    def short_fname(file_name):
        return file_name.replace('SCRIPT/', '')

    @staticmethod
    def get_short_sname(ssbs, breaked, hanger):
        """
        Returns the short ssb file name for display in the script column.
        If breaked and the ssb file in RAM has a breakpoint handling file currently registered, that
        is different from it's file name, then this file's name is also returned in parenthesis.
        """
        try:
            if ssbs[hanger]:
                extra = ''
                if breaked and ssbs[hanger].breaked and ssbs[hanger].breaked__handler_file != ssbs[hanger].file_name:
                    extra = f' ({ssbs[hanger].breaked__handler_file.split(os.path.sep)[-1]})'
                return ssbs[hanger].file_name.split('/')[-1] + extra
            return ''
        except IndexError:
            return ''
