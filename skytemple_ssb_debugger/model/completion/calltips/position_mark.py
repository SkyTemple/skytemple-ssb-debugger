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

from typing import Optional, Tuple, List

from gi.repository import GtkSource, GObject, Gtk

from explorerscript.error import ParseError
from explorerscript.explorerscript_reader import ExplorerScriptReader
from explorerscript.source_map import SourceMapPositionMark
from explorerscript.ssb_converting.compiler.compiler_visitor.position_mark_visitor import PositionMarkVisitor
from explorerscript.ssb_converting.ssb_data_types import SsbOpParamPositionMarker
from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_files.common.i18n_util import f, _


class PositionMarkEditorCalltip(GObject.Object, GtkSource.CompletionProvider):
    """
    Provides a button to click to open a scene editor for interactively editing position marks.
    This is done by parsing the SSBScript / ExplorerScript, extracting all position marks, and then
    telling the DebuggerControlContext to open an editor for the position marks.
    When it's confirmed, the returned position mark data will be read, and the text in the buffer will
    replace this position marks.
    """
    def __init__(self, view: GtkSource.View,
                 mapname: str, scene_name: str, scene_type: str,
                 context: AbstractDebuggerControlContext):
        self.view = view
        self.buffer: GtkSource.Buffer = view.get_buffer()
        self.is_ssbs = False
        self.mapname = mapname
        self.scene_name = scene_name
        self.scene_type = scene_type
        self.context = context

        self._active_widget: Optional[Gtk.Button] = None
        self._active_pos: Optional[Tuple[int, int]] = None

    def reset(self, box):
        if self._active_widget and box is not None:
            for c in box.get_children():
                if c == self._active_widget:
                    box.remove(c)
        self._active_widget = None
        self._active_pos = None

    def add_button_if_pos_mark(self, box: Gtk.Box, buffer: Gtk.TextBuffer):
        textiter = buffer.get_iter_at_offset(buffer.props.cursor_position)
        pos = self._get_start_pos_mark(textiter)
        if pos is None or pos != self._active_pos:
            self.reset(box)

        if pos is not None and pos != self._active_pos:
            self._active_pos = pos
            self._active_widget: Gtk.Button = Gtk.Button.new_with_label('Edit Position Mark')
            self._active_widget.connect('clicked', self.on_clicked)
            box.pack_start(self._active_widget, True, False, 0)

        return True

    def on_clicked(self, *args):
        if self._active_pos is None:
            return
        try:
            tree = ExplorerScriptReader(self.buffer.get_text(
                self.buffer.get_start_iter(), self.buffer.get_end_iter(), False
            )).read()
        except ParseError as err:
            md = self.context.message_dialog_cls()(
                None,
                Gtk.DialogFlags.MODAL, Gtk.MessageType.WARNING, Gtk.ButtonsType.OK,
                f(_("The script contains a syntax error, please fix it before editing the Position Mark.\n"
                    "Parse error: {err}")),
                title=_("Warning!")
            )
            md.run()
            md.destroy()
            return

        pos_marks: List[SourceMapPositionMark] = PositionMarkVisitor().visit(tree)
        pos_mark_to_edit = None
        active_line, active_col = self._active_pos
        for i, mark in enumerate(pos_marks):
            if mark.line_number == active_line and mark.column_number == active_col:
                pos_mark_to_edit = i
                break
        if pos_mark_to_edit is None:
            return
        self.buffer.begin_user_action()
        if self.context.edit_position_mark(self.mapname, self.scene_name, self.scene_type, pos_marks, pos_mark_to_edit):
            for mark in pos_marks:
                start = self.buffer.get_iter_at_line_offset(mark.line_number, mark.column_number)
                end = self.buffer.get_iter_at_line_offset(mark.end_line_number, mark.end_column_number + 1)
                new_mark = str(SsbOpParamPositionMarker(mark.name, mark.x_offset, mark.y_offset,
                                                        mark.x_relative, mark.y_relative))
                self.buffer.delete(start, end)
                self.buffer.insert(start, new_mark)
        self.buffer.end_user_action()

    @staticmethod
    def _get_start_pos_mark(textiter: Gtk.TextIter) -> Optional[Tuple[int, int]]:
        cursor: Gtk.TextIter = textiter.copy()
        limit = 50
        i = 0
        while cursor.backward_char():
            if i > limit:
                break
            if cursor.get_char() == '>':
                # We are not in a PositionMark, for sure!
                return None
            if cursor.get_char() == 'P':
                # Start of position mark?
                end_cursor = cursor.copy()
                end_cursor.forward_chars(9)
                if cursor.get_text(end_cursor) == 'Position<':
                    return cursor.get_line(), cursor.get_line_offset()
            i += 1
        return None
