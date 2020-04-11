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
import string

from gi.repository import GtkSource, Gtk


def backward_until_space(it: Gtk.TextIter):
    it.backward_char()
    while it.get_char() not in string.whitespace:
        if not it.backward_char():
            return
    it.forward_char()


def common_do_match(filter_func, all_func, context: GtkSource.CompletionContext) -> bool:
    _, textiter = context.get_iter()
    buffer: Gtk.TextBuffer = textiter.get_buffer()

    prev_textiter = textiter.copy()
    prev_textiter.backward_char()
    previous_char = prev_textiter.get_char()

    if textiter.ends_word() or previous_char == '_':
        start_word = textiter.copy()
        backward_until_space(start_word)
        word = buffer.get_text(start_word, textiter, False)
        return (
                       len(word) > 2 or context.get_activation() == GtkSource.CompletionActivation.USER_REQUESTED
               ) and len(filter_func(word)) > 0
    return not textiter.inside_word() and context.get_activation() == GtkSource.CompletionActivation.USER_REQUESTED


def common_do_populate(obj, filter_func, all_func, context: GtkSource.CompletionContext):
    _, textiter = context.get_iter()
    buffer: Gtk.TextBuffer = textiter.get_buffer()

    prev_textiter = textiter.copy()
    prev_textiter.backward_char()
    previous_char = prev_textiter.get_char()

    if textiter.ends_word() or previous_char == '_':
        start_word = textiter.copy()
        backward_until_space(start_word)
        word = buffer.get_text(start_word, textiter, False)
        context.add_proposals(obj, filter_func(word), True)
    context.add_proposals(obj, all_func(), True)
