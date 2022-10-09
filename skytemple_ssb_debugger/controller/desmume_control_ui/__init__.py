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
from gi.repository import Gtk
from skytemple_files.common.i18n_util import _

key_names_localized = [
    _("A"),  # TRANSLATORS: DS Key name
    _("B"),  # TRANSLATORS: DS Key name
    _("Select"),  # TRANSLATORS: DS Key name
    _("Start"),  # TRANSLATORS: DS Key name
    _("Right"),  # TRANSLATORS: DS Key name
    _("Left"),  # TRANSLATORS: DS Key name
    _("Up"),  # TRANSLATORS: DS Key name
    _("Down"),  # TRANSLATORS: DS Key name
    _("R"),  # TRANSLATORS: DS Key name
    _("L"),  # TRANSLATORS: DS Key name
    _("X"),  # TRANSLATORS: DS Key name
    _("Y"),  # TRANSLATORS: DS Key name
    _("Debug"),  # TRANSLATORS: DS Key name
    _("Boost"),  # TRANSLATORS: DS Key name
    _("Lid")  # TRANSLATORS: DS Key name
]


def widget_to_primitive(w: Gtk.Widget):
    name = Gtk.Buildable.get_name(w)
    if name.startswith("%d:"):
        return int(name[3:])
    elif name.startswith("%f:"):
        return float(name[3:])
    raise ValueError("Invalid widget for widget_to_primitive.")
