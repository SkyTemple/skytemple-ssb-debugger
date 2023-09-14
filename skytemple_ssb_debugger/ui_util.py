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

import os
import sys
from typing import TypeVar, Any

from gi.repository import GObject, Gtk

if sys.version_info >= (3, 9):
    import importlib.metadata as importlib_metadata
else:
    import importlib_metadata


T = TypeVar("T", bound=GObject.Object)
X = TypeVar("X")
UI_ASSERT = "SKYTEMPLE_UI_ASSERT" in os.environ


def assert_not_none(obj: X | None) -> X:
    assert obj is not None
    return obj


def builder_get_assert(builder: Gtk.Builder, typ: type[T], name: str) -> T:
    obj = builder.get_object(name)
    if UI_ASSERT:
        assert isinstance(obj, typ)
        return obj
    else:
        return obj  # type: ignore


def iter_tree_model(model: Gtk.TreeModel) -> Any:
    # TODO: This works but isn't supported by the typestubs.
    return model  # type: ignore


def create_tree_view_column(
    title: str,
    renderer: Gtk.CellRenderer,
    **kwargs: int
) -> Gtk.TreeViewColumn:
    """
    Compatibility with the 'old' TreeViewColumn constructor and generally a convenient shortcut for quick TreeViewColumn
    construction.
    The kwargs name is the attribute name, the value the column ID.
    """
    column = Gtk.TreeViewColumn(title=title)
    column.pack_start(renderer, True)
    for attr, column_id in kwargs.items():
        column.add_attribute(renderer, attr, column_id)
    return column


def get_debugger_version():
    try:
        return importlib_metadata.metadata("skytemple_ssb_debugger")["version"]
    except importlib_metadata.PackageNotFoundError:
        return 'unknown'
