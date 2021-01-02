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


class StringEventEmitter:
    """Emits the string changed event to the context when a string was selected or changed."""
    def __init__(self, view: GtkSource.View, context: AbstractDebuggerControlContext):
        self.view = view
        self.buffer: GtkSource.Buffer = view.get_buffer()
        self.buffer.connect('notify::cursor-position', self.on_buffer_notify_cursor_position)
        self.buffer.connect('changed', self.on_buffer_notify_cursor_position)
        self.context = context

    def on_buffer_notify_cursor_position(self, buffer: GtkSource.Buffer, *args):
        textiter = buffer.get_iter_at_offset(buffer.props.cursor_position)
        if 'string' in buffer.get_context_classes_at_iter(textiter):
            # iter_backward_to_context_class_toggle and iter_forward_to_context_class_toggle
            # seem to be broken (because of course they are), so we do it manually.
            start = self._get_string_start(textiter)
            end = self._get_string_end(textiter)
            if start is None or end is None:
                return True
            string = buffer.get_text(start, end, False)
            self.context.on_selected_string_changed(string)
        return True

    @staticmethod
    def _get_string_start(textiter):
        # First make sure we aren't at the start of the string...
        pit = textiter.copy()
        pit_char = pit.get_char()
        pit.forward_char()
        pit_next_char = pit.get_char()
        if pit_char in ["'", '"'] and pit_next_char == pit_char:
            return
        it = textiter.copy()
        it.backward_char()
        prev = it.copy()
        prev.backward_char()
        while it.get_char() not in ["'", '"'] or prev.get_char() == '\\':
            if not it.backward_char():
                return
            prev = it.copy()
            prev.backward_char()
        it.forward_char()
        return it

    @staticmethod
    def _get_string_end(textiter):
        it = textiter.copy()
        prev_char = it.get_char()
        while it.get_char() not in ["'", '"'] or prev_char == '\\':
            prev_char = it.get_char()
            if not it.forward_char():
                return
        return it
