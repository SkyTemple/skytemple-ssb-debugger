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

import logging
import os
import sys

import gi
import pkg_resources

gi.require_version('Gtk', '3.0')

from skytemple_icons import icons
from skytemple_ssb_debugger.context.standalone import StandaloneDebuggerControlContext
from skytemple_ssb_debugger.controller.main import MainController
from skytemple_ssb_debugger.emulator_thread import EmulatorThread

from gi.repository import Gtk, GLib
from gi.repository.Gtk import Window


def main():
    try:
        if sys.platform.startswith('win'):
            # Load theming under Windows
            _windows_load_theme()

        itheme: Gtk.IconTheme = Gtk.IconTheme.get_default()
        itheme.append_search_path(os.path.abspath(icons()))
        itheme.append_search_path(os.path.abspath(os.path.join(get_debugger_data_dir(), "icons")))
        itheme.rescan_if_needed()

        # Load Builder and Window
        builder = get_debugger_builder()
        main_window: Window = builder.get_object("main_window")
        main_window.set_role("SkyTemple Script Engine Debugger")
        GLib.set_application_name("SkyTemple Script Engine Debugger")
        GLib.set_prgname("skytemple_ssb_debugger")
        # TODO: Deprecated but the only way to set the app title on GNOME...?
        main_window.set_wmclass("SkyTemple Script Engine Debugger", "SkyTemple Script Engine Debugger")

        # Load main window + controller
        MainController(builder, main_window, StandaloneDebuggerControlContext(main_window))

        Gtk.main()
    finally:
        if EmulatorThread.instance():
            EmulatorThread.instance().stop()


def get_debugger_builder() -> Gtk.Builder:
    builder = Gtk.Builder()
    builder.add_from_file(os.path.join(get_debugger_package_dir(), "debugger.glade"))
    return builder


def get_debugger_package_dir():
    return os.path.abspath(os.path.dirname(__file__))


def get_debugger_data_dir():
    return os.path.join(get_debugger_package_dir(), "data")


def get_debugger_version():
    try:
        return pkg_resources.get_distribution("skytemple_ssb_debugger").version
    except pkg_resources.DistributionNotFound:
        return 'unknown'


def _windows_load_theme():
    from skytemple_files.common.platform_utils.win import win_use_light_theme
    settings = Gtk.Settings.get_default()
    theme_name = 'Windows-10-Dark-3.2-dark'
    if win_use_light_theme():
        theme_name = 'Windows-10-3.2'
    else:
        settings.set_property("gtk-application-prefer-dark-theme", True)
    settings.set_property("gtk-theme-name", theme_name)


if __name__ == '__main__':
    # TODO: At the moment doesn't support any cli arguments.
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    main()
