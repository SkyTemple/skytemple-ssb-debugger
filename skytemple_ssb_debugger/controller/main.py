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
import os
import shutil
import traceback
from functools import partial
from typing import Optional

import cairo
import gi
from ndspy.rom import NintendoDSRom

from desmume.controls import Keys, keymask, load_configured_config
from desmume.emulator import SCREEN_WIDTH, SCREEN_HEIGHT
from explorerscript import EXPLORERSCRIPT_EXT
from explorerscript.ssb_converting.ssb_data_types import SsbRoutineType
from skytemple_files.common.config.path import skytemple_config_dir
from skytemple_files.common.project_file_manager import ProjectFileManager
from skytemple_files.common.script_util import load_script_files, SCRIPT_DIR
from skytemple_files.common.util import get_rom_folder, get_ppmdu_config_for_rom
from skytemple_ssb_debugger.controller.editor_notebook import EditorNotebookController
from skytemple_ssb_debugger.controller.debug_overlay import DebugOverlayController
from skytemple_ssb_debugger.controller.debugger import DebuggerController
from skytemple_ssb_debugger.controller.ground_state import GroundStateController, GE_FILE_STORE_SCRIPT
from skytemple_ssb_debugger.controller.local_variable import LocalVariableController
from skytemple_ssb_debugger.controller.variable import VariableController
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.model.breakpoint_manager import BreakpointManager
from skytemple_ssb_debugger.model.breakpoint_state import BreakpointState, BreakpointStateType
from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct
from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager
from skytemple_ssb_debugger.renderer.async_software import AsyncSoftwareRenderer
from skytemple_ssb_debugger.threadsafe import threadsafe_emu, threadsafe_emu_nonblocking, threadsafe_gtk_nonblocking

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gdk, GLib
from gi.repository.Gtk import *


SAVESTATE_EXT_DESUME = 'ds'
SAVESTATE_EXT_GROUND_ENGINE = 'ge.json'
PROJECT_DIR_SUBDIR_NAME = 'debugger'
PROJECT_DIR_MACRO_NAME = 'Macros'


class MainController:
    def __init__(self, builder: Builder, window: Window):
        self.builder = builder
        self.window = window
        self.emu_thread: Optional[EmulatorThread] = None
        self.rom: Optional[NintendoDSRom] = None
        self.ssb_fm: Optional[SsbFileManager] = None
        self.breakpoint_manager: Optional[BreakpointManager] = None
        self.rom_filename = None
        self._emu_is_running = False

        self.debugger: Optional[DebuggerController] = None
        self.debug_overlay: Optional[DebugOverlayController] = None
        self.breakpoint_state: Optional[BreakpointState] = None

        self.config_dir = os.path.join(skytemple_config_dir(), 'debugger')
        os.makedirs(self.config_dir, exist_ok=True)

        self.project_fm: Optional[ProjectFileManager] = None

        self._click = False
        self._debug_log_scroll_to_bottom = False
        self._suppress_event = False
        self._stopped = False

        self._search_text = None
        self._ssb_item_filter = None

        self._log_stdout_io_source = None

        self._current_screen_width = SCREEN_WIDTH
        self._current_screen_height = SCREEN_HEIGHT

        self._filter_nds = Gtk.FileFilter()
        self._filter_nds.set_name("Nintendo DS ROMs (*.nds)")
        self._filter_nds.add_pattern("*.nds")

        self._filter_gba_ds = Gtk.FileFilter()
        self._filter_gba_ds.set_name("Nintendo DS ROMs with binary loader (*.ds.gba)")
        self._filter_gba_ds.add_pattern("*.nds")

        self._filter_any = Gtk.FileFilter()
        self._filter_any.set_name("All files")
        self._filter_any.add_pattern("*")

        self.main_draw = builder.get_object("draw_main")
        self.main_draw.set_events(Gdk.EventMask.ALL_EVENTS_MASK)
        self.main_draw.show()
        self.sub_draw = builder.get_object("draw_sub")
        self.sub_draw.set_events(Gdk.EventMask.ALL_EVENTS_MASK)
        self.sub_draw.show()

        self.renderer = None
        self.init_emulator()

        if self.emu_thread:

            self.debugger = DebuggerController(self.emu_thread, self._debugger_print_callback, self)

            self.debug_overlay = DebugOverlayController(self.debugger)
            self.renderer = AsyncSoftwareRenderer(self.emu_thread, self.main_draw, self.sub_draw, self.debug_overlay.draw)
            self.renderer.init()
            self.renderer.start()

            self._keyboard_cfg, self._joystick_cfg = threadsafe_emu(
                self.emu_thread, lambda: load_configured_config(self.emu_thread.emu)
            )
            self._keyboard_tmp = self._keyboard_cfg

        self.editor_notebook: EditorNotebookController = EditorNotebookController(self.builder, self, self.window)
        self.variable_controller: VariableController = VariableController(self.emu_thread, self.builder)
        self.local_variable_controller: LocalVariableController = LocalVariableController(self.emu_thread, self.builder, self.debugger)
        self.ground_state_controller = GroundStateController(self.emu_thread, self.debugger, self.builder)

        # Load more initial settings
        self.on_debug_log_cntrl_ops_toggled(builder.get_object('debug_log_cntrl_ops'))
        self.on_debug_log_cntrl_script_toggled(builder.get_object('debug_log_cntrl_script'))
        self.on_debug_log_cntrl_internal_toggled(builder.get_object('debug_log_cntrl_internal'))
        self.on_debug_log_cntrl_ground_state_toggled(builder.get_object('debug_log_cntrl_ground_state'))
        self.on_debug_settings_debug_mode_toggled(builder.get_object('debug_settings_debug_mode'))
        self.on_debug_settings_overlay_toggled(builder.get_object('debug_settings_overlay'))
        self.on_emulator_controls_volume_toggled(builder.get_object('emulator_controls_volume'))
        self.on_debug_log_scroll_to_bottom_toggled(builder.get_object('debug_log_scroll_to_bottom'))

        # Trees / Lists
        ssb_file_tree: TreeView = self.builder.get_object('ssb_file_tree')
        column_main = TreeViewColumn("Name", Gtk.CellRendererText(), text=1)
        ssb_file_tree.append_column(column_main)

        # Other gtk stuff
        self._debug_log_textview_right_marker = self.builder.get_object('debug_log_textview').get_buffer().create_mark(
            'end', self.builder.get_object('debug_log_textview').get_buffer().get_end_iter(), False
        )

        # Initial sizes
        self.builder.get_object('frame_debug_log').set_size_request(220, -1)

        builder.connect_signals(self)

        # DEBUG
        self.open_rom('/home/marco/austausch/dev/skytemple/skyworkcopy_edit.nds')

    @property
    def emu_is_running(self):
        """
        Keeps track of whether the emulator is running or not, via self._emu_is_running.
        Always returns false, if a breakpoint_state is active and breaking.
        """
        if self.breakpoint_state and self.breakpoint_state.is_stopped():
            return False
        return self._emu_is_running

    @emu_is_running.setter
    def emu_is_running(self, value):
        self._emu_is_running = value

    def init_emulator(self):
        try:
            # Load desmume
            # TODO: Dummy
            #self.emu_thread = EmulatorThread(self, "C:\\Users\\Marco\\austausch\\dev\\desmume\\desmume\\src\\frontend\\interface\\windows\\__bins\\DeSmuME Interface-VS2017-x64-Release.dll")
            self.emu_thread = EmulatorThread(self, "../../../desmume/desmume/src/frontend/interface/.libs/libdesmume.so")
            self.emu_thread.start()

            # Init joysticks
            threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.input.joy_init())
        except BaseException as ex:
            print("DeSmuME load error:")
            print(''.join(traceback.format_exception(etype=type(ex), value=ex, tb=ex.__traceback__)))

            self.emu_thread = None
            md = Gtk.MessageDialog(self.window,
                                   Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                                   Gtk.ButtonsType.OK, f"DeSmuME couldn't be loaded. "
                                                       f"Debugging functionality will not be available:\n\n"
                                                       f"{ex}",
                                   title="Error loading the emulator!")
            md.set_position(Gtk.WindowPosition.CENTER)
            md.run()
            md.destroy()
            return

    def on_main_window_delete_event(self, *args):
        if not self.editor_notebook.close_all_tabs():
            return True
        self.gtk_main_quit()
        return False

    def on_main_window_destroy(self, *args):
        self.gtk_main_quit()

    def gtk_main_quit(self, *args):
        if self.breakpoint_state:
            self.breakpoint_state.fail_hard()
        if self.emu_thread:
            self.emu_thread.stop()
        Gtk.main_quit()

    def gtk_widget_hide_on_delete(self, w: Gtk.Widget, *args):
        w.hide_on_delete()
        return True

    def gtk_widget_hide(self, w: Gtk.Widget, *args):
        w.hide()

    # EMULATOR
    def on_draw_aspect_frame_size_allocate(self, widget: Gtk.AspectFrame, *args):
        scale = widget.get_child().get_allocated_width() / SCREEN_WIDTH
        if self.renderer:
            self.renderer.set_scale(scale)
        self._current_screen_height = SCREEN_HEIGHT * scale
        self._current_screen_width = SCREEN_WIDTH * scale

    def on_main_window_key_press_event(self, widget: Gtk.Widget, event: Gdk.EventKey, *args):
        if self.emu_thread:
            # Don't enable controls when in any entry or text view
            if isinstance(self.window.get_focus(), Gtk.Entry) or isinstance(self.window.get_focus(), Gtk.TextView):
                return False
            key = self.lookup_key(event.keyval)
            # shift,ctrl, both alts
            mask = Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK | Gdk.ModifierType.MOD5_MASK
            if event.state & mask == 0:
                if key and self.emu_is_running:
                    threadsafe_emu_nonblocking(self.emu_thread, lambda: self.emu_thread.emu.input.keypad_add_key(key))
                    return True
            return False

    def on_main_window_key_release_event(self, widget: Gtk.Widget, event: Gdk.EventKey, *args):
        if self.emu_thread:
            key = self.lookup_key(event.keyval)
            if key and self.emu_is_running:
                threadsafe_emu_nonblocking(self.emu_thread, lambda: self.emu_thread.emu.input.keypad_rm_key(key))

    def on_draw_main_draw(self, widget: Gtk.DrawingArea, ctx: cairo.Context, *args):
        if self.renderer:
            return self.renderer.screen(self._current_screen_width, self._current_screen_height, ctx, 0)

    def on_draw_main_configure_event(self, widget: Gtk.DrawingArea, *args):
        if self.renderer:
            self.renderer.reshape(widget, 0)
        return True

    def on_draw_sub_draw(self, widget: Gtk.DrawingArea, ctx: cairo.Context, *args):
        if self.renderer:
            return self.renderer.screen(self._current_screen_width, self._current_screen_height, ctx, 1)

    def on_draw_sub_configure_event(self, widget: Gtk.DrawingArea, *args):
        if self.renderer:
            self.renderer.reshape(widget, 1)
        return True

    def on_draw_main_motion_notify_event(self, widget: Gtk.Widget, event: Gdk.EventMotion, *args):
        return self.on_draw_motion_notify_event(widget, event, 0)

    def on_draw_main_button_release_event(self, widget: Gtk.Widget, event: Gdk.EventButton, *args):
        return self.on_draw_button_release_event(widget, event, 0)

    def on_draw_main_button_press_event(self, widget: Gtk.Widget, event: Gdk.EventButton, *args):
        return self.on_draw_button_press_event(widget, event, 0)

    def on_draw_sub_motion_notify_event(self, widget: Gtk.Widget, event: Gdk.EventMotion, *args):
        return self.on_draw_motion_notify_event(widget, event, 1)

    def on_draw_sub_button_release_event(self, widget: Gtk.Widget, event: Gdk.EventButton, *args):
        return self.on_draw_button_release_event(widget, event, 1)

    def on_draw_sub_button_press_event(self, widget: Gtk.Widget, event: Gdk.EventButton, *args):
        return self.on_draw_button_press_event(widget, event, 1)

    def on_draw_motion_notify_event(self, widget: Gtk.Widget, event: Gdk.EventMotion, display_id: int):
        if self.emu_thread:
            if display_id == 1 and self._click:
                if event.is_hint:
                    _, x, y, state = widget.get_window().get_pointer()
                else:
                    x = event.x
                    y = event.y
                    state = event.state
                if state & Gdk.ModifierType.BUTTON1_MASK:
                    self.set_touch_pos(x, y)

    def on_draw_button_release_event(self, widget: Gtk.Widget, event: Gdk.EventButton, display_id: int):
        if self.emu_thread:
            if display_id == 1 and self._click:
                self._click = False
                threadsafe_emu_nonblocking(self.emu_thread, lambda: self.emu_thread.emu.input.touch_release())
            return True

    def on_draw_button_press_event(self, widget: Gtk.Widget, event: Gdk.EventButton, display_id: int):
        widget.grab_focus()
        if self.emu_thread:
            if event.button == 1:
                if display_id == 1 and self.emu_is_running:
                    self._click = True
                    _, x, y, state = widget.get_window().get_pointer()
                    if state & Gdk.ModifierType.BUTTON1_MASK:
                        self.set_touch_pos(x, y)
            return True

    def on_right_event_box_button_press_event(self, widget: Gtk.Widget, *args):
        """If the right area of the window is pressed, focus it, to disable any entry/textview focus."""
        widget.grab_focus()
        return False

    # MENU FILE
    def on_menu_open_activate(self, *args):
        if self.emu_thread:
            threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.pause())

        response, fn = self._file_chooser(Gtk.FileChooserAction.OPEN, "Open...", (self._filter_nds, self._filter_gba_ds, self._filter_any))

        if response == Gtk.ResponseType.OK:
            self.open_rom(fn)

    def on_menu_save_activate(self, menu_item: Gtk.MenuItem, *args):
        if self.editor_notebook and self.editor_notebook.currently_open:
            self.editor_notebook.currently_open.save()

    def on_menu_save_all_activate(self, menu_item: Gtk.MenuItem, *args):
        pass  # todo

    def on_menu_quit_activate(self, menu_item: Gtk.MenuItem, *args):
        self.gtk_main_quit()

    # EMULATOR CONTROLS
    def on_emulator_controls_playstop_clicked(self, button: Gtk.Button):
        if self.emu_thread:
            if not self._stopped:
                self.emu_stop()
            else:
                if not self.variable_controller.variables_changed_but_not_saved or self._warn_about_unsaved_vars():
                    self.emu_reset()
                    self.emu_resume()

    def on_emulator_controls_pause_clicked(self, button: Gtk.Button):
        if self.emu_thread:
            if self.emu_is_running and self.emu_thread.registered_main_loop:
                self.emu_pause()
            elif not self._stopped:
                self.emu_resume()

    def on_emulator_controls_reset_clicked(self, button: Gtk.Button):
        if self.emu_thread:
            self.emu_reset()
            self.emu_resume()

    def on_emulator_controls_volume_toggled(self, button: Gtk.ToggleButton):
        if self.emu_thread:
            if button.get_active():
                threadsafe_emu_nonblocking(self.emu_thread, lambda: self.emu_thread.emu.volume_set(100))
            else:
                threadsafe_emu_nonblocking(self.emu_thread, lambda: self.emu_thread.emu.volume_set(0))

    def on_emulator_controls_savestate1_clicked(self, button: Gtk.Button):
        if self.emu_thread:
            self.savestate(1)

    def on_emulator_controls_savestate2_clicked(self, button: Gtk.Button):
        if self.emu_thread:
            self.savestate(2)

    def on_emulator_controls_savestate3_clicked(self, button: Gtk.Button):
        if self.emu_thread:
            self.savestate(3)

    def on_emulator_controls_loadstate1_clicked(self, button: Gtk.Button):
        if self.emu_thread:
            self.loadstate(1)

    def on_emulator_controls_loadstate2_clicked(self, button: Gtk.Button):
        if self.emu_thread:
            self.loadstate(2)

    def on_emulator_controls_loadstate3_clicked(self, button: Gtk.Button):
        if self.emu_thread:
            self.loadstate(3)

    # OPTION TOGGLES
    def on_debug_log_cntrl_ops_toggled(self, btn: Gtk.Widget):
        if self.debugger:
            self.debugger.log_operations(btn.get_active())

    def on_debug_log_cntrl_script_toggled(self, btn: Gtk.Widget):
        if self.debugger:
            self.debugger.log_debug_print(btn.get_active())

    def on_debug_log_cntrl_internal_toggled(self, btn: Gtk.Widget):
        if self.debugger:
            self.debugger.log_printfs(btn.get_active())

    def on_debug_log_cntrl_ground_state_toggled(self, btn: Gtk.Widget):
        if self.debugger:
            self.debugger.log_ground_engine_state(btn.get_active())

    def on_debug_settings_debug_mode_toggled(self, btn: Gtk.Widget):
        if self.debugger:
            self.debugger.debug_mode(btn.get_active())

    def on_debug_settings_overlay_toggled(self, btn: Gtk.Widget):
        if self.debug_overlay:
            self.debug_overlay.toggle(btn.get_active())

    def on_debug_log_scroll_to_bottom_toggled(self, btn: Gtk.ToggleButton):
        self._debug_log_scroll_to_bottom = btn.get_active()

    def on_debug_log_clear_clicked(self, btn: Gtk.Button):
        buff: Gtk.TextBuffer = self.builder.get_object('debug_log_textview').get_buffer()
        buff.delete(buff.get_start_iter(), buff.get_end_iter())

    # FILE TREE

    def on_ssb_file_search_search_changed(self, search: Gtk.SearchEntry):
        """Filter the main item view using the search field"""
        self._search_text = search.get_text()
        self._ssb_item_filter.refilter()

    def on_ssb_file_tree_button_press_event(self, tree: Gtk.TreeView, event: Gdk.Event):
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            model, treeiter = tree.get_selection().get_selected()
            if treeiter is not None and model is not None:
                if model[treeiter][0] == '':
                    tree.expand_row(model[treeiter].path, False)
                elif model[treeiter][2] == 'ssb':
                    self.editor_notebook.open_ssb(SCRIPT_DIR + '/' + model[treeiter][0])
                elif model[treeiter][2] == 'exps_macro':
                    short_path = model[treeiter][0].replace(self.project_fm.dir() + os.path.sep, '')
                    self.editor_notebook.open_exps_macro(
                        model[treeiter][0], short_path
                    )
                else:
                    tree.expand_row(model.get_path(treeiter), False)
        elif event.type == Gdk.EventType.BUTTON_PRESS and event.button == Gdk.BUTTON_SECONDARY:
            # Right click!
            model = self.builder.get_object('ssb_file_tree_store')
            treepath = tree.get_path_at_pos(int(event.x), int(event.y))[0]
            if treepath is not None:
                if model[treepath][2] == 'exps_macro_dir':
                    menu: Gtk.Menu = Gtk.Menu.new()
                    create_dir: Gtk.MenuItem = Gtk.MenuItem.new_with_label("Create directory...")
                    create_dir.connect('activate', partial(self.on_ssb_file_tree__menu_create_macro_dir, model, treepath))
                    create_file: Gtk.MenuItem = Gtk.MenuItem.new_with_label("Create new script file...")
                    create_file.connect('activate', partial(self.on_ssb_file_tree__menu_create_macro_file, model, treepath))
                    menu.attach_to_widget(tree, None)
                    menu.add(create_dir)
                    menu.add(create_file)
                    if model[treepath][1] != 'Macros':
                        # prevent main dir from being deleted
                        # todo: this is a bit lazy and obviously flawed...
                        delete_dir: Gtk.MenuItem = Gtk.MenuItem.new_with_label("Delete directory...")
                        delete_dir.connect('activate', partial(self.on_ssb_file_tree__menu_delete_dir, model, treepath))
                        menu.add(Gtk.SeparatorMenuItem.new())
                        menu.add(delete_dir)
                    menu.show_all()
                    menu.popup_at_pointer(event)
                elif model[treepath][2] == 'exps_macro':
                    menu: Gtk.Menu = Gtk.Menu.new()
                    delete_file: Gtk.MenuItem = Gtk.MenuItem.new_with_label("Delete script file...")
                    delete_file.connect('activate', partial(self.on_ssb_file_tree__menu_delete_file, model, treepath))
                    menu.attach_to_widget(tree, None)
                    menu.add(delete_file)
                    menu.show_all()
                    menu.popup_at_pointer(event)

    def on_ssb_file_tree__menu_create_macro_dir(self, store: Gtk.TreeStore, treepath: Gtk.TreePath, *args):
        row = store[treepath]
        response, dirname = self._show_generic_input('Name of the directory:', 'Create Directory')
        if response == Gtk.ResponseType.OK:
            abs_dirname = row[0] + os.path.sep + dirname
            os.makedirs(abs_dirname, exist_ok=True)
            store.append(store.get_iter(treepath), [abs_dirname, dirname, 'exps_macro_dir'])

    def on_ssb_file_tree__menu_create_macro_file(self, store: Gtk.TreeStore, treepath: Gtk.TreePath, *args):
        row = store[treepath]
        response, filename = self._show_generic_input('Name of the new script file:', 'Create File')
        if len(filename) < 5 or filename[-5:] != EXPLORERSCRIPT_EXT:
            filename += EXPLORERSCRIPT_EXT
        if response == Gtk.ResponseType.OK:
            abs_filename = row[0] + os.path.sep + filename
            os.makedirs(row[0], exist_ok=True)
            with open(abs_filename, 'w') as f:
                f.write('')
            store.append(store.get_iter(treepath), [abs_filename, filename, 'exps_macro'])

    def on_ssb_file_tree__menu_delete_dir(self, model: Gtk.TreeModel, treepath: Gtk.TreePath, *args):
        row = model[treepath]
        response = self._show_are_you_sure_delete(f"Do you want to delete the directory "
                                                  f"{row[1]} with all of it's contents?")
        if response == Gtk.ResponseType.DELETE_EVENT:
            shutil.rmtree(row[0])
            del model[treepath]

    def on_ssb_file_tree__menu_delete_file(self, model, treepath, *args):
        row = model[treepath]
        response = self._show_are_you_sure_delete(f"Do you want to delete the script file "
                                                  f"{row[1]}?")
        if response == Gtk.ResponseType.DELETE_EVENT:
            os.remove(row[0])
            del model[treepath]

    def init_file_tree(self):
        ssb_file_tree_store: Gtk.TreeStore = self.builder.get_object('ssb_file_tree_store')
        ssb_file_tree_store.clear()

        if not self._ssb_item_filter:
            self._ssb_item_filter = ssb_file_tree_store.filter_new()
            self.builder.get_object('ssb_file_tree').set_model(self._ssb_item_filter)
            self._ssb_item_filter.set_visible_func(self._ssb_item_filter_visible_func)

        self._set_sensitve('ssb_file_search', True)

        script_files = load_script_files(get_rom_folder(self.rom, SCRIPT_DIR))

        # EXPLORERSCRIPT MACROS
        #    -> Macros
        macros_dir_name = self.project_fm.dir(PROJECT_DIR_MACRO_NAME)
        macros_tree_nodes = {macros_dir_name: ssb_file_tree_store.append(None, [macros_dir_name, 'Macros', 'exps_macro_dir'])}
        for root, dnames, fnames in os.walk(macros_dir_name):
            root_node = macros_tree_nodes[root]
            for dirname in dnames:
                macros_tree_nodes[root + os.path.sep + dirname] = ssb_file_tree_store.append(
                    root_node, [root + os.path.sep + dirname, dirname, 'exps_macro_dir']
                )
            for filename in fnames:
                if len(filename) > 4 and filename[-5:] == EXPLORERSCRIPT_EXT:
                    ssb_file_tree_store.append(root_node, [root + os.path.sep + filename, filename, 'exps_macro'])

        # SSB SCRIPT FILES
        #    -> Common [common]
        common_root = ssb_file_tree_store.append(None, ['', 'Common', ''])
        #       -> Master Script (unionall) [ssb]
        #       -> (others) [ssb]
        for name in script_files['common']:
            ssb_file_tree_store.append(common_root, ['COMMON/' + name, name, 'ssb'])

        for i, map_obj in enumerate(script_files['maps'].values()):
            #    -> (Map Name) [map]
            map_root = ssb_file_tree_store.append(None, ['', map_obj['name'], ''])

            enter_root = ssb_file_tree_store.append(map_root, ['', 'Enter (sse)', ''])
            if map_obj['enter_sse'] is not None:
                #          -> Script X [ssb]
                for ssb in map_obj['enter_ssbs']:
                    ssb_file_tree_store.append(enter_root, [f"{map_obj['name']}/{ssb}", ssb, 'ssb'])

            #       -> Acting Scripts [lsd]
            acting_root = ssb_file_tree_store.append(map_root, ['', 'Acting (ssa)', ''])
            for _, ssb in map_obj['ssas']:
                #             -> Script [ssb]
                ssb_file_tree_store.append(acting_root, [f"{map_obj['name']}/{ssb}", ssb, 'ssb'])

            #       -> Sub Scripts [sub]
            sub_root = ssb_file_tree_store.append(map_root, ['', 'Sub (sss)', ''])
            for sss, ssbs in map_obj['subscripts'].items():
                #          -> (name) [sub_entry]
                sub_entry = ssb_file_tree_store.append(sub_root, ['', sss, ''])
                for ssb in ssbs:
                    #             -> Script X [ssb]
                    ssb_file_tree_store.append(sub_entry, [f"{map_obj['name']}/{ssb}", ssb, 'ssb'])

    # VARIABLES VIEW

    def on_variables_reload_clicked(self, *args):
        self.variable_controller.sync()

    def on_variables_load1_clicked(self, *args):
        if self.project_fm:
            self.variable_controller.load(1, self.project_fm.dir(PROJECT_DIR_SUBDIR_NAME))

    def on_variables_load2_clicked(self, *args):
        if self.project_fm:
            self.variable_controller.load(2, self.project_fm.dir(PROJECT_DIR_SUBDIR_NAME))

    def on_variables_load3_clicked(self, *args):
        if self.project_fm:
            self.variable_controller.load(3, self.project_fm.dir(PROJECT_DIR_SUBDIR_NAME))

    def on_variables_save1_clicked(self, *args):
        if self.project_fm:
            self.variable_controller.save(1, self.project_fm.dir(PROJECT_DIR_SUBDIR_NAME))

    def on_variables_save2_clicked(self, *args):
        if self.project_fm:
            self.variable_controller.save(2, self.project_fm.dir(PROJECT_DIR_SUBDIR_NAME))

    def on_variables_save3_clicked(self, *args):
        if self.project_fm:
            self.variable_controller.save(3, self.project_fm.dir(PROJECT_DIR_SUBDIR_NAME))

    # TODO: A bit of weird coupling with those two signal handlers.
    def on_ground_state_entities_tree_button_press_event(self, tree: Gtk.TreeView, event: Gdk.Event):
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            model, treeiter = tree.get_selection().get_selected()
            if treeiter is not None and model is not None:
                script_entity_type = SsbRoutineType.create_for_index(model[treeiter][10])
                script_entity_id = 0
                try:
                    script_entity_id = int(model[treeiter][0])
                except ValueError:
                    pass
                ges = self.debugger.ground_engine_state
                if ges:
                    if script_entity_type == SsbRoutineType.GENERIC:
                        ss = ges.global_script.script_struct
                    elif script_entity_type == SsbRoutineType.ACTOR:
                        ss = ges.get_actor(script_entity_id).script_struct
                    elif script_entity_type == SsbRoutineType.OBJECT:
                        ss = ges.get_object(script_entity_id).script_struct
                    elif script_entity_type == SsbRoutineType.PERFORMER:
                        ss = ges.get_performer(script_entity_id).script_struct
                    else:
                        return
                    if ss.hanger_ssb == -1:
                        return
                    ssb = ges.loaded_ssb_files[ss.hanger_ssb]
                    if not ssb:
                        return
                    self.editor_notebook.focus_by_opcode_addr(ssb.file_name, ss.current_opcode_addr_relative)

    def on_ground_state_files_tree_button_press_event(self, tree: Gtk.TreeView, event: Gdk.Event):
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            model, treeiter = tree.get_selection().get_selected()
            if treeiter is not None and model is not None:
                entry_type = model[treeiter][2]
                path = model[treeiter][1]
                # TODO: SSA/SSS/SSE support
                if entry_type == GE_FILE_STORE_SCRIPT and path and path != '':
                    self.editor_notebook.open_ssb(SCRIPT_DIR + '/' + path)

    # More functions
    def open_rom(self, fn: str):
        # TODO: Inject most of this later with SkyTemple via new environment object
        try:
            self.rom = NintendoDSRom.fromFile(fn)
            rom_data = get_ppmdu_config_for_rom(self.rom)
            self.project_fm = ProjectFileManager(fn)
            self.ssb_fm = SsbFileManager(self.rom, rom_data, fn, self.debugger, self.project_fm)
            self.breakpoint_manager = BreakpointManager(
                os.path.join(self.config_dir, f'{os.path.basename(fn)}.breakpoints.json'), self.ssb_fm
            )
            # Immediately save, because the module packs the ROM differently.
            self.rom.saveToFile(fn)
            self.rom_filename = fn
            if self.debugger:
                self.debugger.enable(rom_data, self.ssb_fm, self.breakpoint_manager,
                                     self.on_ground_engine_start)
            self.init_file_tree()
            self.variable_controller.init(rom_data)
            self.local_variable_controller.init(rom_data)
            self.editor_notebook.init(self.ssb_fm, self.breakpoint_manager, rom_data)
        except BaseException as ex:
            print(''.join(traceback.format_exception(etype=type(ex), value=ex, tb=ex.__traceback__)))
            md = Gtk.MessageDialog(self.window,
                                   Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                                   Gtk.ButtonsType.OK, f"Unable to load: {fn}\n{ex}",
                                   title="Error!")
            md.set_position(Gtk.WindowPosition.CENTER)
            md.run()
            md.destroy()
        else:
            self.enable_editing_features()
            if self.emu_thread:
                self.enable_debugging_features()
            self.emu_stop()

    def enable_editing_features(self):
        code_editor_main: Gtk.Box = self.builder.get_object('code_editor_main')
        code_editor_notebook: Gtk.Notebook = self.builder.get_object('code_editor_notebook')
        code_editor_main.remove(self.builder.get_object('main_label'))
        code_editor_main.pack_start(code_editor_notebook, True, True, 0)

    def enable_debugging_features(self):
        self._set_sensitve("emulator_controls_playstop", True)
        self._set_sensitve("emulator_controls_pause", True)
        self._set_sensitve("emulator_controls_playstop", True)
        self._set_sensitve("emulator_controls_reset", True)
        self._set_sensitve("emulator_controls_savestate1", True)
        self._set_sensitve("emulator_controls_savestate2", True)
        self._set_sensitve("emulator_controls_savestate3", True)
        self._set_sensitve("emulator_controls_loadstate1", True)
        self._set_sensitve("emulator_controls_loadstate2", True)
        self._set_sensitve("emulator_controls_loadstate3", True)
        self._set_sensitve("emulator_controls_volume", True)

        self._set_sensitve("variables_save1", True)
        self._set_sensitve("variables_save2", True)
        self._set_sensitve("variables_save3", True)
        self._set_sensitve("variables_load1", True)
        self._set_sensitve("variables_load2", True)
        self._set_sensitve("variables_load3", True)
        self._set_sensitve("variables_notebook_parent", True)

    def toggle_paused_debugging_features(self, on_off):
        if not on_off:
            if self.editor_notebook:
                self.editor_notebook.remove_hanger_halt_lines()
        # These are always on for now. (mostly for performance reason. TODO: Does this lead to issues?)
        #self._set_sensitve("variables_save1", on_off)
        #self._set_sensitve("variables_save2", on_off)
        #self._set_sensitve("variables_save3", on_off)
        #self._set_sensitve("variables_load1", on_off)
        #self._set_sensitve("variables_load2", on_off)
        #self._set_sensitve("variables_load3", on_off)
        #self._set_sensitve("variables_notebook_parent", on_off)
        self._set_sensitve("ground_state_files_tree_sw", on_off)
        self._set_sensitve("ground_state_entities_tree_sw", on_off)
        self._set_sensitve("macro_variables_sw", on_off)
        self._set_sensitve("local_variables_sw", on_off)

    def load_debugger_state(self, breaked_for: ScriptRuntimeStruct = None):
        self.toggle_paused_debugging_features(True)
        # Load Ground State
        self.ground_state_controller.sync(self.editor_notebook, breaked_for)
        # This will show the local and macro variables
        if breaked_for:
            self.local_variable_controller.sync(breaked_for)
        else:
            self.local_variable_controller.disable()

    def savestate(self, i: int):
        """Save both the emulator state and the ground engine state to files."""
        if not self.project_fm:
            return
        try:
            #if self.breakpoint_state.is_stopped():
            #    raise RuntimeError("Savestates can not be created while debugging.")
            rom_basename = os.path.basename(self.rom_filename)
            desmume_savestate_path = os.path.join(
                self.project_fm.dir(PROJECT_DIR_SUBDIR_NAME), f'{rom_basename}.save.{i}.{SAVESTATE_EXT_DESUME}'
            )
            ground_engine_savestate_path = os.path.join(
                self.project_fm.dir(PROJECT_DIR_SUBDIR_NAME), f'{rom_basename}.save.{i}.{SAVESTATE_EXT_GROUND_ENGINE}'
            )

            with open(ground_engine_savestate_path, 'w') as f:
                json.dump(self.debugger.ground_engine_state.serialize(), f)
            threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.savestate.save_file(desmume_savestate_path))
        except BaseException as err:
            md = Gtk.MessageDialog(self.window,
                                   Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                                   Gtk.ButtonsType.OK, str(err),
                                   title="Unable to save savestate!")
            md.set_position(Gtk.WindowPosition.CENTER)
            md.run()
            md.destroy()
            return

    def loadstate(self, i: int):
        """Loads both the emulator state and the ground engine state from files."""
        if not self.project_fm:
            return
        rom_basename = os.path.basename(self.rom_filename)
        desmume_savestate_path = os.path.join(
            self.project_fm.dir(PROJECT_DIR_SUBDIR_NAME), f'{rom_basename}.save.{i}.{SAVESTATE_EXT_DESUME}'
        )
        ground_engine_savestate_path = os.path.join(
            self.project_fm.dir(PROJECT_DIR_SUBDIR_NAME), f'{rom_basename}.save.{i}.{SAVESTATE_EXT_GROUND_ENGINE}'
        )

        if os.path.exists(ground_engine_savestate_path):
            try:
                was_running = threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.is_running())
                self._stopped = False
                self.emu_reset()
                threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.savestate.load_file(desmume_savestate_path))
                with open(ground_engine_savestate_path, 'r') as f:
                    self.debugger.ground_engine_state.deserialize(json.load(f))
                self.emu_is_running = threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.is_running())
                self.load_debugger_state()
                self.variable_controller.sync()
                if was_running:
                    self._set_buttons_running()
                else:
                    self._set_buttons_paused()
            except BaseException as ex:
                print("Savestate load error:")
                print(''.join(traceback.format_exception(etype=type(ex), value=ex, tb=ex.__traceback__)))
                md = Gtk.MessageDialog(self.window,
                                       Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.OK, str(ex),
                                       title="Unable to load savestate!")
                md.set_position(Gtk.WindowPosition.CENTER)
                md.run()
                md.destroy()
                return

    def set_touch_pos(self, x: int, y: int):
        scale = self.renderer.get_scale()
        rotation = self.renderer.get_screen_rotation()
        x /= scale
        y /= scale
        emu_x = x
        emu_y = y
        if rotation == 90 or rotation == 270:
            emu_x = 256 -y
            emu_y = x

        if emu_x < 0:
            emu_x = 0
        elif emu_x > SCREEN_WIDTH - 1:
            emu_x = SCREEN_WIDTH - 1

        if emu_y < 9:
            emu_y = 0
        elif emu_y > SCREEN_HEIGHT:
            emu_y = SCREEN_HEIGHT

        threadsafe_emu_nonblocking(self.emu_thread, lambda: self.emu_thread.emu.input.touch_set_pos(int(emu_x), int(emu_y)))

    def lookup_key(self, keyval):
        key = False
        for i in range(0, Keys.NB_KEYS):
            if keyval == self._keyboard_cfg[i]:
                key = keymask(i)
                break
        return key

    def emu_reset(self):
        if self.emu_thread:
            if self.breakpoint_state:
                self.breakpoint_state.fail_hard()
            if self.debugger.ground_engine_state:
                self.debugger.ground_engine_state.reset(fully=True)
            try:
                threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.open(self.rom_filename))
                self.emu_is_running = threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.is_running())
            except RuntimeError:
                md = Gtk.MessageDialog(self.window,
                                       Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.OK, f"Emulator failed to load: {self.rom_filename}",
                                       title="Error!")
                md.set_position(Gtk.WindowPosition.CENTER)
                md.run()
                md.destroy()

    def emu_resume(self, state_type = BreakpointStateType.RESUME):
        """Resume the emulator. If the debugger is currently breaked, the state will transition to state_type."""
        self._stopped = False
        self.toggle_paused_debugging_features(False)
        self.clear_info_bar()
        if self.emu_thread:
            self._set_buttons_running()
            if not self._emu_is_running:
                threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.resume())
            if self.breakpoint_state:
                self.breakpoint_state.transition(state_type)
            else:
                threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.input.keypad_update(0))
                self.emu_thread.register_main_loop()
            self.emu_is_running = True

    def emu_stop(self):
        self._stopped = True
        if self.emu_thread:
            if self.breakpoint_state:
                self.breakpoint_state.fail_hard()
            threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.reset())
            threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.pause())
            self.emu_is_running = False

            self._set_buttons_stopped()
            self.load_debugger_state()
            self.write_info_bar(Gtk.MessageType.WARNING, "The game is stopped.")

    def emu_pause(self):
        if self.breakpoint_state and self.breakpoint_state.is_stopped():
            # This shouldn't happen...? It would lead to an invalid state, so just return.
            return
        if self.emu_is_running:
            threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.pause())
        self.load_debugger_state()
        self.write_info_bar(Gtk.MessageType.INFO, "The game is paused.")

        self._set_buttons_paused()
        self.emu_is_running = False

    # Runs in emu thread
    def on_ground_engine_start(self):
        """The ground engine started"""
        # TODO: This is more a quick fix for some issue with the variable syncing.
        threadsafe_gtk_nonblocking(lambda: self.variable_controller.sync())

    # Runs in emu thread
    def on_ground_engine_stop(self):
        """The ground engine stopped"""
        # TODO: This is more a quick fix for some issue with the variable syncing.
        threadsafe_gtk_nonblocking(lambda: self.variable_controller.sync())

    def break_pulled(self, state: BreakpointState, srs: ScriptRuntimeStruct):
        """
        The DebuggerController has paused at an instruction.
        - Update reference to state object.
        - Update the main UI (info bar, emulator controls).
        - Tell the GroundStateController about the hanger, to mark it in the list.
        - Tell the code editor about which file to open and which instruction to jump to.
        - Add release hook.
        """
        threadsafe_emu_nonblocking(self.emu_thread, lambda: self.emu_thread.emu.volume_set(0))

        ssb = self.debugger.ground_engine_state.loaded_ssb_files[state.hanger_id]
        opcode_addr = srs.current_opcode_addr_relative
        self.breakpoint_state = state
        self._set_buttons_paused()
        self.write_info_bar(Gtk.MessageType.WARNING, f"The debugger is halted at {ssb.file_name}.")
        # This will mark the hanger as being breaked:
        self.debugger.ground_engine_state.break_pulled(state)
        # This will tell the code editor to refresh the debugger controls for all open editors
        self.editor_notebook.break_pulled(state, ssb.file_name, opcode_addr)
        self.editor_notebook.focus_by_opcode_addr(ssb.file_name, opcode_addr)
        self.load_debugger_state(srs)
        self.debug_overlay.break_pulled()

        state.add_release_hook(self.break_released)

    def break_released(self, state: BreakpointState):
        """
        The BreakpointState went into a resuming state (hook added via BreakpointState.add_release_hook).
        - Delete local reference to state object
        - Update the main UI (info bar, emulator controls).
        - The ground state controller and code editors have their own hooks for the releasing.
        """
        # TODO: Don't resume / reset everything until the next tick, so save some time / resources during stepping.
        #       Because of race conditions, it's probably best not to call break_pulled until tick end
        #       but we may still need to update variables?
        if self.builder.get_object('emulator_controls_volume').get_active():
            threadsafe_emu_nonblocking(self.emu_thread, lambda: self.emu_thread.emu.volume_set(100))
        self.breakpoint_state = None
        self._set_buttons_running()
        self.toggle_paused_debugging_features(False)
        self.clear_info_bar()
        # This is faster than syncing the entire debugger state again.
        self.ground_state_controller.sync_break_hanger()
        self.debug_overlay.break_released()

    def _ssb_item_filter_visible_func(self, model, iter, data):
        return self._recursive_filter_func(self._search_text, model, iter)

    def _recursive_filter_func(self, search, model, iter):
        # TODO: This is super slow, there's definitely a better way.
        if search is None:
            return True
        i_match = search.lower() in model[iter][1].lower()
        if i_match:
            return True
        # See if parent matches
        parent = model[iter].parent
        while parent:
            if search.lower() in parent[1].lower():
                return True
            parent = parent.parent
        # See if child matches
        for child in model[iter].iterchildren():
            child_match = self._recursive_filter_func(search, child.model, child.iter)
            if child_match:
                self.builder.get_object('ssb_file_tree').expand_row(child.parent.path, False)
                return True
        return False

    def _set_sensitve(self, name, state):
        w = self.builder.get_object(name)
        w.set_sensitive(state)

    def _file_chooser(self, type, name, filter):
        btn = Gtk.STOCK_OPEN
        if type == Gtk.FileChooserAction.SAVE:
            btn = Gtk.STOCK_SAVE
        dialog = Gtk.FileChooserDialog(
            name,
            self.window,
            type,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, btn, Gtk.ResponseType.OK)
        )
        for f in filter:
            dialog.add_filter(f)

        response = dialog.run()
        fn = dialog.get_filename()
        dialog.destroy()

        return response, fn

    def _debugger_print_callback(self, string):
        textview: Gtk.TextView = self.builder.get_object('debug_log_textview')
        textview.get_buffer().insert(textview.get_buffer().get_end_iter(), string + '\n')

        if self._debug_log_scroll_to_bottom:
            self._suppress_event = True
            textview.scroll_to_mark(self._debug_log_textview_right_marker, 0, True, 0, 0)
            self._suppress_event = False

    def _warn_about_unsaved_vars(self):
        md = Gtk.MessageDialog(
            self.window,
            Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.WARNING,
            Gtk.ButtonsType.OK_CANCEL,
            f"You have unsaved changes to variables.\n"
            f"Variables are reset when the game is rebooted.\n"
            f"You need to save the variables and load them after boot.\n\n"
            f"Do you still want to continue?",
            title="Warning!"
        )

        response = md.run()
        md.destroy()

        if response == Gtk.ResponseType.OK:
            self.variable_controller.variables_changed_but_not_saved = False
            return True
        return False

    def write_info_bar(self, message_type: Gtk.MessageType, text: str):
        info_bar: Gtk.InfoBar = self.builder.get_object('info_bar')
        info_bar_label: Gtk.Label = self.builder.get_object('info_bar_label')
        info_bar_label.set_text(text)
        info_bar.set_message_type(message_type)
        info_bar.set_revealed(True)

    def clear_info_bar(self):
        info_bar: Gtk.InfoBar = self.builder.get_object('info_bar')
        info_bar.set_revealed(False)

    def _set_buttons_running(self):
        btn: Gtk.Button = self.builder.get_object('emulator_controls_playstop')
        if self.builder.get_object('img_play').get_parent():
            btn.remove(self.builder.get_object('img_play'))
            btn.add(self.builder.get_object('img_stop'))
        btn: Gtk.Button = self.builder.get_object('emulator_controls_pause')
        if self.builder.get_object('img_play2').get_parent():
            btn.remove(self.builder.get_object('img_play2'))
            btn.add(self.builder.get_object('img_pause'))

    def _set_buttons_stopped(self):
        btn: Gtk.Button = self.builder.get_object('emulator_controls_playstop')
        if self.builder.get_object('img_stop').get_parent():
            btn.remove(self.builder.get_object('img_stop'))
            btn.add(self.builder.get_object('img_play'))
        btn: Gtk.Button = self.builder.get_object('emulator_controls_pause')
        if self.builder.get_object('img_play2').get_parent():
            btn.remove(self.builder.get_object('img_play2'))
            btn.add(self.builder.get_object('img_pause'))

    def _set_buttons_paused(self):
        btn: Gtk.Button = self.builder.get_object('emulator_controls_pause')
        if self.builder.get_object('img_pause').get_parent():
            btn.remove(self.builder.get_object('img_pause'))
            btn.add(self.builder.get_object('img_play2'))
        btn: Gtk.Button = self.builder.get_object('emulator_controls_playstop')
        if self.builder.get_object('img_play').get_parent():
            btn.remove(self.builder.get_object('img_play'))
            btn.add(self.builder.get_object('img_stop'))

    def _show_are_you_sure_delete(self, text):
        dialog: Gtk.MessageDialog = Gtk.MessageDialog(
            self.window,
            Gtk.DialogFlags.MODAL,
            Gtk.MessageType.WARNING,
            Gtk.ButtonsType.NONE, text
        )
        dont_save: Gtk.Widget = dialog.add_button("Delete", Gtk.ResponseType.DELETE_EVENT)
        dont_save.get_style_context().add_class('destructive-action')
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.format_secondary_text('You will not be able to restore it.')
        response = dialog.run()
        dialog.destroy()
        return response

    def _show_generic_input(self, label_text, ok_text):
        dialog: Gtk.Dialog = self.builder.get_object('generic_input_dialog')
        entry: Gtk.Entry = self.builder.get_object('generic_input_dialog_entry')
        label: Gtk.Label = self.builder.get_object('generic_input_dialog_label')
        label.set_text(label_text)
        btn_cancel = dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        btn = dialog.add_button(ok_text, Gtk.ResponseType.OK)
        btn.set_can_default(True)
        btn.grab_default()
        entry.set_activates_default(True)
        response = dialog.run()
        dialog.hide()
        btn.get_parent().remove(btn)
        btn_cancel.get_parent().remove(btn_cancel)
        return response, entry.get_text()
