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

"""
TODO:
- Running scripts
- Creating new ssb files [-> only via SkyTemple]
- Psy's list patch [SkyTemple]
"""
import logging
import os

import gi

from desmume.emulator import DeSmuME
from skytemple_ssb_debugger.controller.main import MainController
from skytemple_ssb_debugger.emulator_thread import EmulatorThread

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GLib
from gi.repository.Gtk import Window


def main():
    try:
        path = os.path.abspath(os.path.dirname(__file__))

        itheme: Gtk.IconTheme = Gtk.IconTheme.get_default()
        itheme.append_search_path(os.path.abspath(os.path.join(path, "data", "icons")))
        itheme.rescan_if_needed()

        # Load Builder and Window
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(path, "debugger.glade"))
        main_window: Window = builder.get_object("main_window")
        main_window.set_role("SkyTemple Script Engine Debugger")
        GLib.set_application_name("SkyTemple Script Engine Debugger")
        GLib.set_prgname("skytemple_ssb_debugger")
        # TODO: Deprecated but the only way to set the app title on GNOME...?
        main_window.set_wmclass("SkyTemple Script Engine Debugger", "SkyTemple Script Engine Debugger")

        # Load main window + controller
        MainController(builder, main_window)

        Gtk.main()
    finally:
        if EmulatorThread.instance():
            EmulatorThread.instance().stop()


if __name__ == '__main__':
    # TODO: At the moment doesn't support any cli arguments.
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    main()
