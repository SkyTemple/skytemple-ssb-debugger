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
from typing import Optional
import gi
from gi.repository.Gtk import TreeViewColumn

from skytemple_ssb_debugger.model.ground_engine_state import TALK_HANGER_OFFSET

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

        self._files__tree: Gtk.TreeView = builder.get_object('ground_state_files_tree')
        icon = Gtk.CellRendererPixbuf()
        path = Gtk.CellRendererText()
        column = TreeViewColumn("Path")
        column.pack_start(icon, True)
        column.pack_start(path, True)
        column.add_attribute(icon, "icon_name", 0)
        column.add_attribute(path, "text", 1)
        self._files__tree.append_column(resizable(column))
        self._files__tree.append_column(resizable(TreeViewColumn("Hanger", Gtk.CellRendererText(), text=3)))
        self._files__tree.append_column(resizable(TreeViewColumn("Type", Gtk.CellRendererText(), text=2)))

        self._entities__tree: Gtk.TreeView = builder.get_object('ground_state_entities_tree')
        #self._files__tree.append_column(resizable(TreeViewColumn("Preview", Gtk.CellRendererPixbuf(), xxx=4)))
        self._entities__tree.append_column(resizable(TreeViewColumn("ID", Gtk.CellRendererText(), text=0)))
        self._entities__tree.append_column(resizable(TreeViewColumn("Kind", Gtk.CellRendererText(), text=5)))
        self._entities__tree.append_column(resizable(TreeViewColumn("Hanger", Gtk.CellRendererText(), text=1)))
        self._entities__tree.append_column(resizable(TreeViewColumn("Sector", Gtk.CellRendererText(), text=2)))
        self._entities__tree.append_column(resizable(TreeViewColumn("Script", Gtk.CellRendererText(), text=3)))

        self._files__tree_store: Gtk.TreeStore = builder.get_object('ground_state_files_tree_store')
        self._entities__tree_store: Gtk.TreeStore = builder.get_object('ground_state_entities_store')

    def sync(self):
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
                # Is running
                global_script, ssb, ssx, actors, objects, performers, events = ground_state.collect()

                # File tree store
                self._files__tree_store.clear()
                if ssb[0]:
                    self._files__tree_store.append(None, [
                        'text-plain', self.short_fname(ssb[0].file_name), 'Script', '0 (Global)'
                    ])
                else:
                    self._files__tree_store.append(None, [
                        'image-missing', '<Empty>', '', '0 (Global)'
                    ])
                for i in range(1, 4):
                    # Build the three main hanger slots
                    hanger_str = '1 (Enter)'
                    type_str = 'SSE'
                    if i == 2:
                        hanger_str = '2 (Sub)'
                        type_str = 'SSS'
                    elif i == 3:
                        hanger_str = '3 (Acting)'
                        type_str = 'SSA'

                    if ssx[i]:
                        # Slot is filled
                        ssx_root = self._files__tree_store.append(None, [
                            'image', self.short_fname(ssx[i].file_name), type_str, hanger_str
                        ])
                    else:
                        # Slot is not filled
                        ssx_root = self._files__tree_store.append(None, [
                            'image-missing', '<Empty>', '', hanger_str
                        ])

                    if ssb[i]:
                        # SSB Slot for this is filled
                        self._files__tree_store.append(ssx_root, [
                            'text-plain', self.short_fname(ssb[i].file_name), 'Script', hanger_str
                        ])
                    if ssb[i + TALK_HANGER_OFFSET]:
                        # SSB Talk slot for this is filled
                        self._files__tree_store.append(ssx_root, [
                            'text-plain', self.short_fname(ssb[i+TALK_HANGER_OFFSET].file_name), 'Script', f'{i+TALK_HANGER_OFFSET} (Talk)'
                        ])

                # Entities store
                self._entities__tree_store.clear()
                self._entities__tree_store.append(None, [
                    '<Global>', '0', '',
                    self.get_short_sname(ssb, global_script.current_script_hanger), None, ''
                ])
                actors_node = self._entities__tree_store.append(None, [
                    'Actors', '', '', '', None, ''
                ])
                for actor in actors:
                    self._entities__tree_store.append(actors_node, [
                        f'{actor.id}', f'{actor.hanger}', f'{actor.sector}',
                        self.get_short_sname(ssb, actor.current_script_hanger), None, f'{actor.kind.name}'
                    ])
                objects_node = self._entities__tree_store.append(None, [
                    'Objects', '', '', '', None, ''
                ])
                for object in objects:
                    kind_name = object.kind.name
                    if kind_name == 'NULL':
                        kind_name = f'{object.kind.name} ({object.kind.id})'
                    self._entities__tree_store.append(objects_node, [
                        f'{object.id}', f'{object.hanger}', f'{object.sector}',
                        self.get_short_sname(ssb, object.current_script_hanger), None, kind_name
                    ])
                performers_node = self._entities__tree_store.append(None, [
                    'Performers', '', '', '', None, ''
                ])
                for performer in performers:
                    self._entities__tree_store.append(performers_node, [
                        f'{performer.id}', f'{performer.hanger}', f'{performer.sector}',
                        self.get_short_sname(ssb, performer.current_script_hanger), None, f'{performer.kind}'
                    ])
                events_node = self._entities__tree_store.append(None, [
                    'Events', '', '', '', None, ''
                ])
                for event in events:
                    self._entities__tree_store.append(events_node, [
                        f'{event.id}', f'{event.hanger}', f'{event.sector}',
                        '', None, f'{event.kind}'
                    ])

                pos_marks_node = self._entities__tree_store.append(None, [
                    'Position Markers', '', '', '', None, ''
                ])
                # TODO

                self._files__tree.expand_all()
                self._entities__tree.expand_all()

    @staticmethod
    def short_fname(file_name):
        return file_name.replace('SCRIPT/', '')

    @staticmethod
    def get_short_sname(ssbs, hanger):
        try:
            if ssbs[hanger]:
                return ssbs[hanger].file_name.split('/')[-1]
            return ''
        except IndexError:
            return ''
