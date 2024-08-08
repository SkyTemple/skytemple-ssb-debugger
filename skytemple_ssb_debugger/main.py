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

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
gi.require_version("Adw", "1")

import logging
import os
import sys

from skytemple_ssb_debugger.widget.application import SkyTempleSsbDebuggerApp

from skytemple_icons import icons

from gi.repository import Gtk, Gdk


def main(argv: list[str] | None = None):
    if argv is None:
        argv = sys.argv

    display = Gdk.Display.get_default()
    assert display is not None
    itheme = Gtk.IconTheme.get_for_display(display)
    itheme.add_search_path(os.path.abspath(icons()))
    itheme.add_search_path(os.path.abspath(os.path.join(get_debugger_data_dir(), "icons")))

    app = SkyTempleSsbDebuggerApp()
    sys.exit(app.run(argv))


def get_debugger_package_dir():
    return os.path.abspath(os.path.dirname(__file__))


def get_debugger_data_dir():
    return os.path.join(get_debugger_package_dir(), "data")


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    main()
