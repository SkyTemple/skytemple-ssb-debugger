#  Copyright 2020-2024 Capypara and the SkyTemple Contributors
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

from gi.repository import Adw, Gio, GLib

from skytemple_ssb_debugger.context.standalone import StandaloneDebuggerControlContext
from skytemple_ssb_debugger.widget.application_window import SkyTempleSsbDebuggerAppWindow

SKYTEMPLE_DEV = "SKYTEMPLE_DEV" in os.environ


class SkyTempleSsbDebuggerApp(Adw.Application):
    development_mode: bool

    def __init__(self):
        # Load Builder and Window
        app_id = "org.skytemple.SsbDebugger.Devel" if SKYTEMPLE_DEV else "org.skytemple.SsbDebugger"
        super().__init__(application_id=app_id, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.connect("open", self.on_open)
        GLib.set_application_name("SkyTemple Randomizer")
        self.development_mode = SKYTEMPLE_DEV
        self.context = StandaloneDebuggerControlContext()

    def do_activate(self, file: str | None = None) -> None:
        # TODO: Do something with file
        window = SkyTempleSsbDebuggerAppWindow(application=self, context=self.context)
        if file is not None:
            window.open_file(file)
        window.present()

    def on_open(self, _, files: list[Gio.File], *args):
        self.do_activate(files[0].get_path())
