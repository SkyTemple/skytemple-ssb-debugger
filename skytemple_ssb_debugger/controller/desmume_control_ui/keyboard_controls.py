#  Copyright 2020-2022 Capypara and the SkyTemple Contributors
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
import os
from typing import Optional, List

from gi.repository import Gtk, Gdk
from skytemple_ssb_emulator import emulator_get_key_names, EmulatorKeys

from skytemple_ssb_debugger.controller.desmume_control_ui import key_names_localized, widget_to_primitive
from skytemple_ssb_debugger.ui_util import builder_get_assert, assert_not_none


class KeyboardControlsDialogController:
    """This dialog shows the keyboard controls."""
    def __init__(self, parent_window: Gtk.Window):
        path = os.path.abspath(os.path.dirname(__file__))
        # SkyTemple translation support
        try:
            from skytemple.core.ui_utils import make_builder  # type: ignore
            self.builder = make_builder(os.path.join(path, "PyDeSmuMe_controls.glade"))  # type: ignore
        except ImportError:
            self.builder = Gtk.Builder()
            self.builder.add_from_file(os.path.join(path, "PyDeSmuMe_controls.glade"))
        self.window = builder_get_assert(self.builder, Gtk.Dialog, 'wKeybConfDlg')
        self.window.set_transient_for(parent_window)
        self.window.set_attached_to(parent_window)
        self._keyboard_cfg: list[int] | None = None
        self._tmp_key: int | None = None
        self.builder.connect_signals(self)

    def run(self, keyboard_cfg: list[int]) -> list[int] | None:
        """Configure the keyboard configuration provided using the dialog,
        returns the new keyboard config if changed, else None."""
        self._keyboard_cfg = keyboard_cfg.copy()
        key_names = emulator_get_key_names()
        for i in range(0, EmulatorKeys.NB_KEYS):
            b = builder_get_assert(self.builder, Gtk.Button, f"button_{key_names[i]}")
            b.set_label(f"{key_names_localized[i]} : {Gdk.keyval_name(self._keyboard_cfg[i])}")
        response = self.window.run()

        self.window.hide()
        if response == Gtk.ResponseType.OK:
            return self._keyboard_cfg
        return None

    # KEYBOARD CONFIG / KEY DEFINITION
    def on_wKeyDlg_key_press_event(self, widget: Gtk.Widget, event: Gdk.EventKey, *args):
        self._tmp_key = event.keyval
        builder_get_assert(self.builder, Gtk.Label, "label_key").set_text(
            assert_not_none(Gdk.keyval_name(self._tmp_key))
        )
        return True

    def on_button_kb_key_clicked(self, w, *args):
        key = widget_to_primitive(w)
        dlg = builder_get_assert(self.builder, Gtk.Dialog, "wKeyDlg")
        key -= 1  # key = bit position, start with
        assert self._keyboard_cfg is not None
        self._tmp_key = self._keyboard_cfg[key]
        assert self._tmp_key is not None
        builder_get_assert(self.builder, Gtk.Label, "label_key").set_text(assert_not_none(
            Gdk.keyval_name(self._tmp_key)
        ))
        if dlg.run() == Gtk.ResponseType.OK:
            self._keyboard_cfg[key] = self._tmp_key
            builder_get_assert(self.builder, Gtk.Button, f"button_{emulator_get_key_names()[key]}").set_label(f"{key_names_localized[key]} : {Gdk.keyval_name(self._tmp_key)}")

        dlg.hide()

    # Joystick configuration / Key definition
    def on_button_joy_key_clicked(self, w, *args):
        pass  # not part of this

    def gtk_widget_hide_on_delete(self, w: Gtk.Widget, *args):
        w.hide_on_delete()
        return True
