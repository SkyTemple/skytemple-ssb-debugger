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
import re
from typing import List, Iterable, Tuple, Optional

from gi.repository import GtkSource, Gtk

# file, opcode offset, optional attribute

MARK_PATTERN = re.compile('opcode_<<<(.*)>>>_(\\d+)(?:_(.*))?')
MARK_PATTERN_TMP = re.compile('TMP_opcode_<<<(.*)>>>_(\\d+)(?:_(.*))?')


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
    def get_line_marks_for(cls, b: GtkSource.Buffer, line: int, category: str) -> List[GtkSource.Mark]:
        return b.get_source_marks_at_line(line, category)

    @classmethod
    def get_tmp_opcodes_in_line(cls, b: GtkSource.Buffer, line: int) -> Iterable[Tuple[str, int]]:
        return cls._get_opcode_in_line(b, line, True)

    @classmethod
    def get_opcodes_in_line(cls, b: GtkSource.Buffer, line: int) -> Iterable[Tuple[str, int]]:
        return cls._get_opcode_in_line(b, line, False)

    @classmethod
    def extract_opcode_data_from_line_mark(cls, mark: GtkSource.Mark) -> Tuple[str, int]:
        match = MARK_PATTERN.match(mark.get_name()[4:])
        return str(match.group(1)), int(match.group(2))

    @classmethod
    def add_breakpoint_line_mark(cls, b: GtkSource.Buffer, ssb_filename: str, opcode_offset: int, category: str):
        ms = []
        m: Gtk.TextMark = cls._get_opcode_mark(b, ssb_filename, opcode_offset, True)
        if m is not None:
            ms.append(m)
        m: Gtk.TextMark = cls._get_opcode_mark(b, ssb_filename, opcode_offset, False)
        if m is not None:
            ms.append(m)
        for i, m in enumerate(ms):
            line_iter = b.get_iter_at_line(b.get_iter_at_mark(m).get_line())
            lm: Gtk.TextMark = b.get_mark(f'for:opcode_<<<{ssb_filename}>>>_{opcode_offset}_{i}')
            if lm is not None:
                return
            b.create_source_mark(f'for:opcode_<<<{ssb_filename}>>>_{opcode_offset}_{i}', category, line_iter)

    @classmethod
    def remove_breakpoint_line_mark(cls, b: GtkSource.Buffer, ssb_filename: str, opcode_offset: int, category: str):
        # XXX: This is a bit ugly, but due to the fact, that there can be one call to a macro
        # in the same file, there can be exactly 0-2 line markers:
        for i in [0, 1]:
            m: Gtk.TextMark = b.get_mark(f'for:opcode_<<<{ssb_filename}>>>_{opcode_offset}_{i}')
            if m is None:
                return
            b.remove_source_marks(b.get_iter_at_mark(m), b.get_iter_at_mark(m), category)

    @classmethod
    def create_opcode_mark(cls, b: GtkSource.Buffer, ssb_filename: str,
                           offset: int, line: int, col: int, is_tmp: bool, is_for_macro_call: bool):
        textiter = b.get_iter_at_line_offset(line, col)
        tmp_prefix = 'TMP_' if is_tmp else ''
        macro_call_suffix = '_call' if is_for_macro_call else ''
        b.create_mark(f'{tmp_prefix}opcode_<<<{ssb_filename}>>>_{offset}{macro_call_suffix}', textiter)

    @classmethod
    def switch_to_new_op_marks(cls, b: GtkSource.Buffer, ssb_filename: str):
        textiter: Gtk.TextIter = b.get_start_iter().copy()
        # TODO: This is probably pretty slow
        while textiter.forward_char():
            old_marks_at_pos = [
                m for m in textiter.get_marks()
                if m.get_name() and m.get_name().startswith(f'opcode_<<<{ssb_filename}>>>_')
            ]
            new_marks_at_pos = [
                m for m in textiter.get_marks()
                if m.get_name() and m.get_name().startswith(f'TMP_opcode_<<<{ssb_filename}>>>_')
            ]
            for m in old_marks_at_pos:
                b.delete_mark(m)
            for m in new_marks_at_pos:
                name = m.get_name()
                # Maybe by chance an old mark with this name still exists elsewhere, remove it.
                om = b.get_mark(name[4:])
                if om is not None:
                    b.delete_mark(om)
                # Move by deleting and re-creating.
                match = MARK_PATTERN_TMP.match(m.get_name())
                if match.group(3):
                    b.create_mark(f'opcode_<<<{str(match.group(1))}>>>_{int(match.group(2))}_{match.group(3)}', textiter)
                else:
                    b.create_mark(f'opcode_<<<{str(match.group(1))}>>>_{int(match.group(2))}', textiter)
                b.delete_mark(m)

    @classmethod
    def _get_opcode_mark(cls, b: GtkSource.Buffer, ssb_filename: str, opcode_addr: int, is_for_macro_call: bool) -> Optional[Gtk.TextMark]:
        if is_for_macro_call:
            return b.get_mark(f'opcode_<<<{ssb_filename}>>>_{opcode_addr}_call')
        else:
            return b.get_mark(f'opcode_<<<{ssb_filename}>>>_{opcode_addr}')

    @classmethod
    def _get_opcode_in_line(cls, buffer: Gtk.TextBuffer, line, use_temp_markers=False) -> List[Tuple[str, int]]:
        marker_prefix = 'opcode_'
        marker_pattern = MARK_PATTERN
        if use_temp_markers:
            marker_prefix = 'TMP_opcode_'
            marker_pattern = MARK_PATTERN_TMP
        i = buffer.get_iter_at_line(line)
        marks = []
        while i.get_line() == line:
            marks_at_pos = [
                m for m in i.get_marks() if m.get_name() and m.get_name().startswith(marker_prefix)
            ]
            for m in marks_at_pos:
                match = marker_pattern.match(m.get_name())
                marks.append((str(match.group(1)), int(match.group(2))))
            if not i.forward_char():  # TODO: the other forwards might also work!
                return marks
        return marks
