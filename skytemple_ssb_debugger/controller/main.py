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
from typing import Optional

import cairo
import gi
from ndspy.rom import NintendoDSRom

from desmume.controls import Keys, keymask, load_configured_config
from desmume.emulator import DeSmuME, SCREEN_WIDTH, SCREEN_HEIGHT
from desmume.frontend.gtk_drawing_area_desmume import AbstractRenderer
from desmume.frontend.gtk_drawing_impl.software import SoftwareRenderer
from skytemple_files.common.config.path import skytemple_config_dir
from skytemple_files.common.script_util import load_script_files, SCRIPT_DIR
from skytemple_files.common.util import get_rom_folder, get_ppmdu_config_for_rom
from skytemple_ssb_debugger.controller.debug_overlay import DebugOverlayController
from skytemple_ssb_debugger.controller.debugger import DebuggerController
from skytemple_ssb_debugger.controller.ground_state import GroundStateController
from skytemple_ssb_debugger.controller.variable import VariableController

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gdk, GLib
from gi.repository.Gtk import *


TICKS_PER_FRAME = 17
SAVESTATE_EXT_DESUME = 'ds'
SAVESTATE_EXT_GROUND_ENGINE = 'ge.json'


class MainController:
    def __init__(self, builder: Builder, window: Window):
        self.builder = builder
        self.window = window
        self.emu: Optional[DeSmuME] = None
        self.debugger: Optional[DebuggerController] = None
        self.debug_overlay: Optional[DebugOverlayController] = None
        self.variable_controller: VariableController = None
        self.rom: Optional[NintendoDSRom] = None
        self.rom_filename = None

        self.config_dir = os.path.join(skytemple_config_dir(), 'debugger')
        os.makedirs(self.config_dir, exist_ok=True)

        self._registered_main_loop = False
        self._fps_frame_count = 0
        self._fps_sec_start = 0
        self._fps = 0
        self._ticks_prev_frame = 0
        self._ticks_cur_frame = 0
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

        self._main_draw = builder.get_object("draw_main")
        self._main_draw.set_events(Gdk.EventMask.ALL_EVENTS_MASK)
        self._main_draw.show()
        self._sub_draw = builder.get_object("draw_sub")
        self._sub_draw.set_events(Gdk.EventMask.ALL_EVENTS_MASK)
        self._sub_draw.show()

        self.init_emulator()

        if self.emu:

            self.debugger = DebuggerController(self.emu, self._debugger_print_callback)

            self.debug_overlay = DebugOverlayController(self.emu, self.debugger)
            self.renderer = SoftwareRenderer(self.emu, self.debug_overlay.draw)
            self.renderer.init()

            self._keyboard_cfg, self._joystick_cfg = load_configured_config(self.emu)
            self._keyboard_tmp = self._keyboard_cfg

        self.variable_controller = VariableController(self.emu, self.builder)
        self.ground_state_controller = GroundStateController(self.emu, self.debugger, self.builder)

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
        self.builder.get_object('box_r3').set_size_request(330, -1)
        self.builder.get_object('frame_debug_log').set_size_request(220, -1)

        builder.connect_signals(self)

        # DEBUG
        self.open_rom('/home/marco/austausch/dev/skytemple/skyworkcopy_edit.nds')

    def init_emulator(self):
        try:
            # Load desmume
            # TODO: Dummy
            self.emu = DeSmuME("../../../desmume/desmume/src/frontend/interface/.libs/libdesmume.so")

            # Init joysticks
            self.emu.input.joy_init()
        except BaseException as ex:
            self.emu = None
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

    def on_main_window_destroy(self, *args):
        self.emu.destroy()
        Gtk.main_quit()

    def gtk_main_quit(self, *args):
        self.emu.destroy()
        Gtk.main_quit()

    def gtk_widget_hide_on_delete(self, w: Gtk.Widget, *args):
        w.hide_on_delete()
        return True

    def gtk_widget_hide(self, w: Gtk.Widget, *args):
        w.hide()

    # EMULATOR
    def on_draw_aspect_frame_size_allocate(self, widget: Gtk.AspectFrame, *args):
        scale = widget.get_child().get_allocated_width() / SCREEN_WIDTH
        self.renderer.set_scale(scale)
        self._current_screen_height = SCREEN_HEIGHT * scale
        self._current_screen_width = SCREEN_WIDTH * scale

    def on_main_window_key_press_event(self, widget: Gtk.Widget, event: Gdk.EventKey, *args):
        if self.emu:
            key = self.lookup_key(event.keyval)
            # shift,ctrl, both alts
            mask = Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK | Gdk.ModifierType.MOD5_MASK
            if event.state & mask == 0:
                if key and self.emu.is_running():
                    self.emu.input.keypad_add_key(key)
                    return True
            return False

    def on_main_window_key_release_event(self, widget: Gtk.Widget, event: Gdk.EventKey, *args):
        if self.emu:
            key = self.lookup_key(event.keyval)
            if key and self.emu.is_running():
                self.emu.input.keypad_rm_key(key)

    def on_draw_main_draw(self, widget: Gtk.DrawingArea, ctx: cairo.Context, *args):
        return self.renderer.screen(self._current_screen_width, self._current_screen_height, ctx, 0)

    def on_draw_main_configure_event(self, widget: Gtk.DrawingArea, *args):
        self.renderer.reshape(widget, 0)
        return True

    def on_draw_sub_draw(self, widget: Gtk.DrawingArea, ctx: cairo.Context, *args):
        return self.renderer.screen(self._current_screen_width, self._current_screen_height, ctx, 1)

    def on_draw_sub_configure_event(self, widget: Gtk.DrawingArea, *args):
        self.renderer.reshape(widget, 1)
        return True

    # TODO: Size changes!

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
        if self.emu:
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
        if self.emu:
            if display_id == 1 and self._click:
                self._click = False
                self.emu.input.touch_release()
            return True

    def on_draw_button_press_event(self, widget: Gtk.Widget, event: Gdk.EventButton, display_id: int):
        if self.emu:
            if event.button == 1:
                if display_id == 1 and self.emu.is_running():
                    self._click = True
                    _, x, y, state = widget.get_window().get_pointer()
                    if state & Gdk.ModifierType.BUTTON1_MASK:
                        self.set_touch_pos(x, y)
            return True

    # MENU FILE
    def on_menu_open_activate(self, *args):
        self.emu.pause()

        response, fn = self._file_chooser(Gtk.FileChooserAction.OPEN, "Open...", (self._filter_nds, self._filter_gba_ds, self._filter_any))

        if response == Gtk.ResponseType.OK:
            self.open_rom(fn)

    def on_menu_save_activate(self, menu_item: Gtk.MenuItem, *args):
        pass  # todo

    def on_menu_save_all_activate(self, menu_item: Gtk.MenuItem, *args):
        pass  # todo

    def on_menu_quit_activate(self, menu_item: Gtk.MenuItem, *args):
        self.gtk_main_quit()

    # EMULATOR CONTROLS
    def on_emulator_controls_playstop_clicked(self, button: Gtk.Button):
        if self.emu:
            if not self._stopped:
                self.emu_stop()
            else:
                if not self.variable_controller.variables_changed_but_not_saved or self._warn_about_unsaved_vars():
                    self.emu_reset()
                    self.emu_resume()

    def on_emulator_controls_pause_clicked(self, button: Gtk.Button):
        if self.emu:
            if self.emu.is_running() and self._registered_main_loop:
                self.emu_pause()
            elif not self._stopped:
                self.emu_resume()

    def on_emulator_controls_reset_clicked(self, button: Gtk.Button):
        if self.emu:
            self.emu.reset()
            self.emu_resume()

    def on_emulator_controls_volume_toggled(self, button: Gtk.ToggleButton):
        if self.emu:
            if button.get_active():
                self.emu.volume_set(100)
            else:
                self.emu.volume_set(0)

    def on_emulator_controls_savestate1_clicked(self, button: Gtk.Button):
        if self.emu:
            self.savestate(1)

    def on_emulator_controls_savestate2_clicked(self, button: Gtk.Button):
        if self.emu:
            self.savestate(2)

    def on_emulator_controls_savestate3_clicked(self, button: Gtk.Button):
        if self.emu:
            self.savestate(3)

    def on_emulator_controls_loadstate1_clicked(self, button: Gtk.Button):
        if self.emu:
            self.loadstate(1)

    def on_emulator_controls_loadstate2_clicked(self, button: Gtk.Button):
        if self.emu:
            self.loadstate(2)

    def on_emulator_controls_loadstate3_clicked(self, button: Gtk.Button):
        if self.emu:
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

    def init_file_tree(self):
        ssb_file_tree_store: Gtk.TreeStore = self.builder.get_object('ssb_file_tree_store')
        ssb_file_tree_store.clear()

        if not self._ssb_item_filter:
            self._ssb_item_filter = ssb_file_tree_store.filter_new()
            self.builder.get_object('ssb_file_tree').set_model(self._ssb_item_filter)
            self._ssb_item_filter.set_visible_func(self._ssb_item_filter_visible_func)

        self._set_sensitve('ssb_file_search', True)

        script_files = load_script_files(get_rom_folder(self.rom, SCRIPT_DIR))

        #    -> Common [common]
        common_root = ssb_file_tree_store.append(None, ['', 'Common'])
        #       -> Master Script (unionall) [ssb]
        #       -> (others) [ssb]
        for name in script_files['common']:
            ssb_file_tree_store.append(common_root, ['COMMON/' + name, name])

        for i, map_obj in enumerate(script_files['maps'].values()):
            #    -> (Map Name) [map]
            map_root = ssb_file_tree_store.append(None, ['', map_obj['name']])

            enter_root = ssb_file_tree_store.append(map_root, ['', 'Enter (sse)'])
            if map_obj['enter_sse'] is not None:
                #          -> Script X [ssb]
                for ssb in map_obj['enter_ssbs']:
                    ssb_file_tree_store.append(enter_root, [f"{map_obj['name']}/{ssb}", ssb])

            #       -> Acting Scripts [lsd]
            acting_root = ssb_file_tree_store.append(map_root, ['', 'Acting (ssa)'])
            for _, ssb in map_obj['ssas']:
                #             -> Script [ssb]
                ssb_file_tree_store.append(acting_root, [f"{map_obj['name']}/{ssb}", ssb])

            #       -> Sub Scripts [sub]
            sub_root = ssb_file_tree_store.append(map_root, ['', 'Sub (sss)'])
            for sss, ssbs in map_obj['subscripts'].items():
                #          -> (name) [sub_entry]
                sub_entry = ssb_file_tree_store.append(sub_root, ['', sss])
                for ssb in ssbs:
                    #             -> Script X [ssb]
                    ssb_file_tree_store.append(sub_entry, [f"{map_obj['name']}/{ssb}", ssb])

    # VARIABLES VIEW

    def on_variables_load1_clicked(self, *args):
        self.variable_controller.load(1, self.config_dir)

    def on_variables_load2_clicked(self, *args):
        self.variable_controller.load(2, self.config_dir)

    def on_variables_load3_clicked(self, *args):
        self.variable_controller.load(3, self.config_dir)

    def on_variables_save1_clicked(self, *args):
        self.variable_controller.save(1, self.config_dir)

    def on_variables_save2_clicked(self, *args):
        self.variable_controller.save(2, self.config_dir)

    def on_variables_save3_clicked(self, *args):
        self.variable_controller.save(3, self.config_dir)

    # More functions
    def open_rom(self, fn: str):
        try:
            self.rom = NintendoDSRom.fromFile(fn)
            # Immediately save, because the module packs the ROM differently.
            self.rom.saveToFile(fn)
            self.rom_filename = fn
            rom_data = get_ppmdu_config_for_rom(self.rom)
            self.debugger.enable(rom_data)
            self.init_file_tree()
            self.variable_controller.init(rom_data)
        except BaseException as ex:
            md = Gtk.MessageDialog(self.window,
                                   Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                                   Gtk.ButtonsType.OK, f"Unable to load: {fn}\n{ex}",
                                   title="Error!")
            md.set_position(Gtk.WindowPosition.CENTER)
            md.run()
            md.destroy()
        else:
            self.enable_editing_features()
            if self.emu:
                self.enable_debugging_features()
            self.emu_stop()

    def enable_editing_features(self):
        label: Gtk.Label = self.builder.get_object('main_label')
        label.set_text('Welcome to\n' 
                       'SkyTemple\n'
                       'Script Engine Debugger.\n'
                       '\n'
                       'Please select a script to edit,\n'
                       'or start the game.')

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

    def toggle_paused_debugging_features(self, on_off):
        self._set_sensitve("variables_save1", on_off)
        self._set_sensitve("variables_save2", on_off)
        self._set_sensitve("variables_save3", on_off)
        self._set_sensitve("variables_load1", on_off)
        self._set_sensitve("variables_load2", on_off)
        self._set_sensitve("variables_load3", on_off)
        self._set_sensitve("variables_notebook", on_off)
        self._set_sensitve("ground_state_files_tree_sw", on_off)
        self._set_sensitve("ground_state_entities_tree_sw", on_off)

    def load_debugger_state(self):
        self.toggle_paused_debugging_features(True)
        # Load Variables
        self.variable_controller.sync()
        # Load Ground State
        self.ground_state_controller.sync()

    def savestate(self, i: int):
        """Save both the emulator state and the ground engine state to files."""
        rom_basename = os.path.basename(self.rom_filename)
        desmume_savestate_path = os.path.join(self.config_dir, f'{rom_basename}.save.{i}.{SAVESTATE_EXT_DESUME}')
        ground_engine_savestate_path = os.path.join(self.config_dir, f'{rom_basename}.save.{i}.{SAVESTATE_EXT_GROUND_ENGINE}')

        try:
            with open(ground_engine_savestate_path, 'w') as f:
                json.dump(self.debugger.ground_engine_state.serialize(), f)
            self.emu.savestate.save_file(desmume_savestate_path)
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
        rom_basename = os.path.basename(self.rom_filename)
        desmume_savestate_path = os.path.join(self.config_dir, f'{rom_basename}.save.{i}.{SAVESTATE_EXT_DESUME}')
        ground_engine_savestate_path = os.path.join(self.config_dir, f'{rom_basename}.save.{i}.{SAVESTATE_EXT_GROUND_ENGINE}')

        if os.path.exists(ground_engine_savestate_path):
            try:
                was_running = self.emu.is_running()
                self.emu_reset()
                self._stopped = False
                with open(ground_engine_savestate_path, 'r') as f:
                    self.debugger.ground_engine_state.deserialize(json.load(f))
                self.emu.savestate.load_file(desmume_savestate_path)
                self.ground_state_controller.sync()
                if was_running:
                    self._set_buttons_running()
                else:
                    self._set_buttons_paused()
            except BaseException as err:
                md = Gtk.MessageDialog(self.window,
                                       Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.OK, str(err),
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

        self.emu.input.touch_set_pos(int(emu_x), int(emu_y))

    def lookup_key(self, keyval):
        key = False
        for i in range(0, Keys.NB_KEYS):
            if keyval == self._keyboard_cfg[i]:
                key = keymask(i)
                break
        return key

    def emu_reset(self):
        if self.emu:
            if self.debugger.ground_engine_state:
                self.debugger.ground_engine_state.reset()
            try:
                self.emu.open(self.rom_filename)
            except RuntimeError:
                md = Gtk.MessageDialog(self.window,
                                       Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.OK, f"Emulator failed to load: {self.rom_filename}",
                                       title="Error!")
                md.set_position(Gtk.WindowPosition.CENTER)
                md.run()
                md.destroy()

    def emu_resume(self):
        self._stopped = False
        self.toggle_paused_debugging_features(False)
        self.clear_info_bar()
        if self.emu:
            self._set_buttons_running()
            self.emu.resume()
            self.emu.input.keypad_update(0)
            if not self._registered_main_loop:
                self._registered_main_loop = True
                GLib.idle_add(self.emu_cycle)

    def emu_stop(self):
        self._stopped = True
        if self.emu:
            self._set_buttons_stopped()
            self.load_debugger_state()
            self.write_info_bar(Gtk.MessageType.WARNING, "The game is stopped.")
            self.emu.reset()
            self.emu.pause()

    def emu_pause(self):
        self.load_debugger_state()
        self.write_info_bar(Gtk.MessageType.INFO, "The game is paused.")

        self._set_buttons_paused()
        if self.emu.is_running():
            self.emu.pause()

    def emu_cycle(self):
        if not self.emu:
            self._registered_main_loop = False
            return False

        if self.emu.is_running():
            self._fps_frame_count += 1

            if not self._fps_sec_start:
                self._fps_sec_start = self.emu.get_ticks()
            if self.emu.get_ticks() - self._fps_sec_start >= 1000:
                self._fps_sec_start = self.emu.get_ticks()
                self._fps = self._fps_frame_count
                self._fps_frame_count = 0

            self.emu.cycle()

            self._main_draw.queue_draw()
            self._sub_draw.queue_draw()

            self._ticks_cur_frame = self.emu.get_ticks()

            if self._ticks_cur_frame - self._ticks_prev_frame < TICKS_PER_FRAME:
                while self._ticks_cur_frame - self._ticks_prev_frame < TICKS_PER_FRAME:
                    self._ticks_cur_frame = self.emu.get_ticks()

            self._ticks_prev_frame = self.emu.get_ticks()
            return True

        self._main_draw.queue_draw()
        self._sub_draw.queue_draw()
        self._registered_main_loop = False
        return False

    def _ssb_item_filter_visible_func(self, model, iter, data):
        return self._recursive_filter_func(self._search_text, model, iter)

    def _recursive_filter_func(self, search, model, iter):
        if search is None:
            return True
        i_match = search.lower() in model[iter][1].lower()
        if i_match:
            return True
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
