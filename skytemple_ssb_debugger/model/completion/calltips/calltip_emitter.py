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
from typing import List, Optional

from gi.repository import GtkSource, Gtk

from skytemple_files.common.ppmdu_config.script_data import Pmd2ScriptOpCode
from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_ssb_debugger.model.completion.calltips.position_mark import PositionMarkEditorCalltip
from skytemple_ssb_debugger.model.completion.util import backward_until_space


class CalltipEmitter:
    """Provides calltips for the currently selected function (if inside the parentheses)"""
    def __init__(self, view: GtkSource.View, opcodes: List[Pmd2ScriptOpCode],
                 mapname: str, scene_name: str, scene_type: str, context: AbstractDebuggerControlContext, is_ssbs=False):
        self.view = view
        self.buffer: GtkSource.Buffer = view.get_buffer()
        self.opcodes = opcodes
        self.buffer.connect('notify::cursor-position', self.on_buffer_notify_cursor_position)
        self.position_mark_calltip = None
        if not is_ssbs and mapname is not None and scene_name is not None and scene_type is not None:
            self.position_mark_calltip = PositionMarkEditorCalltip(
                view, mapname, scene_name, scene_type, context
            )

        self._active_widget: Optional[GtkSource.CompletionInfo] = None
        self._active_op: Optional[Pmd2ScriptOpCode] = None
        self._active_arg: Optional[int] = None

    def on_buffer_notify_cursor_position(self, buffer: GtkSource.Buffer, *args):
        textiter = buffer.get_iter_at_offset(buffer.props.cursor_position)
        tip = self._build_calltip_data(textiter, buffer)
        if not tip:
            if self.position_mark_calltip is not None:
                self.position_mark_calltip.reset(self._active_widget)
            if self._active_widget:
                self._active_widget.destroy()
                self._active_widget = None
                self._active_op = None
                self._active_arg = None
            return True

        op: Pmd2ScriptOpCode
        op, arg_index = tip
        if not self._active_widget:
            self._active_widget: GtkSource.CompletionInfo = GtkSource.CompletionInfo.new()
            self._active_widget.set_attached_to(self.view)

        self._active_widget.move_to_iter(self.view, textiter)

        op_was_same = self._active_op == op
        if not op_was_same:
            self._active_op = op
            for c in self._active_widget.get_children():
                self._active_widget.remove(c)

            outer_box: Gtk.Box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
            btn_box: Gtk.Box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
            outer_box.pack_start(btn_box, True, False, 0)
            self._active_widget.add(outer_box)

        if not op_was_same or self._active_arg != arg_index:
            self._active_arg = arg_index
            btn_box: Gtk.Box = self._active_widget.get_children()[0].get_children()[0]
            for c in btn_box.get_children():
                btn_box.remove(c)
            for i, arg in enumerate(op.arguments):
                lbl: Gtk.Label = Gtk.Label.new('')
                if arg_index == i:
                    markup = f'<b>{arg.name}: <i>{arg.type}</i></b>, '
                else:
                    markup = f'<span weight="light">{arg.name}:  <i>{arg.type}</i></span>, '
                if i == len(op.arguments) - 1 and not op.repeating_argument_group:
                    markup = markup.rstrip(', ')
                lbl.set_markup(markup)
                btn_box.pack_start(lbl, True, False, 0)
            if op.repeating_argument_group:
                lbl: Gtk.Label = Gtk.Label.new('[')
                btn_box.pack_start(lbl, True, False, 0)
                for i, arg in enumerate(op.repeating_argument_group.arguments):
                    lbl: Gtk.Label = Gtk.Label.new('')
                    # TODO: Support highlighting individual repeating args. (not really used though)
                    if arg_index >= len(op.arguments):
                        markup = f'<b>{arg.name}: <i>{arg.type}</i></b>, '
                    else:
                        markup = f'<span weight="light">{arg.name}:  <i>{arg.type}</i></span>, '
                    if i == len(op.repeating_argument_group.arguments) - 1:
                        markup = markup.rstrip(', ')
                    lbl.set_markup(markup)
                    btn_box.pack_start(lbl, True, False, 0)
                lbl: Gtk.Label = Gtk.Label.new('... ]')
                btn_box.pack_start(lbl, True, False, 0)

        if self.position_mark_calltip is not None:
            self.position_mark_calltip.add_button_if_pos_mark(self._active_widget.get_children()[0], buffer)

        self._active_widget.show_all()

        return True

    def _build_calltip_data(self, textiter: Gtk.TextIter, buffer: GtkSource.Buffer):
        cursor = textiter.copy()
        count_commas = 0
        count_commas_since_last_lang_string_begin_mark = 0
        while cursor.backward_char():
            if cursor.get_char() == ')':
                # We are not in a function, for sure!
                return None
            if cursor.get_char() == '{' or cursor.get_char() == '<':
                # Handle middle of language string or a pos marker
                count_commas -= count_commas_since_last_lang_string_begin_mark
                count_commas_since_last_lang_string_begin_mark = 0
            if cursor.get_char() == '}' or cursor.get_char() == '>':
                # Handle end of language string or a pos marker
                count_commas_since_last_lang_string_begin_mark = 0
            if cursor.get_char() == '(':
                # Handle the opcode/function name
                start_of_word = cursor.copy()
                backward_until_space(start_of_word)
                opcode_name = buffer.get_text(start_of_word, cursor, False)
                for op in self.opcodes:
                    if op.name == opcode_name:
                        return op, count_commas
                return None
            if cursor.get_char() == ',':
                # Collect commas for the arg index
                count_commas += 1
                count_commas_since_last_lang_string_begin_mark += 1
        return None
