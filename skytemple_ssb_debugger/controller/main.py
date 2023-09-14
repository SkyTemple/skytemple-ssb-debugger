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
import os
import shutil
import sys
import webbrowser
from functools import partial
from typing import Optional, Dict, List, Sequence, cast, TypeVar

import cairo
import gi
from PIL import Image
from range_typed_integers import u32

from skytemple_files.common.util import open_utf8, add_extension_if_missing
from skytemple_ssb_emulator import SCREEN_WIDTH, SCREEN_HEIGHT, emulator_load_controls, Language, emulator_poll, \
    emulator_get_kbcfg, emulator_set_kbcfg, emulator_get_jscfg, emulator_set_jscfg, emulator_keypad_add_key, \
    emulator_keymask, EmulatorKeys, emulator_keypad_rm_key, emulator_touch_release, emulator_supports_joystick, \
    emulator_is_running, SCREEN_HEIGHT_BOTH, emulator_volume_set, emulator_savestate_load_file, \
    emulator_savestate_save_file, emulator_set_debug_mode, emulator_set_debug_flag_1, emulator_set_debug_flag_2, \
    emulator_start, emulator_joy_init, emulator_touch_set_pos, emulator_resume, emulator_unpress_all_keys, \
    emulator_reset, emulator_pause, emulator_shutdown, emulator_set_boost, emulator_set_language, emulator_open_rom, \
    emulator_display_buffer_as_rgbx, emulator_debug_init_breakpoint_manager

gi.require_version('GtkSource', '4')
from gi.repository.GtkSource import StyleSchemeManager

from explorerscript import EXPLORERSCRIPT_EXT
from explorerscript.ssb_converting.ssb_data_types import SsbRoutineType
from skytemple_files.common.script_util import SCRIPT_DIR
from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_ssb_debugger.controller.debug_overlay import DebugOverlayController
from skytemple_ssb_debugger.controller.debugger import DebuggerController
from skytemple_ssb_debugger.controller.editor_notebook import EditorNotebookController
from skytemple_ssb_debugger.controller.ground_state import GroundStateController, GE_FILE_STORE_SCRIPT
from skytemple_ssb_debugger.controller.local_variable import LocalVariableController
from skytemple_ssb_debugger.controller.global_state import GlobalStateController
from skytemple_ssb_debugger.controller.variable import VariableController
from skytemple_ssb_debugger.model.breakpoint_file_state import BreakpointFileState
from skytemple_ssb_emulator import BreakpointState, BreakpointStateType
from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct
from skytemple_ssb_debugger.model.settings import DebuggerSettingsStore, TEXTBOX_TOOL_URL
from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager
from skytemple_ssb_debugger.renderer.async_software import AsyncSoftwareRenderer
from skytemple_ssb_debugger.ui_util import builder_get_assert, create_tree_view_column
from skytemple_ssb_debugger.controller.desmume_control_ui.joystick_controls import JoystickControlsDialogController
from skytemple_ssb_debugger.controller.desmume_control_ui.keyboard_controls import KeyboardControlsDialogController
from skytemple_files.common.i18n_util import f, _
from skytemple_ssb_debugger.ui_util import assert_not_none

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gdk, GLib

logger = logging.getLogger(__name__)


SAVESTATE_EXT_DESUME = 'ds'
SAVESTATE_EXT_GROUND_ENGINE = 'ge.json'
COL_VISIBLE = 3


class MainController:
    
    def __init__(self, builder: Gtk.Builder, window: Gtk.Window, control_context: AbstractDebuggerControlContext):
        self.builder = builder
        self.window = window
        self.context: AbstractDebuggerControlContext = control_context
        self.settings = DebuggerSettingsStore()
        self.ssb_fm: Optional[SsbFileManager] = None
        self.rom_was_loaded = False
        self._emu_is_running = False

        self._enable_explorerscript = True

        self.debugger: Optional[DebuggerController] = None
        self.debug_overlay: Optional[DebugOverlayController] = None
        self.breakpoint_state: Optional[BreakpointState] = None

        self._click = False
        self._debug_log_scroll_to_bottom = False
        self._suppress_event = False
        self._stopped = False
        self._resize_timeout_id: Optional[int] = None

        self._search_text: Optional[str] = None
        self._ssb_item_filter: Optional[Gtk.TreeModelFilter] = None

        self._log_stdout_io_source = None

        self._file_tree_store = Gtk.TreeStore(str, str, str, bool)  # type: ignore

        self._current_screen_width = SCREEN_WIDTH
        self._current_screen_height = SCREEN_HEIGHT

        # A mapping for ssb filenames and their scene types ('ssa'/'sse'/'sss'/''[if n/a])
        # - For opening the scene editor.
        self._scene_types: Dict[str, str] = {}
        self._scene_names: Dict[str, str] = {}
        # Significant sub-branches of the file list. Contains entries in the form:
        # mapname_{enter,acting,subroot,{sss_name_with_extension}}
        self._tree_branches: Dict[str, Gtk.TreeIter] = {}
        # Root branches for the maps. Contains entries in the form:
        # mapname
        self._registered_maps: Dict[str, Gtk.TreeIter] = {}

        spellcheck_enabled_item = builder_get_assert(self.builder, Gtk.CheckMenuItem, 'menu_spellcheck_enabled')
        spellcheck_enabled_item.set_active(self.settings.get_spellcheck_enabled())

        # Source editor style schema
        self.style_scheme_manager = StyleSchemeManager()
        self.selected_style_scheme_id: str = self.settings.get_style_scheme()  # type: ignore
        was_none_before = self.selected_style_scheme_id is None
        style_dict: Dict[str, str] = {}
        for style_id in assert_not_none(self.style_scheme_manager.get_scheme_ids()):
            if not self.selected_style_scheme_id or (was_none_before and style_id == 'oblivion'):
                self.selected_style_scheme_id = style_id
            style_dict[style_id] = assert_not_none(self.style_scheme_manager.get_scheme(style_id)).get_name()
        menu_view_schemes = builder_get_assert(self.builder, Gtk.MenuItem, 'menu_view_schemes')
        first_item = None
        submenu = Gtk.Menu.new()
        for style_id, style_name in style_dict.items():
            new_item: Gtk.RadioMenuItem = Gtk.RadioMenuItem.new()
            new_item.set_property('group', first_item)  # upstream bug; can't use the constructor for this.
            new_item.set_label(style_name)
            if first_item is None:
                first_item = new_item
            if self.selected_style_scheme_id == style_id:
                new_item.set_active(True)
            new_item.connect('toggled', partial(self.on_menu_view_schemes_switch, style_id))
            submenu.append(new_item)
        submenu.show_all()
        menu_view_schemes.set_submenu(submenu)

        self._filter_nds = Gtk.FileFilter()
        self._filter_nds.set_name(_("Nintendo DS ROMs (*.nds)"))
        self._filter_nds.add_pattern("*.nds")

        self._filter_gba_ds = Gtk.FileFilter()
        self._filter_gba_ds.set_name(_("Nintendo DS ROMs with binary loader (*.ds.gba)"))
        self._filter_gba_ds.add_pattern("*.nds")

        self._filter_any = Gtk.FileFilter()
        self._filter_any.set_name(_("All files"))
        self._filter_any.add_pattern("*")

        self._poll_emulator_event_id: Optional[int] = None

        self.main_draw = builder_get_assert(builder, Gtk.DrawingArea, "draw_main")
        self.main_draw.set_events(Gdk.EventMask.ALL_EVENTS_MASK)
        self.main_draw.show()
        self.sub_draw = builder_get_assert(builder, Gtk.DrawingArea, "draw_sub")
        self.sub_draw.set_events(Gdk.EventMask.ALL_EVENTS_MASK)
        self.sub_draw.show()

        self.renderer = None
        self.init_emulator()

        self.debugger = DebuggerController(self._debugger_print_callback, self)

        self.debug_overlay = DebugOverlayController(self.debugger)
        self.renderer = AsyncSoftwareRenderer(self.main_draw, self.sub_draw, self.debug_overlay.draw)
        self.renderer.start()

        emulator_load_controls(
            self.settings.get_emulator_keyboard_cfg(),
            self.settings.get_emulator_joystick_cfg()
        )

        lang = self.settings.get_emulator_language()
        if lang:
            self._suppress_event = True
            if lang == Language.Japanese:
                builder_get_assert(self.builder, Gtk.RadioMenuItem, 'menu_emulator_language_jp').set_active(True)
            elif lang == Language.English:
                builder_get_assert(self.builder, Gtk.RadioMenuItem, 'menu_emulator_language_en').set_active(True)
            elif lang == Language.French:
                builder_get_assert(self.builder, Gtk.RadioMenuItem, 'menu_emulator_language_fr').set_active(True)
            elif lang == Language.German:
                builder_get_assert(self.builder, Gtk.RadioMenuItem, 'menu_emulator_language_de').set_active(True)
            elif lang == Language.Italian:
                builder_get_assert(self.builder, Gtk.RadioMenuItem, 'menu_emulator_language_it').set_active(True)
            elif lang == Language.Spanish:
                builder_get_assert(self.builder, Gtk.RadioMenuItem, 'menu_emulator_language_es').set_active(True)
            self._suppress_event = False

        self.editor_notebook: EditorNotebookController = EditorNotebookController(
            self.builder, self, self.window, self._enable_explorerscript
        )
        self.variable_controller: VariableController = VariableController(self.builder, self.context)
        self.global_state_controller: GlobalStateController = GlobalStateController(self.builder)
        self.local_variable_controller: LocalVariableController = LocalVariableController(self.builder, self.debugger)
        self.ground_state_controller = GroundStateController(self.debugger, self.builder)

        # Load more initial settings
        self.on_debug_log_cntrl_ops_toggled(builder_get_assert(builder, Gtk.CheckButton, 'debug_log_cntrl_ops'))
        self.on_debug_log_cntrl_script_toggled(builder_get_assert(builder, Gtk.CheckButton, 'debug_log_cntrl_script'))
        self.on_debug_log_cntrl_internal_toggled(builder_get_assert(builder, Gtk.CheckButton, 'debug_log_cntrl_internal'))
        self.on_debug_log_cntrl_ground_state_toggled(builder_get_assert(builder, Gtk.CheckButton, 'debug_log_cntrl_ground_state'))
        self.on_debug_settings_debug_mode_toggled(builder_get_assert(builder, Gtk.CheckButton, 'debug_settings_debug_mode'))
        self.on_debug_settings_overlay_toggled(builder_get_assert(builder, Gtk.CheckButton, 'debug_settings_overlay'))
        self.on_emulator_controls_volume_toggled(builder_get_assert(builder, Gtk.ToggleButton, 'emulator_controls_volume'))
        self.on_debug_log_scroll_to_bottom_toggled(builder_get_assert(builder, Gtk.ToggleButton, 'debug_log_scroll_to_bottom'))

        # Trees / Lists
        ssb_file_tree = builder_get_assert(self.builder, Gtk.TreeView, 'ssb_file_tree')
        column_main = create_tree_view_column(_("Name"), Gtk.CellRendererText(), text=1)
        ssb_file_tree.append_column(column_main)

        # Other gtk stuff
        self._debug_log_textview_right_marker = builder_get_assert(self.builder, Gtk.TextView, 'debug_log_textview').get_buffer().create_mark(
            'end', builder_get_assert(self.builder, Gtk.TextView, 'debug_log_textview').get_buffer().get_end_iter(), False
        )

        # Initial sizes
        builder_get_assert(self.builder, Gtk.Frame, 'frame_debug_log').set_size_request(220, -1)

        # Load window sizes
        window_size = self.settings.get_window_size()
        if window_size is not None:
            self.window.resize(*window_size)
        window_position = self.settings.get_window_position()
        if window_position is not None:
            self.window.move(*window_position)

        builder.connect_signals(self)
        self.window.present()

        if not self.context.allows_interactive_file_management():
            menu_file = builder_get_assert(self.builder, Gtk.Menu, 'menu_file')
            for child in menu_file.get_children():
                if Gtk.Buildable.get_name(child) in ['menu_open', 'menu_open_sep']:
                    menu_file.remove(child)

    def get_context(self) -> AbstractDebuggerControlContext:
        return self.context

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

    @property
    def _keyboard_cfg(self):
        return emulator_get_kbcfg()

    @_keyboard_cfg.setter
    def _keyboard_cfg(self, value):
        emulator_set_kbcfg(value)

    @property
    def _joystick_cfg(self):
        return emulator_get_jscfg()

    @_joystick_cfg.setter
    def _joystick_cfg(self, value):
        emulator_set_jscfg(value, False)

    @property
    def global_state__breaks_disabled(self):
        return builder_get_assert(self.builder, Gtk.CheckMenuItem, 'menu_debugger_disable_breaks').get_active()

    @global_state__breaks_disabled.setter
    def global_state__breaks_disabled(self, value):
        if self._suppress_event:
            return
        builder_get_assert(self.builder, Gtk.CheckMenuItem, 'menu_debugger_disable_breaks').set_active(value)

    @property
    def global_state__audio_enabled(self):
        return builder_get_assert(self.builder, Gtk.ToggleButton, 'emulator_controls_volume').get_active()

    def init_emulator(self):
        try:
            # Load emulator
            emulator_start()

            # Init joysticks
            emulator_joy_init()

            # Poll the emulator for events periodically
            self.install_poll_emulator()
        except BaseException as ex:
            self.context.display_error(
                sys.exc_info(),
                f(_("The emulator couldn't be loaded. "
                    "Debugging functionality will not be available:\n\n"
                    "{ex}")),
                _("Error loading the emulator!")
            )
            return

    def install_poll_emulator(self):
        # 30 FPS
        self._poll_emulator_event_id = GLib.timeout_add(1000 // 30, self.do_poll_emulator)

    def uninstall_poll_emulator(self):
        if self._poll_emulator_event_id is not None:
            GLib.source_remove(self._poll_emulator_event_id)

    def do_poll_emulator(self):
        try:
            errs = []
            while emulator_poll(lambda err: errs.append(err)):
                pass
            if len(errs) > 0:
                # noinspection PyUnusedLocal
                errs_as_str = "\n".join(errs)
                self.context.display_error(
                    None,
                    f(_("The emulator reported an error:\n\n{errs_as_str}")),
                    _("Emulator Error")
                )
        except Exception as ex:
            self.context.display_error(
                sys.exc_info(),
                f(_("The emulator reported an internal error:\n\n")),
                _("Emulator Error")
            )
        return True

    def on_main_window_delete_event(self, *args):
        if not self.editor_notebook.close_all_tabs() or not self.context.before_quit():
            return True
        if self.rom_was_loaded:
            self.uninit_project()
        self.gtk_main_quit()
        return False

    def on_main_window_destroy(self, *args):
        self.gtk_main_quit()

    def gtk_main_quit(self, *args):
        if self.breakpoint_state:
            self.breakpoint_state.fail_hard()
        if not self._stopped:
            self.emu_stop()
        self.uninstall_poll_emulator()
        emulator_shutdown()
        self.context.on_quit()

    def gtk_widget_hide_on_delete(self, w: Gtk.Widget, *args):
        w.hide_on_delete()
        return True

    def gtk_widget_hide(self, w: Gtk.Widget, *args):
        w.hide()

    def on_main_window_state_event(self, w: Gtk.Window, evt: Gdk.EventWindowState):
        if evt.changed_mask & Gdk.WindowState.FOCUSED:
            if evt.new_window_state & Gdk.WindowState.FOCUSED:
                self.context.on_focus()
            else:
                self.context.on_blur()

    # EMULATOR
    def on_draw_aspect_frame_size_allocate(self, widget: Gtk.AspectFrame, *args):
        scale = assert_not_none(widget.get_child()).get_allocated_width() / SCREEN_WIDTH
        if self.renderer:
            self.renderer.set_scale(scale)
        self._current_screen_height = round(SCREEN_HEIGHT * scale)
        self._current_screen_width = round(SCREEN_WIDTH * scale)

    def on_main_window_key_press_event(self, widget: Gtk.Widget, event: Gdk.EventKey, *args):
        # Don't enable controls when in any entry or text view
        if isinstance(self.window.get_focus(), Gtk.Entry) or isinstance(self.window.get_focus(), Gtk.TextView):
            return False
        key = self.lookup_key(event.keyval)
        # shift,ctrl, both alts
        mask = Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK | Gdk.ModifierType.MOD5_MASK
        if event.state & mask == 0:
            if key and self.emu_is_running:
                emulator_keypad_add_key(key)
                if key == emulator_keymask(EmulatorKeys.KEY_BOOST):
                    # Handle boost
                    self.toggle_boost(True)
                return True
        return False

    def on_main_window_key_release_event(self, widget: Gtk.Widget, event: Gdk.EventKey, *args):
        key = self.lookup_key(event.keyval)
        if key and self.emu_is_running:
            emulator_keypad_rm_key(key)
            if key == emulator_keymask(EmulatorKeys.KEY_BOOST):
                # Handle boost
                self.toggle_boost(False)

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
        if display_id == 1 and self._click:
            if event.is_hint:
                _, x, y, state = assert_not_none(widget.get_window()).get_pointer()
            else:
                x = round(event.x)
                y = round(event.y)
                state = event.state
            if state & Gdk.ModifierType.BUTTON1_MASK:
                self.set_touch_pos(x, y)

    def on_draw_button_release_event(self, widget: Gtk.Widget, event: Gdk.EventButton, display_id: int):
        if display_id == 1 and self._click:
            self._click = False
            emulator_touch_release()
        return True

    def on_draw_button_press_event(self, widget: Gtk.Widget, event: Gdk.EventButton, display_id: int):
        widget.grab_focus()
        if event.button == 1:
            if display_id == 1 and self.emu_is_running:
                self._click = True
                _, x, y, state = assert_not_none(widget.get_window()).get_pointer()
                if state & Gdk.ModifierType.BUTTON1_MASK:
                    self.set_touch_pos(x, y)
        return True

    def on_right_event_box_button_press_event(self, widget: Gtk.Widget, *args):
        """If the right area of the window is pressed, focus it, to disable any entry/textview focus."""
        widget.grab_focus()
        return False

    # MENU FILE
    def on_menu_open_activate(self, *args):
        if not self.context.allows_interactive_file_management():
            return
        emulator_pause()

        response, fn = self._file_chooser(Gtk.FileChooserAction.OPEN, _("Open..."), (self._filter_nds, self._filter_gba_ds, self._filter_any))

        if response == Gtk.ResponseType.ACCEPT:
            try:
                self.context.open_rom(fn)
            except BaseException as ex:
                self.context.display_error(
                    sys.exc_info(),
                    f(_("Unable to load: {fn}\n{ex}"))
                )
            self.load_rom()

    def on_menu_save_activate(self, menu_item: Gtk.MenuItem, *args):
        if self.editor_notebook and self.editor_notebook.currently_open:
            self.editor_notebook.currently_open.save()

    def on_menu_close_activate(self, menu_item: Gtk.MenuItem, *args):
        self.editor_notebook.close_open_tab()

    def on_menu_save_all_activate(self, menu_item: Gtk.MenuItem, *args):
        self.editor_notebook.save_all()

    def on_menu_quit_activate(self, menu_item: Gtk.MenuItem, *args):
        self.on_main_window_delete_event()

    # MENU EDIT
    def on_menu_edit_cut_activate(self, menu_item: Gtk.MenuItem, *args):
        if self.editor_notebook and self.editor_notebook.currently_open:
            self.editor_notebook.currently_open.menu__cut()

    def on_menu_edit_copy_activate(self, menu_item: Gtk.MenuItem, *args):
        if self.editor_notebook and self.editor_notebook.currently_open:
            self.editor_notebook.currently_open.menu__copy()

    def on_menu_edit_paste_activate(self, menu_item: Gtk.MenuItem, *args):
        if self.editor_notebook and self.editor_notebook.currently_open:
            self.editor_notebook.currently_open.menu__paste()

    def on_menu_edit_undo_activate(self, menu_item: Gtk.MenuItem, *args):
        if self.editor_notebook and self.editor_notebook.currently_open:
            self.editor_notebook.currently_open.menu__undo()

    def on_menu_edit_redo_activate(self, menu_item: Gtk.MenuItem, *args):
        if self.editor_notebook and self.editor_notebook.currently_open:
            self.editor_notebook.currently_open.menu__redo()

    def on_menu_edit_search_activate(self, menu_item: Gtk.MenuItem, *args):
        if self.editor_notebook and self.editor_notebook.currently_open:
            self.editor_notebook.currently_open.menu__search()

    def on_menu_edit_replace_activate(self, menu_item: Gtk.MenuItem, *args):
        if self.editor_notebook and self.editor_notebook.currently_open:
            self.editor_notebook.currently_open.menu__replace()

    # MENU VIEW
    def on_menu_view_schemes_switch(self, scheme_id: str, *args):
        if hasattr(self, 'editor_notebook'):  # skip during __init__
            self.selected_style_scheme_id = scheme_id
            self.editor_notebook.switch_style_scheme(self.style_scheme_manager.get_scheme(scheme_id))
            self.settings.set_style_scheme(scheme_id)

    def on_menu_spellcheck_enabled_toggled(self, btn: Gtk.CheckMenuItem, *args):
        if hasattr(self, 'editor_notebook'):  # skip during __init__
            self.editor_notebook.toggle_spellchecker(btn.get_active())
            self.settings.set_spellcheck_enabled(btn.get_active())

    # MENU DEBUGGER
    def on_menu_debugger_disable_breaks_toggled(self, btn: Gtk.CheckMenuItem, *args):
        if self.debugger:
            self.debugger.breakpoints_disabled = btn.get_active()
            self._suppress_event = True
            self.editor_notebook.toggle_breaks_disabled(btn.get_active())
            self._suppress_event = False

    def on_menu_debugger_step_over_activate(self, btn: Gtk.MenuItem, *args):
        if self.breakpoint_state:
            self.editor_notebook.pull_break__step_over()

    def on_menu_debugger_step_into_activate(self, btn: Gtk.MenuItem, *args):
        if self.breakpoint_state:
            self.editor_notebook.pull_break__step_into()

    def on_menu_debugger_step_out_activate(self, btn: Gtk.MenuItem, *args):
        if self.breakpoint_state:
            self.editor_notebook.pull_break__step_out()

    def on_menu_debugger_step_next_activate(self, btn: Gtk.MenuItem, *args):
        if self.breakpoint_state:
            self.editor_notebook.pull_break__step_next()

    # MENU EMULATOR
    def on_menu_emulator_execute_activate(self, button: Gtk.CheckMenuItem, *args):
        self.on_emulator_controls_pause_clicked()

    def on_menu_emulator_reset_activate(self, button: Gtk.CheckMenuItem, *args):
        self.on_emulator_controls_reset_clicked()

    def on_menu_emulator_keyboard_controls_activate(self, button: Gtk.CheckMenuItem, *args):
        new_keyboard_cfg = KeyboardControlsDialogController(self.window).run(self._keyboard_cfg)
        if new_keyboard_cfg is not None:
            self._keyboard_cfg = new_keyboard_cfg
            self.settings.set_emulator_keyboard_cfg(self._keyboard_cfg)

    def on_menu_emulator_joystick_controls_activate(self, button: Gtk.CheckMenuItem, *args):
        if not emulator_supports_joystick():
            self.context.display_error(
                None,
                _("Joypads are not supported on macOS. Sorry!"),
            )
            return

        def update(jscfg):
            self._joystick_cfg = jscfg
            self.settings.set_emulator_joystick_cfg(self._joystick_cfg)

        JoystickControlsDialogController(self.window, self.context).run(
            self.do_poll_emulator, self._joystick_cfg, emulator_is_running(), update
        )


    def on_menu_emulator_language_jp_toggled(self, button: Gtk.RadioMenuItem):
        self.on_menu_emulator_language_XX_toggled(Language.Japanese)

    def on_menu_emulator_language_en_toggled(self, button: Gtk.RadioMenuItem):
        self.on_menu_emulator_language_XX_toggled(Language.English)

    def on_menu_emulator_language_fr_toggled(self, button: Gtk.RadioMenuItem):
        self.on_menu_emulator_language_XX_toggled(Language.French)

    def on_menu_emulator_language_de_toggled(self, button: Gtk.RadioMenuItem):
        self.on_menu_emulator_language_XX_toggled(Language.German)

    def on_menu_emulator_language_it_toggled(self, button: Gtk.RadioMenuItem):
        self.on_menu_emulator_language_XX_toggled(Language.Italian)

    def on_menu_emulator_language_es_toggled(self, button: Gtk.RadioMenuItem):
        self.on_menu_emulator_language_XX_toggled(Language.Spanish)

    def on_menu_emulator_language_XX_toggled(self, lang: Language):
        if self._suppress_event:
            return
        self.settings.set_emulator_language(lang)

    def on_menu_emulator_savestate1_activate(self, button: Gtk.CheckMenuItem, *args):
        self.on_emulator_controls_savestate1_clicked()

    def on_menu_emulator_savestate2_activate(self, button: Gtk.CheckMenuItem, *args):
        self.on_emulator_controls_savestate2_clicked()

    def on_menu_emulator_savestate3_activate(self, button: Gtk.CheckMenuItem, *args):
        self.on_emulator_controls_savestate3_clicked()

    def on_menu_emulator_loadstate1_activate(self, button: Gtk.CheckMenuItem, *args):
        self.on_emulator_controls_loadstate1_clicked()

    def on_menu_emulator_loadstate2_activate(self, button: Gtk.CheckMenuItem, *args):
        self.on_emulator_controls_loadstate2_clicked()

    def on_menu_emulator_loadstate3_activate(self, button: Gtk.CheckMenuItem, *args):
        self.on_emulator_controls_loadstate3_clicked()

    def on_menu_emulator_volume_toggled(self, button: Gtk.CheckMenuItem, *args):
        builder_get_assert(self.builder, Gtk.ToggleButton, 'emulator_controls_volume').set_active(button.get_active())

    def on_menu_emulator_screenshot_activate(self, button: Gtk.CheckMenuItem, *args):
        filter_png = Gtk.FileFilter()
        filter_png.set_name(_("PNG Image (*.png)"))
        filter_png.add_pattern("*.png")

        response, fn = self._file_chooser(Gtk.FileChooserAction.SAVE, _("Save Screenshot..."),
                                          (filter_png, self._filter_any))

        if response == Gtk.ResponseType.ACCEPT:
            fn = add_extension_if_missing(fn, 'png')
            Image.frombuffer(
                'RGBA',
                (SCREEN_WIDTH, SCREEN_HEIGHT_BOTH),
                emulator_display_buffer_as_rgbx(), 'raw', 'RGBA', 0, 1
            ).save(fn)

    # MENU HELP
    def on_menu_help_exps_docs_activate(self, btn: Gtk.MenuItem, *args):
        webbrowser.open_new_tab("https://explorerscript.readthedocs.io/en/latest/language_spec.html")

    def on_menu_help_textbox_tool_activate(self, btn: Gtk.MenuItem, *args):
        webbrowser.open_new_tab(TEXTBOX_TOOL_URL)

    def on_menu_help_about_activate(self, btn: Gtk.MenuItem, *args):
        from skytemple_ssb_debugger.ui_util import get_debugger_version
        about = builder_get_assert(self.builder, Gtk.AboutDialog, "about_dialog")
        about.connect("response", lambda d, r: d.hide())

        def activate_link(l, uri, *args):
            webbrowser.open_new_tab(uri)
            return True

        about.connect("activate-link", activate_link)
        header_bar: Optional[Gtk.HeaderBar] = about.get_header_bar()
        if header_bar is not None:
            # Cool bug??? And it only works on the left as well, wtf?
            header_bar.set_decoration_layout('close')
        about.set_version(get_debugger_version())
        about.run()

    # EMULATOR CONTROLS
    def on_emulator_controls_playstop_clicked(self, button: Gtk.Button):
        if not self._stopped:
            self.emu_stop()
        else:
            if not self.variable_controller.variables_changed_but_not_saved or self._warn_about_unsaved_vars():
                self.emu_reset()
                self.emu_resume()

    def on_emulator_controls_pause_clicked(self, *args):
        if self.emu_is_running:
            self.emu_pause()
        elif not self._stopped:
            self.emu_resume()

    def on_emulator_controls_reset_clicked(self, *args):
        self.emu_reset()
        self.emu_resume()

    def on_emulator_controls_volume_toggled(self, button: Gtk.ToggleButton):
        if self._suppress_event:
            return
        if button.get_active():
            emulator_volume_set(100)
        else:
            emulator_volume_set(0)
        self._suppress_event = True
        builder_get_assert(self.builder, Gtk.CheckMenuItem, 'menu_emulator_volume').set_active(button.get_active())
        self._suppress_event = False

    def on_emulator_controls_savestate1_clicked(self, *args):
        self.savestate(1)

    def on_emulator_controls_savestate2_clicked(self, *args):
        self.savestate(2)

    def on_emulator_controls_savestate3_clicked(self, *args):
        self.savestate(3)

    def on_emulator_controls_loadstate1_clicked(self, *args):
        self.loadstate(1)

    def on_emulator_controls_loadstate2_clicked(self, *args):
        self.loadstate(2)

    def on_emulator_controls_loadstate3_clicked(self, *args):
        self.loadstate(3)

    # OPTION TOGGLES
    def on_debug_log_cntrl_ops_toggled(self, btn: Gtk.CheckButton):
        if self.debugger:
            self.debugger.log_operations(btn.get_active())

    def on_debug_log_cntrl_script_toggled(self, btn: Gtk.CheckButton):
        if self.debugger:
            self.debugger.log_debug_print(btn.get_active())

    def on_debug_log_cntrl_internal_toggled(self, btn: Gtk.CheckButton):
        if self.debugger:
            self.debugger.log_printfs(btn.get_active())

    def on_debug_log_cntrl_ground_state_toggled(self, btn: Gtk.CheckButton):
        if self.debugger:
            self.debugger.log_ground_engine_state(btn.get_active())

    @staticmethod
    def on_debug_settings_debug_mode_toggled(btn: Gtk.CheckButton):
        emulator_set_debug_mode(btn.get_active())

    def on_debug_settings_debug_dungeon_skip_toggled(self, btn: Gtk.CheckButton):
        if self.debugger:
            self.debugger.debug_dungeon_skip(btn.get_active())

    def on_debug_settings_overlay_toggled(self, btn: Gtk.CheckButton):
        if self.debug_overlay:
            self.debug_overlay.toggle(btn.get_active())

    def on_debug_log_scroll_to_bottom_toggled(self, btn: Gtk.ToggleButton):
        self._debug_log_scroll_to_bottom = btn.get_active()

    def on_debug_log_clear_clicked(self, btn: Gtk.Button):
        buff = builder_get_assert(self.builder, Gtk.TextView, 'debug_log_textview').get_buffer()
        buff.delete(buff.get_start_iter(), buff.get_end_iter())

    # FILE TREE

    def on_ssb_file_search_search_changed(self, search: Gtk.SearchEntry):
        """Filter the main item view using the search field"""
        self._search_text = search.get_text().strip()
        self._filter__refresh_results()

    def on_ssb_file_tree_button_press_event(self, tree: Gtk.TreeView, event: Gdk.EventButton):
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            model, treeiter = tree.get_selection().get_selected()
            if treeiter is not None and model is not None:
                if model[treeiter][0] == '':
                    tree.expand_row(cast(Gtk.TreePath, model[treeiter].path), False)
                elif model[treeiter][2] == 'ssb':
                    self.editor_notebook.open_ssb(SCRIPT_DIR + '/' + model[treeiter][0])
                elif model[treeiter][2] == 'exps_macro':
                    short_path = model[treeiter][0].replace(self.context.get_project_dir() + os.path.sep, '')
                    self.editor_notebook.open_exps_macro(
                        model[treeiter][0]
                    )
                else:
                    tree.expand_row(model.get_path(treeiter), False)
        elif event.type == Gdk.EventType.BUTTON_PRESS and event.button == Gdk.BUTTON_SECONDARY:
            # Right click!
            assert self._ssb_item_filter is not None
            model = self._ssb_item_filter
            paths = tree.get_path_at_pos(int(event.x), int(event.y))
            if paths is not None:
                treepath = paths[0]
                if treepath is not None:
                    if model[treepath][2] in ['map_root', 'map_sss', 'map_sse', 'map_ssa']:
                        menu: Gtk.Menu = Gtk.Menu.new()
                        open_scene: Gtk.MenuItem = Gtk.MenuItem.new_with_label(_("Open Scenes..."))
                        open_scene.connect('activate', lambda *args: self.context.open_scene_editor_for_map(model[not_none(treepath)][0]))
                        menu.add(open_scene)
                        menu.show_all()
                        menu.popup_at_pointer(event)
                    if model[treepath][2] in ['map_sss_entry', 'ssb']:
                        menu = Gtk.Menu.new()
                        open_scene = Gtk.MenuItem.new_with_label(_("Open Scene..."))
                        open_scene.connect('activate', lambda *args: self.context.open_scene_editor(
                            self.get_scene_type_for(model[not_none(treepath)][0]), self.get_scene_name_for(model[not_none(treepath)][0])
                        ))
                        menu.add(open_scene)
                        menu.show_all()
                        menu.popup_at_pointer(event)
                    if model[treepath][2] == 'exps_macro_dir':
                        menu = Gtk.Menu.new()
                        create_dir: Gtk.MenuItem = Gtk.MenuItem.new_with_label(_("Create directory..."))
                        create_dir.connect('activate', partial(self.on_ssb_file_tree__menu_create_macro_dir, model.get_model(), model.convert_path_to_child_path(treepath)))
                        create_file: Gtk.MenuItem = Gtk.MenuItem.new_with_label(_("Create new script file..."))
                        create_file.connect('activate', partial(self.on_ssb_file_tree__menu_create_macro_file, model.get_model(), model.convert_path_to_child_path(treepath)))
                        menu.attach_to_widget(tree, None)
                        menu.add(create_dir)
                        menu.add(create_file)
                        if model[treepath][1] != _('Macros'):
                            # prevent main dir from being deleted
                            # todo: this is a bit lazy and obviously flawed...
                            delete_dir: Gtk.MenuItem = Gtk.MenuItem.new_with_label(_("Delete directory..."))
                            delete_dir.connect('activate', partial(self.on_ssb_file_tree__menu_delete_dir, model.get_model(), model.convert_path_to_child_path(treepath)))
                            menu.add(Gtk.SeparatorMenuItem.new())
                            menu.add(delete_dir)
                        menu.show_all()
                        menu.popup_at_pointer(event)
                    elif model[treepath][2] == 'exps_macro':
                        menu = Gtk.Menu.new()
                        delete_file: Gtk.MenuItem = Gtk.MenuItem.new_with_label(_("Delete script file..."))
                        delete_file.connect('activate', partial(self.on_ssb_file_tree__menu_delete_file, model.get_model(), model.convert_path_to_child_path(treepath)))
                        menu.attach_to_widget(tree, None)
                        menu.add(delete_file)
                        menu.show_all()
                        menu.popup_at_pointer(event)

    def on_ssb_file_tree__menu_create_macro_dir(self, store: Gtk.TreeStore, treepath: Gtk.TreePath, *args):
        row = store[treepath]
        response, dirname = self._show_generic_input(_('Name of the directory:'), _('Create Directory'))
        if response == Gtk.ResponseType.OK:
            abs_dirname = row[0] + os.path.sep + dirname
            os.makedirs(abs_dirname, exist_ok=True)
            store.append(store.get_iter(treepath), [abs_dirname, dirname, 'exps_macro_dir', True])

    def on_ssb_file_tree__menu_create_macro_file(self, store: Gtk.TreeStore, treepath: Gtk.TreePath, *args):
        row = store[treepath]
        response, filename = self._show_generic_input(_('Name of the new script file:'), _('Create File'))
        if len(filename) < 5 or filename[-5:] != EXPLORERSCRIPT_EXT:
            filename += EXPLORERSCRIPT_EXT
        if response == Gtk.ResponseType.OK:
            abs_filename = row[0] + os.path.sep + filename
            os.makedirs(row[0], exist_ok=True)
            with open_utf8(abs_filename, 'w') as f:
                f.write('')
            store.append(store.get_iter(treepath), [abs_filename, filename, 'exps_macro', True])

    def on_ssb_file_tree__menu_delete_dir(self, model: Gtk.TreeModel, treepath: Gtk.TreePath, *args):
        row = model[treepath]
        response = self._show_are_you_sure_delete(f(_("Do you want to delete the directory "
                                                      "{row[1]} with all of it's contents?")))
        if response == Gtk.ResponseType.DELETE_EVENT:
            shutil.rmtree(row[0])
            del model[treepath]

    def on_ssb_file_tree__menu_delete_file(self, model, treepath, *args):
        row = model[treepath]
        response = self._show_are_you_sure_delete(f(_("Do you want to delete the script file "
                                                      "{row[1]}?")))
        if response == Gtk.ResponseType.DELETE_EVENT:
            os.remove(row[0])
            del model[treepath]

    def init_file_tree(self):
        ssb_file_tree_store: Gtk.TreeStore = self._file_tree_store
        ssb_file_tree_store.clear()

        if not self._ssb_item_filter:
            self._ssb_item_filter = ssb_file_tree_store.filter_new()
            builder_get_assert(self.builder, Gtk.TreeView, 'ssb_file_tree').set_model(self._ssb_item_filter)
            assert self._ssb_item_filter is not None
            self._ssb_item_filter.set_visible_column(COL_VISIBLE)

        self._set_sensitve('ssb_file_search', True)

        script_files = self.context.load_script_files()

        # EXPLORERSCRIPT MACROS
        #    -> Macros
        macros_dir_name = self.context.get_project_macro_dir()
        macros_tree_nodes = {macros_dir_name: ssb_file_tree_store.append(
            None, [macros_dir_name, _('Macros'), 'exps_macro_dir', True]
        )}
        for root, dnames, fnames in os.walk(macros_dir_name):
            root_node = macros_tree_nodes[root]
            for dirname in dnames:
                macros_tree_nodes[root + os.path.sep + dirname] = ssb_file_tree_store.append(
                    root_node, [root + os.path.sep + dirname, dirname, 'exps_macro_dir', True]
                )
            for filename in fnames:
                if len(filename) > 4 and filename[-5:] == EXPLORERSCRIPT_EXT:
                    ssb_file_tree_store.append(root_node, [root + os.path.sep + filename, filename, 'exps_macro', True])

        # SSB SCRIPT FILES
        #    -> Common [common]
        common_root = ssb_file_tree_store.append(None, ['', _('Common'), 'common_dir', True])
        #       -> Master Script (unionall) [ssb]
        #       -> (others) [ssb]
        for name in script_files['common']:
            ssb_file_tree_store.append(common_root, ['COMMON/' + name, name, 'ssb', True])

        for i, map_obj in enumerate(script_files['maps'].values()):
            #    -> (Map Name) [map]
            map_root = ssb_file_tree_store.append(None, [map_obj['name'], map_obj['name'], 'map_root', True])
            self._registered_maps[map_obj['name']] = map_root

            enter_root = ssb_file_tree_store.append(map_root, [map_obj['name'], _('Enter (sse)'), 'map_sse', True])
            self._tree_branches[f"{map_obj['name']}_enter"] = enter_root
            if map_obj['enter_sse'] is not None:
                #          -> Script X [ssb]
                for ssb in map_obj['enter_ssbs']:
                    ssb_name = f"{map_obj['name']}/{ssb}"
                    self._scene_types[ssb_name] = 'sse'
                    self._scene_names[ssb_name] = f"{map_obj['name']}/enter.sse"
                    ssb_file_tree_store.append(enter_root, [ssb_name, ssb, 'ssb', True])

            #       -> Acting Scripts [lsd]
            acting_root = ssb_file_tree_store.append(map_root, [map_obj['name'], _('Acting (ssa)'), 'map_ssa', True])
            self._tree_branches[f"{map_obj['name']}_acting"] = acting_root
            for __, ssb in map_obj['ssas']:
                #             -> Script [ssb]
                ssb_name = f"{map_obj['name']}/{ssb}"
                self._scene_types[ssb_name] = 'ssa'
                self._scene_names[ssb_name] = ssb_name
                ssb_file_tree_store.append(acting_root, [ssb_name, ssb, 'ssb', True])

            #       -> Sub Scripts [sub]
            sub_root = ssb_file_tree_store.append(map_root, [map_obj['name'], _('Sub (sss)'), 'map_sss', True])
            self._tree_branches[f"{map_obj['name']}_subroot"] = sub_root
            for sss, ssbs in map_obj['subscripts'].items():
                #          -> (name) [sub_entry]
                sss_name = f"{map_obj['name']}/{sss}"
                self._scene_types[sss_name] = 'sss'
                self._scene_names[sss_name] = sss_name
                sub_entry = ssb_file_tree_store.append(sub_root, [sss_name, sss, 'map_sss_entry', True])
                self._tree_branches[sss_name.replace('/', '_')] = sub_entry
                for ssb in ssbs:
                    #             -> Script X [ssb]
                    ssb_name = f"{map_obj['name']}/{ssb}"
                    self._scene_types[ssb_name] = 'sss'
                    self._scene_names[ssb_name] = sss_name
                    ssb_file_tree_store.append(sub_entry, [ssb_name, ssb, 'ssb', True])

    # CODE EDITOR NOTEBOOK
    def on_code_editor_notebook_switch_page(self, wdg, page, *args):
        self.editor_notebook.on_page_changed(page)

    # GLOBAL STATE VIEW

    def on_spin_alloc_table_nb_value_changed(self, widget):
        try:
            val = int(widget.get_text())
        except ValueError:
            val = -1
        self.global_state_controller.change_current_table(val)
        
    def on_global_state_reload_clicked(self, *args):
        self.global_state_controller.sync()
        
    def on_global_state_alloc_dump_clicked(self, *args):
        active_rows: List[Gtk.TreePath] = builder_get_assert(self.builder, Gtk.TreeView, 'global_state_alloc_treeview').get_selection().get_selected_rows()[1]
        if len(active_rows) >= 1:
            def do_dump(data):
                dialog = Gtk.FileChooserNative.new(
                    _("Save dumped block..."),
                    self.window,
                    Gtk.FileChooserAction.SAVE,
                    _('_Save'), None
                )

                response = dialog.run()
                fn = dialog.get_filename()
                dialog.destroy()

                if response == Gtk.ResponseType.ACCEPT and fn is not None:
                    with open(fn, 'wb') as f:
                        f.write(data)

            self.global_state_controller.dump(active_rows[0].get_indices()[0], do_dump)

    # VARIABLES VIEW

    def on_variables_reload_clicked(self, *args):
        self.variable_controller.sync()

    def on_variables_load1_clicked(self, *args):
        if self.context.is_project_loaded():
            self.variable_controller.load(1, self.context.get_project_debugger_dir())
            self.variable_controller.sync()

    def on_variables_load2_clicked(self, *args):
        if self.context.is_project_loaded():
            self.variable_controller.load(2, self.context.get_project_debugger_dir())
            self.variable_controller.sync()

    def on_variables_load3_clicked(self, *args):
        if self.context.is_project_loaded():
            self.variable_controller.load(3, self.context.get_project_debugger_dir())
            self.variable_controller.sync()

    def on_variables_save1_clicked(self, *args):
        if self.context.is_project_loaded():
            self.variable_controller.save(1, self.context.get_project_debugger_dir())

    def on_variables_save2_clicked(self, *args):
        if self.context.is_project_loaded():
            self.variable_controller.save(2, self.context.get_project_debugger_dir())

    def on_variables_save3_clicked(self, *args):
        if self.context.is_project_loaded():
            self.variable_controller.save(3, self.context.get_project_debugger_dir())

    def on_main_window_configure_event(self, *args):
        """Save the window size and position to the settings store"""
        # We delay handling this, to make sure we only handle it when the user is done resizing/moving.
        if self._resize_timeout_id is not None:
            GLib.source_remove(self._resize_timeout_id)
        self._resize_timeout_id = GLib.timeout_add_seconds(1, self.on_main_window_configure_event__handle)

    def on_main_window_configure_event__handle(self):
        self.settings.set_window_position(self.window.get_position())
        self.settings.set_window_size(self.window.get_size())
        self._resize_timeout_id = None

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
                assert self.debugger
                ges = self.debugger.ground_engine_state
                if ges:
                    ss: ScriptRuntimeStruct
                    if script_entity_type == SsbRoutineType.GENERIC:
                        ss = ges.global_script.script_struct
                    elif script_entity_type == SsbRoutineType.ACTOR:
                        ss = ges.get_actor(script_entity_id).script_struct  # type: ignore
                    elif script_entity_type == SsbRoutineType.OBJECT:
                        ss = ges.get_object(script_entity_id).script_struct  # type: ignore
                    elif script_entity_type == SsbRoutineType.PERFORMER:
                        ss = ges.get_performer(script_entity_id).script_struct  # type: ignore
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
    def uninit_project(self):
        if not self.editor_notebook.close_all_tabs():
            return
        self.global_state_controller.uninit()
        self.variable_controller.uninit()
        if self.debugger:
            self.debugger.disable()
        self.rom_was_loaded = False

    def load_rom(self):
        try:
            # Unload old ROM first
            if self.rom_was_loaded:
                self.uninit_project()
            self.ssb_fm = SsbFileManager(self.context)
            fn = self.context.get_rom_filename()
            emulator_debug_init_breakpoint_manager(
                os.path.join(self.context.get_project_debugger_dir(), f'{os.path.basename(fn)}.breakpoints.json')
            )
            # Immediately save, because the module packs the ROM differently.
            self.context.save_rom()
            rom_data = self.context.get_static_data()
            if self.debugger:
                fl1 = []
                fl2 = []
                for i in range(0, 12):
                    fl1.append(builder_get_assert(self.builder, Gtk.CheckButton, f"chk_debug_flag_1_{i}").get_active())
                for j in range(0, 16):
                    fl2.append(builder_get_assert(self.builder, Gtk.CheckButton, f"chk_debug_flag_2_{j}").get_active())
                self.debugger.enable(
                    rom_data, self.ssb_fm, self.on_ground_engine_start,
                    debug_mode=builder_get_assert(self.builder, Gtk.CheckButton, 'debug_settings_debug_mode').get_active(),
                    debug_flag_1=fl1, debug_flag_2=fl2
                )
            self.init_file_tree()
            self.global_state_controller.init(rom_data)
            self.variable_controller.init(rom_data)
            self.local_variable_controller.init(rom_data)
            self.editor_notebook.init(self.ssb_fm, rom_data)
            self.rom_was_loaded = True
        except BaseException as ex:
            self.context.display_error(
                sys.exc_info(),
                f"Unable to load: {self.context.get_rom_filename()}\n{ex}"
            )
            self.ssb_fm = None
        else:
            self.enable_editing_features()
            self.enable_debugging_features()
            self.emu_stop()

    def enable_editing_features(self):
        code_editor_main = builder_get_assert(self.builder, Gtk.Box, 'code_editor_main')
        code_editor_notebook = builder_get_assert(self.builder, Gtk.Notebook, 'code_editor_notebook')
        code_editor_main.remove(builder_get_assert(self.builder, Gtk.Widget, 'main_label'))
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

    def load_debugger_state(
            self,
            breaked_for: Optional[ScriptRuntimeStruct] = None,
            file_state: Optional[BreakpointFileState] = None,
            local_vars_values: Optional[Sequence[int]] = None
    ):
        self.toggle_paused_debugging_features(True)
        # Load Ground State
        self.ground_state_controller.sync(self.editor_notebook, breaked_for)
        # This will show the local and macro variables
        if local_vars_values and file_state:
            self.local_variable_controller.sync(local_vars_values, file_state)
        else:
            self.local_variable_controller.disable()

    def savestate(self, i: int):
        """Save both the emulator state and the ground engine state to files."""
        if not self.context.is_project_loaded():
            return
        try:
            #if self.breakpoint_state.is_stopped():
            #    raise RuntimeError("Savestates can not be created while debugging.")
            rom_basename = os.path.basename(self.context.get_rom_filename())
            desmume_savestate_path = os.path.join(
                self.context.get_project_debugger_dir(), f'{rom_basename}.save.{i}.{SAVESTATE_EXT_DESUME}'
            )
            ground_engine_savestate_path = os.path.join(
                self.context.get_project_debugger_dir(), f'{rom_basename}.save.{i}.{SAVESTATE_EXT_GROUND_ENGINE}'
            )

            with open_utf8(ground_engine_savestate_path, 'w') as f:
                assert self.debugger and self.debugger.ground_engine_state
                json.dump(self.debugger.ground_engine_state.serialize(), f)
            emulator_savestate_save_file(desmume_savestate_path)
        except BaseException as err:
            self.context.display_error(
                sys.exc_info(),
                str(err),
                _("Unable to save savestate!")
            )
            return

    def loadstate(self, i: int):
        """Loads both the emulator state and the ground engine state from files."""
        if not self.context.is_project_loaded():
            return
        rom_basename = os.path.basename(self.context.get_rom_filename())
        desmume_savestate_path = os.path.join(
            self.context.get_project_debugger_dir(), f'{rom_basename}.save.{i}.{SAVESTATE_EXT_DESUME}'
        )
        ground_engine_savestate_path = os.path.join(
            self.context.get_project_debugger_dir(), f'{rom_basename}.save.{i}.{SAVESTATE_EXT_GROUND_ENGINE}'
        )

        assert self.debugger
        if os.path.exists(ground_engine_savestate_path):
            try:
                was_running = emulator_is_running()
                self._stopped = False
                self.emu_reset()
                emulator_savestate_load_file(desmume_savestate_path)
                with open_utf8(ground_engine_savestate_path, 'r') as f:
                    self.debugger.ground_engine_state.deserialize(json.load(f))  # type: ignore
                self.emu_is_running = emulator_is_running()
                self.load_debugger_state()
                self.variable_controller.sync()
                if was_running:
                    self._set_buttons_running()
                else:
                    self._set_buttons_paused()
            except BaseException as ex:
                self.context.display_error(
                    sys.exc_info(),
                    str(ex),
                    _("Unable to load savestate!")
                )
                return

    def set_touch_pos(self, x: int, y: int):
        assert self.renderer
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

        emulator_touch_set_pos(int(emu_x), int(emu_y))

    def lookup_key(self, keyval):
        key = 0
        for i in range(0, EmulatorKeys.NB_KEYS):
            if keyval == self._keyboard_cfg[i]:
                key = emulator_keymask(i + 1)
                break
        return key

    def emu_reset(self):
        if self.breakpoint_state:
            self.breakpoint_state.fail_hard()
        loaded_overl_grp1_addr = 0
        script_vars_addr = 0
        script_vars_local_addr = 0
        global_script_var_values = 0
        game_state_values = 0
        language_info_data = 0
        game_mode = 0
        debug_special_episode_number = 0
        notify_note = 0
        if self.debugger and self.debugger.ground_engine_state:
            self.debugger.ground_engine_state.reset(fully=True)
            assert self.debugger.rom_data is not None
            arm9data = self.debugger.rom_data.bin_sections.arm9.data
            ramdata = self.debugger.rom_data.bin_sections.ram.data
            loaded_overl_grp1_addr = arm9data.LOADED_OVERLAY_GROUP_1.absolute_address
            script_vars_addr = arm9data.SCRIPT_VARS.absolute_address
            script_vars_local_addr = arm9data.SCRIPT_VARS_LOCALS.absolute_address

            global_script_var_values = ramdata.SCRIPT_VARS_VALUES.absolute_address
            game_state_values = arm9data.GAME_STATE_VALUES.absolute_address
            language_info_data = arm9data.LANGUAGE_INFO_DATA.absolute_address
            game_mode = arm9data.GAME_MODE.absolute_address
            debug_special_episode_number = ramdata.DEBUG_SPECIAL_EPISODE_NUMBER.absolute_address
            notify_note = arm9data.NOTIFY_NOTE.absolute_address
        try:
            lang = self.settings.get_emulator_language()
            if lang:
                emulator_set_language(lang)
            emulator_open_rom(
                self.context.get_rom_filename(),

                address_loaded_overlay_group_1=u32(loaded_overl_grp1_addr),
                global_variable_table_start_addr=u32(script_vars_addr),
                local_variable_table_start_addr=u32(script_vars_local_addr),
                global_script_var_values=u32(global_script_var_values),
                game_state_values=u32(game_state_values),
                language_info_data=u32(language_info_data),
                game_mode=u32(game_mode),
                debug_special_episode_number=u32(debug_special_episode_number),
                notify_note=u32(notify_note),
            )
            self.emu_is_running = emulator_is_running()
        except RuntimeError:
            self.context.display_error(
                sys.exc_info(),
                f"Emulator failed to load: {self.context.get_rom_filename()}"
            )

    def emu_resume(self, state_type=BreakpointStateType.Resume, step_manual_addr=None):
        """Resume the emulator. If the debugger is currently breaked, the state will transition to state_type."""
        self._stopped = False
        self.toggle_paused_debugging_features(False)
        self.clear_info_bar()
        self._set_buttons_running()
        if not self._emu_is_running:
            emulator_resume()
        if self.breakpoint_state and state_type == BreakpointStateType.StepManual:
            self.breakpoint_state.step_manual(step_manual_addr)
        elif self.breakpoint_state:
            self.breakpoint_state.transition(state_type)
        else:
            emulator_unpress_all_keys()
        self.emu_is_running = True

    def emu_stop(self):
        self._stopped = True
        if self.breakpoint_state:
            self.breakpoint_state.fail_hard()
        emulator_reset()
        emulator_pause()
        self.emu_is_running = False

        self._set_buttons_stopped()
        self.load_debugger_state()
        self.write_info_bar(Gtk.MessageType.WARNING, _("The game is stopped."))

    def emu_pause(self):
        if self.breakpoint_state and self.breakpoint_state.is_stopped():
            # This shouldn't happen...? It would lead to an invalid state, so just return.
            return
        if self.emu_is_running:
            emulator_pause()
        self.load_debugger_state()
        self.write_info_bar(Gtk.MessageType.INFO, _("The game is paused."))

        self._set_buttons_paused()
        self.emu_is_running = False

    def on_ground_engine_start(self):
        """The ground engine started"""
        # TODO: This is more a quick fix for some issue with the variable syncing.
        self.variable_controller.sync()

    def on_ground_engine_stop(self):
        """The ground engine stopped"""
        # TODO: This is more a quick fix for some issue with the variable syncing.
        self.variable_controller.sync()

    def on_script_added(self, ssb_path, mapname, scene_type, scene_name):
        """Handle a newly added SSB file."""
        ssb_path = ssb_path.replace(SCRIPT_DIR + '/', '')
        if scene_type == 'sse':
            branch_name = f'{mapname}_enter'
        elif scene_type == 'ssa':
            branch_name = f'{mapname}_acting'
        elif scene_type == 'sss':
            branch_name = f'{mapname}_{scene_name}'
        else:
            return  # todo: raise error?
        ssb_file_tree_store: Gtk.TreeStore = self._file_tree_store
        if branch_name not in self._tree_branches:
            self._create_tree_branch(*branch_name.split('_')[0:2])
        self._scene_types[ssb_path] = scene_type
        self._scene_names[ssb_path] = f'{mapname}/{scene_name}'
        ssb_file_tree_store.append(self._tree_branches[branch_name], [
            ssb_path, ssb_path.split('/')[-1], 'ssb', True
        ])

    def _create_tree_branch(self, mapname, branch):
        # TODO: Refactor class to only use this method for tree branch creation.
        if mapname not in self._registered_maps:
            map_root = self._file_tree_store.append(None, [mapname, mapname, 'map_root', True])
            self._registered_maps[mapname] = map_root
        map_root = self._registered_maps[mapname]

        if branch == 'enter':
            enter_root = self._file_tree_store.append(map_root, [mapname, _('Enter (sse)'), 'map_sse', True])
            self._tree_branches[f"{mapname}_enter"] = enter_root
        elif branch == 'acting':
            acting_root = self._file_tree_store.append(map_root, [mapname, _('Acting (ssa)'), 'map_ssa', True])
            self._tree_branches[f"{mapname}_acting"] = acting_root
        else:
            if f'{mapname}_subroot' not in self._tree_branches:
                sub_root = self._file_tree_store.append(map_root, [mapname, _('Sub (sss)'), 'map_sss', True])
                self._tree_branches[f"{mapname}_subroot"] = sub_root
            sub_root = self._tree_branches[f"{mapname}_subroot"]
            sss_name = f"{mapname}/{branch.replace('_','/')}"
            self._scene_types[sss_name] = 'sss'
            self._scene_names[sss_name] = sss_name
            sub_entry = self._file_tree_store.append(sub_root, [sss_name, branch.replace('_', '/'), 'map_sss_entry', True])
            self._tree_branches[sss_name.replace('/', '_')] = sub_entry

    def on_script_removed(self, ssb_path):
        """Handle a SSB file removal."""
        # todo

    # Debug Flags Checkbox
    def on_chk_debug_flag_1_toggled(self, w):
        emulator_set_debug_flag_1(int(w.get_name()[len("chk_debug_flag_1_"):]), w.get_active())
    def on_chk_debug_flag_2_toggled(self, w):
        emulator_set_debug_flag_2(int(w.get_name()[len("chk_debug_flag_2_"):]), w.get_active())

    def set_check_debug_flag(self, var_id, flag_id, value):
        builder_get_assert(self.builder, Gtk.CheckButton, f"chk_debug_flag_{var_id}_{flag_id}").set_active(bool(value))

    def break_pulled(self, state: BreakpointState):
        """
        The DebuggerController has paused at an instruction.
        - Update reference to state object.
        - Update the main UI (info bar, emulator controls).
        - Tell the GroundStateController about the hanger, to mark it in the list.
        - Tell the code editor about which file to open and which instruction to jump to.
        - Add release hook.
        """
        assert self.ssb_fm
        assert self.debugger and self.debugger.rom_data
        srs = ScriptRuntimeStruct.from_data(
            self.debugger.rom_data,
            state.script_runtime_struct_addr,
            state.script_runtime_struct_mem,
            state.script_target_slot_id
        )
        emulator_volume_set(0)

        ssb = self.debugger.ground_engine_state.loaded_ssb_files[state.hanger_id]  # type: ignore
        opcode_addr = srs.current_opcode_addr_relative
        self.breakpoint_state = state
        self._set_buttons_paused()

        # Build the breakpoint file state: This state object controls which source file is handling the breakpoint
        # and whether we are currently halted on a macro call
        breakpoint_file_state = BreakpointFileState(ssb.file_name, opcode_addr, state)
        breakpoint_file_state.process(
            self.ssb_fm.get(ssb.file_name), opcode_addr, self._enable_explorerscript,
            self.context.get_project_filemanager()
        )
        state.file_state = breakpoint_file_state

        self.write_info_bar(Gtk.MessageType.WARNING, f(_("The debugger is halted at {ssb.file_name}.")))
        # This will mark the hanger as being breaked:
        self.debugger.ground_engine_state.break_pulled(state)  # type: ignore
        # This will tell the code editor to refresh the debugger controls for all open editors
        self.editor_notebook.break_pulled(state)
        self.editor_notebook.focus_by_opcode_addr(ssb.file_name, opcode_addr)
        self.load_debugger_state(srs, breakpoint_file_state, state.local_vars_values)
        self.debug_overlay.break_pulled()  # type: ignore

        state.add_release_hook(self.break_released)

    def step_into_macro_call(self, file_state: BreakpointFileState):
        """Step into a macro call, by simulating it via the BreakpointFileState."""
        assert self.debugger
        file_state.step_into_macro_call()
        assert file_state.parent is not None
        assert self.debugger.ground_engine_state is not None
        assert self.debugger.rom_data is not None
        self.debugger.ground_engine_state.step_into_macro_call(file_state.parent)
        self.editor_notebook.step_into_macro_call(file_state)
        self.editor_notebook.focus_by_opcode_addr(file_state.ssb_filename, file_state.opcode_addr)
        srs = ScriptRuntimeStruct.from_data(
            self.debugger.rom_data,
            file_state.parent.script_runtime_struct_addr,
            file_state.parent.script_runtime_struct_mem,
            file_state.parent.script_target_slot_id
        )
        self.load_debugger_state(srs, file_state, file_state.parent.local_vars_values)

    def break_released(self, state: BreakpointState):
        """
        The BreakpointState went into a resuming state (hook added via BreakpointState.add_release_hook).
        - Delete local reference to state object
        - Update the main UI (info bar, emulator controls).
        - The ground state controller and code editors have their own hooks for the releasing.
        """
        assert self.debug_overlay
        if self.global_state__audio_enabled:
            emulator_volume_set(100)
        self.breakpoint_state = None
        self._set_buttons_running()
        self.toggle_paused_debugging_features(False)
        self.clear_info_bar()
        # This is faster than syncing the entire debugger state again.
        self.ground_state_controller.sync_break_hanger()
        self.debug_overlay.break_released()

    def get_scene_name_for(self, ssb_rom_path):
        """Try to find the ssb file's scene name. if not found, returns an empty string"""
        ssb_rom_path = ssb_rom_path.replace('SCRIPT/', '')
        if ssb_rom_path in self._scene_names :
            return self._scene_names[ssb_rom_path]
        return ''

    def get_scene_type_for(self, ssb_rom_path):
        """Try to find the ssb file's scene type. if not found, returns an empty string"""
        ssb_rom_path = ssb_rom_path.replace('SCRIPT/', '')
        if ssb_rom_path in self._scene_types :
            return self._scene_types[ssb_rom_path]
        return ''

    def toggle_boost(self, state):
        emulator_set_boost(state)
        if self.debug_overlay:
            self.debug_overlay.set_boost(state)
        if self.debugger:
            self.debugger.set_boost(state)
        if self.variable_controller:
            self.variable_controller.set_boost(state)
        if self.renderer:
            self.renderer.set_boost(state)

    # TODO: CODE DUPLICATION BETWEEN SKYTEMPLE AND SSB DEBUGGER -- If we ever make a common package, this must go into it!
    def _filter__refresh_results(self):
        """Filter the main item view"""
        item_store = self._file_tree_store
        if self._search_text == "":
            item_store.foreach(self._filter__reset_row, True)
        else:
            builder_get_assert(self.builder, Gtk.TreeView, 'ssb_file_tree').collapse_all()
            item_store.foreach(self._filter__reset_row, False)
            item_store.foreach(self._filter__show_matches)
            assert self._ssb_item_filter is not None
            self._ssb_item_filter.foreach(self._filter__expand_all_visible)

    def _filter__reset_row(self, model, path, iter, make_visible):
        """Change the visibility of the given row"""
        model[iter][COL_VISIBLE] = make_visible

    def _filter__make_path_visible(self, model, iter):
        """Make a row and its ancestors visible"""
        while iter:
            model[iter][COL_VISIBLE] = True
            iter = model.iter_parent(iter)

    def _filter__make_subtree_visible(self, model, iter):
        """Make descendants of a row visible"""
        for i in range(model.iter_n_children(iter)):
            subtree = model.iter_nth_child(iter, i)
            if model[subtree][COL_VISIBLE]:
                # Subtree already visible
                continue
            model[subtree][COL_VISIBLE] = True
            self._filter__make_subtree_visible(model, subtree)

    def _filter__expand_all_visible(self, model: Gtk.TreeStore, path, iter):
        """
        This is super annoying. Because of the two different "views" on the model,
        we can't do this in show_matches, because we have to use the filter model here!
        """
        if self._search_text:
            search_query = self._search_text.lower()
            text = model[iter][1].lower()
            ssb_file_tree = builder_get_assert(self.builder, Gtk.TreeView, 'ssb_file_tree')
            if search_query in text:
                ssb_file_tree.expand_to_path(path)

    def _filter__show_matches(self, model: Gtk.TreeStore, path, iter):
        if self._search_text:
            search_query = self._search_text.lower()
            text = model[iter][1].lower()
            if search_query in text:
                # Propagate visibility change up
                self._filter__make_path_visible(model, iter)
                # Propagate visibility change down
                self._filter__make_subtree_visible(model, iter)
    # END CODE DUPLICATION

    def _set_sensitve(self, name, state):
        w = builder_get_assert(self.builder, Gtk.Widget, name)
        w.set_sensitive(state)

    def _file_chooser(self, type: Gtk.FileChooserAction, name, filter):
        dialog = Gtk.FileChooserNative.new(
            name,
            self.window,
            type,
            None, None
        )
        for f in filter:
            dialog.add_filter(f)

        response = dialog.run()
        fn = dialog.get_filename()
        dialog.destroy()

        return response, fn

    def _debugger_print_callback(self, string):
        textview = builder_get_assert(self.builder, Gtk.TextView, 'debug_log_textview')
        textview.get_buffer().insert(textview.get_buffer().get_end_iter(), string + '\n')

        if self._debug_log_scroll_to_bottom:
            self._suppress_event = True
            textview.scroll_to_mark(self._debug_log_textview_right_marker, 0, True, 0, 0)
            self._suppress_event = False

    def _warn_about_unsaved_vars(self):
        md = self.context.message_dialog(
            self.window,
            Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.WARNING,
            Gtk.ButtonsType.OK_CANCEL,
            _("You have unsaved changes to variables.\n"
              "Variables are reset when the game is rebooted.\n"
              "You need to save the variables and load them after boot.\n\n"
              "Do you still want to continue?"),
            title=_("Warning!")
        )

        response = md.run()
        md.destroy()

        if response == Gtk.ResponseType.OK:
            self.variable_controller.variables_changed_but_not_saved = False
            return True
        return False

    def write_info_bar(self, message_type: Gtk.MessageType, text: str):
        info_bar = builder_get_assert(self.builder, Gtk.InfoBar, 'info_bar')
        info_bar_label = builder_get_assert(self.builder, Gtk.Label, 'info_bar_label')
        info_bar_label.set_text(text)
        info_bar.set_message_type(message_type)
        info_bar.set_revealed(True)

    def clear_info_bar(self):
        info_bar = builder_get_assert(self.builder, Gtk.InfoBar, 'info_bar')
        info_bar.set_revealed(False)

    def _set_buttons_running(self):
        btn = builder_get_assert(self.builder, Gtk.Button, 'emulator_controls_playstop')
        if builder_get_assert(self.builder, Gtk.Image, 'img_play').get_parent():
            btn.remove(builder_get_assert(self.builder, Gtk.Image, 'img_play'))
            btn.add(builder_get_assert(self.builder, Gtk.Image, 'img_stop'))
        btn = builder_get_assert(self.builder, Gtk.Button, 'emulator_controls_pause')
        if builder_get_assert(self.builder, Gtk.Image, 'img_play2').get_parent():
            btn.remove(builder_get_assert(self.builder, Gtk.Image, 'img_play2'))
            btn.add(builder_get_assert(self.builder, Gtk.Image, 'img_pause'))

    def _set_buttons_stopped(self):
        btn = builder_get_assert(self.builder, Gtk.Button, 'emulator_controls_playstop')
        if builder_get_assert(self.builder, Gtk.Image, 'img_stop').get_parent():
            btn.remove(builder_get_assert(self.builder, Gtk.Image, 'img_stop'))
            btn.add(builder_get_assert(self.builder, Gtk.Image, 'img_play'))
        btn = builder_get_assert(self.builder, Gtk.Button, 'emulator_controls_pause')
        if builder_get_assert(self.builder, Gtk.Image, 'img_play2').get_parent():
            btn.remove(builder_get_assert(self.builder, Gtk.Image, 'img_play2'))
            btn.add(builder_get_assert(self.builder, Gtk.Image, 'img_pause'))

    def _set_buttons_paused(self):
        btn: Gtk.Button = builder_get_assert(self.builder, Gtk.Button, 'emulator_controls_pause')
        if builder_get_assert(self.builder, Gtk.Image, 'img_pause').get_parent():
            btn.remove(builder_get_assert(self.builder, Gtk.Image, 'img_pause'))
            btn.add(builder_get_assert(self.builder, Gtk.Image, 'img_play2'))
        btn = builder_get_assert(self.builder, Gtk.Button, 'emulator_controls_playstop')
        if builder_get_assert(self.builder, Gtk.Image, 'img_play').get_parent():
            btn.remove(builder_get_assert(self.builder, Gtk.Image, 'img_play'))
            btn.add(builder_get_assert(self.builder, Gtk.Image, 'img_stop'))

    def _show_are_you_sure_delete(self, text):
        dialog: Gtk.MessageDialog = self.context.message_dialog(
            self.window,
            Gtk.DialogFlags.MODAL,
            Gtk.MessageType.WARNING,
            Gtk.ButtonsType.NONE, text
        )
        dont_save: Gtk.Widget = dialog.add_button(_("Delete"), Gtk.ResponseType.DELETE_EVENT)
        dont_save.get_style_context().add_class('destructive-action')
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.format_secondary_text(_('You will not be able to restore it.'))
        response = dialog.run()
        dialog.destroy()
        return response

    def _show_generic_input(self, label_text, ok_text):
        dialog = builder_get_assert(self.builder, Gtk.Dialog, 'generic_input_dialog')
        entry = builder_get_assert(self.builder, Gtk.Entry, 'generic_input_dialog_entry')
        label = builder_get_assert(self.builder, Gtk.Label, 'generic_input_dialog_label')
        label.set_text(label_text)
        btn_cancel = dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        btn = dialog.add_button(ok_text, Gtk.ResponseType.OK)
        btn.set_can_default(True)
        btn.grab_default()
        entry.set_activates_default(True)
        response = dialog.run()
        dialog.hide()
        assert_not_none(cast(Optional[Gtk.Container], btn.get_parent())).remove(btn)
        assert_not_none(cast(Optional[Gtk.Container], btn_cancel.get_parent())).remove(btn_cancel)
        return response, entry.get_text()


T = TypeVar('T')


def not_none(x: Optional[T]) -> T:
    return cast(T, x)
