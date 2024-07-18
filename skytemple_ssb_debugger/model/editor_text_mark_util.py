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
import re
from typing import List, Tuple, Optional, TypeVar, cast
from collections.abc import Iterable

from gi.repository import GtkSource, Gtk

CATEGORY_OPCODE = "opcode"
CATEGORY_BREAKPOINT = "breakpoint"
MARK_PATTERN = re.compile('opcode_<<<(.*)>>>_(\\d+)(?:_(.*))?')


class EditorTextMarkUtil:
    """A static utility class for managing the op related text/source marks in a GtkSource.Buffer."""
    @classmethod
    def add_line_mark_for_op(cls, b: GtkSource.Buffer, ssb_filename: str, opcode_addr: int, name: str, category: str, is_for_macro_call: bool):
        m = cls._get_opcode_mark(b, ssb_filename, opcode_addr, is_for_macro_call)
        if m is not None:
            b.create_source_mark(name, category, b.get_iter_at_mark(m))

    @classmethod
    def remove_all_line_marks(cls, b: GtkSource.Buffer, category: str):
        b.remove_source_marks(b.get_start_iter(), b.get_end_iter(), category)

    @classmethod
    def scroll_to_op(cls, b: GtkSource.Buffer, view: GtkSource.View, ssb_filename: str, opcode_addr: int, is_for_macro_call: bool):
        m = cls._get_opcode_mark(b, ssb_filename, opcode_addr, is_for_macro_call)
        if m is not None:
            view.scroll_to_mark(m, 0.1, False, 0.1, 0.1)
            b.place_cursor(b.get_iter_at_mark(m))

    @classmethod
    def get_line_marks_for(cls, b: GtkSource.Buffer, line: int, category: str) -> list[GtkSource.Mark]:
        return b.get_source_marks_at_line(line, category)

    @classmethod
    def get_opcodes_in_line(cls, b: GtkSource.Buffer, line: int) -> Iterable[tuple[str, int]]:
        return cls._get_opcode_in_line(b, line)

    @classmethod
    def extract_opcode_data_from_line_mark(cls, mark: GtkSource.Mark) -> tuple[str, int]:
        name = mark.get_name()
        assert name is not None
        match = MARK_PATTERN.match(name[4:])
        assert match
        return str(match.group(1)), int(match.group(2))

    @classmethod
    def add_breakpoint_line_mark(cls, b: GtkSource.Buffer, ssb_filename: str, opcode_offset: int):
        ms = []
        m = cls._get_opcode_mark(b, ssb_filename, opcode_offset, True)
        if m is not None:
            ms.append(m)
        m = cls._get_opcode_mark(b, ssb_filename, opcode_offset, False)
        if m is not None:
            ms.append(m)
        for i, m in enumerate(ms):
            line_iter = b.get_iter_at_line(b.get_iter_at_mark(m).get_line())
            lm = b.get_mark(f'for:opcode_<<<{ssb_filename}>>>_{opcode_offset}_{i}')
            if lm is not None:
                return
            b.create_source_mark(f'for:opcode_<<<{ssb_filename}>>>_{opcode_offset}_{i}', CATEGORY_BREAKPOINT, line_iter)

    @classmethod
    def remove_breakpoint_line_mark(cls, b: GtkSource.Buffer, ssb_filename: str, opcode_offset: int):
        # XXX: This is a bit ugly, but due to the fact, that there can be one call to a macro
        # in the same file, there can be exactly 0-2 line markers:
        for i in [0, 1]:
            m = b.get_mark(f'for:opcode_<<<{ssb_filename}>>>_{opcode_offset}_{i}')
            if m is None:
                return
            b.remove_source_marks(b.get_iter_at_mark(m), b.get_iter_at_mark(m), CATEGORY_BREAKPOINT)

    @classmethod
    def create_opcode_mark(cls, b: GtkSource.Buffer, ssb_filename: str,
                           offset: int, line: int, col: int, is_for_macro_call: bool):
        textiter = b.get_iter_at_line_offset(line, col)
        macro_call_suffix = '_call' if is_for_macro_call else ''
        b.create_source_mark(f'opcode_<<<{ssb_filename}>>>_{offset}{macro_call_suffix}', CATEGORY_OPCODE, textiter)

    @classmethod
    def _get_opcode_mark(cls, b: GtkSource.Buffer, ssb_filename: str, opcode_addr: int, is_for_macro_call: bool) -> Gtk.TextMark | None:
        if is_for_macro_call:
            return b.get_mark(f'opcode_<<<{ssb_filename}>>>_{opcode_addr}_call')
        else:
            return b.get_mark(f'opcode_<<<{ssb_filename}>>>_{opcode_addr}')

    @classmethod
    def _get_opcode_in_line(cls, buffer: GtkSource.Buffer, line) -> list[tuple[str, int]]:
        i = buffer.get_iter_at_line(line)
        marks = []
        while i.get_line() == line:
            marks_at_pos = buffer.get_source_marks_at_iter(i, CATEGORY_OPCODE)
            for m in marks_at_pos:
                match = MARK_PATTERN.match(not_none(m.get_name()))
                assert match
                marks.append((str(match.group(1)), int(match.group(2))))
            if not i.forward_char():  # TODO: the other forwards might also work!
                return marks
        return marks


T = TypeVar('T')


def not_none(x: T | None) -> T:
    return cast(T, x)
