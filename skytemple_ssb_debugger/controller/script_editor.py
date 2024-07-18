"""Controller for a single SSB script editor (ExplorerScript)."""
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
import logging
import os
import re
import webbrowser
from functools import partial
from typing import Tuple, List, Optional, TYPE_CHECKING, Callable, Dict, cast
from collections.abc import Iterable

from gi.repository import GtkSource, Gtk
from gi.repository.GtkSource import LanguageManager
from gtkspellcheck import SpellChecker

from explorerscript.error import ParseError
from explorerscript.ssb_converting.ssb_data_types import SsbRoutineType

from skytemple_ssb_debugger.model.script_file_context.exps_macro import ExpsMacroFileScriptFileContext
from skytemple_ssb_debugger.ui_util import assert_not_none
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_emulator import emulator_debug_breakpoints_resync, emulator_debug_breakpoint_add, \
    emulator_debug_breakpoint_remove, emulator_breakpoints_get_saved_in_ram_for

from skytemple_ssb_debugger.model.completion.calltips.calltip_emitter import CalltipEmitter
from skytemple_ssb_debugger.model.completion.calltips.string_event_emitter import StringEventEmitter
from skytemple_ssb_debugger.model.completion.constants import GtkSourceCompletionSsbConstants
from skytemple_ssb_debugger.model.completion.exps_statements import GtkSourceCompletionExplorerScriptStatements
from skytemple_ssb_debugger.model.completion.functions import GtkSourceCompletionSsbFunctions
from skytemple_ssb_debugger.model.completion.util import filter_special_exps_opcodes
from skytemple_ssb_debugger.model.constants import ICON_ACTOR, ICON_OBJECT, ICON_PERFORMER, ICON_GLOBAL_SCRIPT
from skytemple_ssb_debugger.model.editor_text_mark_util import EditorTextMarkUtil, CATEGORY_OPCODE, CATEGORY_BREAKPOINT
from skytemple_ssb_debugger.model.script_file_context.abstract import AbstractScriptFileContext
from skytemple_ssb_debugger.model.settings import TEXTBOX_TOOL_URL
from skytemple_ssb_debugger.pixbuf.icons import *
from skytemple_files.common.i18n_util import f, _

from skytemple_ssb_debugger.ui_util import builder_get_assert

if TYPE_CHECKING:
    from skytemple_ssb_debugger.controller.editor_notebook import EditorNotebookController

logger = logging.getLogger(__name__)


EXECUTION_LINE_PATTERN = re.compile('execution_(\\d+)_(\\d+)_(\\d+)')


class ScriptEditorController:
    def __init__(
            self, parent: EditorNotebookController, main_window: Gtk.Window, file_context: AbstractScriptFileContext,
            rom_data: Pmd2Data, modified_handler, mapname: str | None,
    ):
        path = os.path.abspath(os.path.dirname(__file__))
        try:
            from skytemple.core.ui_utils import make_builder  # type: ignore
            self.builder = make_builder(os.path.join(path, "ssb_editor.glade"))  # type: ignore
        except ImportError:
            self.builder = Gtk.Builder()
            self.builder.add_from_file(os.path.join(path, "ssb_editor.glade"))
        self.file_context: AbstractScriptFileContext = file_context
        self.mapname = mapname
        self.rom_data = rom_data
        self.parent = parent
        self._main_window = main_window
        self._modified_handler = modified_handler

        self._root = builder_get_assert(self.builder, Gtk.Box, 'code_editor')
        scheme = self.parent.parent.style_scheme_manager.get_scheme(
            self.parent.parent.selected_style_scheme_id
        )
        self._active_scheme: GtkSource.StyleScheme = assert_not_none(scheme)
        self._lm = LanguageManager()
        self._lm.set_search_path(self._lm.get_search_path() + [os.path.join(path, '..')])

        self._waiting_for_reload = False

        self._explorerscript_view: GtkSource.View = None  # type: ignore
        self._explorerscript_spellcheck: SpellChecker = None  # type: ignore
        self._explorerscript_revealer: Gtk.Revealer = None  # type: ignore
        self._explorerscript_search: Gtk.SearchEntry = None  # type: ignore
        self._explorerscript_search_context: GtkSource.SearchContext = None  # type: ignore
        self._saving_dialog: Gtk.Dialog | None = None

        self._still_loading = True
        self._foucs_opcode_after_load: tuple[str, int] | None = None
        self._on_break_pulled_after_load: tuple[str, int, bool] | None = None
        self._hanger_halt_lines_after_load: tuple[str, list[tuple[SsbRoutineType, int, int]]] | None = None
        self._spellchecker_loaded = False

        self._loaded_search_window: Gtk.Dialog | None = None
        self._active_search_context: GtkSource.SearchContext | None = None

        self._mrk_attrs__breakpoint: GtkSource.MarkAttributes = GtkSource.MarkAttributes.new()
        self._mrk_attrs__breakpoint.set_pixbuf(create_breakpoint_icon())

        self._mrk_attrs__breaked_line: GtkSource.MarkAttributes = GtkSource.MarkAttributes.new()

        self._mrk_attrs__execution_line: GtkSource.MarkAttributes = GtkSource.MarkAttributes.new()

        self.switch_style_scheme(self._active_scheme)

        self.file_context.register_ssbs_state_change_handler(self.on_ssbs_state_change)
        self.file_context.register_ssbs_reload_handler(self.reload_breakpoints)
        self.file_context.register_insert_opcode_text_mark_handler(self.insert_opcode_text_mark)
        self.file_context.register_clear_opcode_text_mark_handler(self.clear_opcode_text_marks)

        self.load_views(
            builder_get_assert(self.builder, Gtk.Box, 'page_explorerscript')
        )

        builder_get_assert(self.builder, Gtk.ToggleToolButton, 'code_editor_cntrls_breaks').set_active(self.parent.parent.global_state__breaks_disabled)

        self.builder.connect_signals(self)

        self._root.show_all()

    def get_root_object(self) -> Gtk.Box:
        return self._root

    def destroy(self):
        self.file_context.destroy()
        self._root.destroy()

    @property
    def has_changes(self):
        if self._explorerscript_view and self._explorerscript_view.get_buffer().get_modified():
            return True
        return False

    @property
    def filename(self):
        if self.file_context.ssb_filepath:
            return self.file_context.ssb_filepath
        return self.file_context.exps_filepath

    def toggle_debugging_controls(self, val):
        builder_get_assert(self.builder, Gtk.ToolButton, 'code_editor_cntrls_resume').set_sensitive(val)
        builder_get_assert(self.builder, Gtk.ToolButton, 'code_editor_cntrls_step_over').set_sensitive(val)
        builder_get_assert(self.builder, Gtk.ToolButton, 'code_editor_cntrls_step_into').set_sensitive(val)
        builder_get_assert(self.builder, Gtk.ToolButton, 'code_editor_cntrls_step_out').set_sensitive(val)
        builder_get_assert(self.builder, Gtk.ToolButton, 'code_editor_cntrls_step_next').set_sensitive(val)

    def on_break_pulled(self, ssb_filename, opcode_addr, halted_on_call):
        """Mark the currently actively halted opcode, if we have one for the current file and opcode."""
        if self._still_loading:
            self._on_break_pulled_after_load = (ssb_filename, opcode_addr, halted_on_call)
        else:
            self.on_break_released()
            expsb: GtkSource.Buffer = self._explorerscript_view.get_buffer()
            if ssb_filename is not None and opcode_addr != -1:
                EditorTextMarkUtil.add_line_mark_for_op(
                    expsb, ssb_filename, opcode_addr, 'breaked-line', 'breaked-line',
                    halted_on_call
                )

    def on_break_released(self):
        """Remove the marks for the current breaked line."""
        expsb: GtkSource.Buffer = self._explorerscript_view.get_buffer()
        EditorTextMarkUtil.remove_all_line_marks(expsb, 'breaked-line')

    def on_ssb_changed_externally(self, ssb_filename, ready_to_reload):
        """
        A ssb file was re-compiled from outside of it's script editor.
        Let our context handle this.
        """
        self.file_context.on_ssb_changed_externally(ssb_filename, ready_to_reload and not self.has_changes)

    def on_exps_macro_ssb_changed(self, exps_abs_path, ssb_filename):
        """
        The ssb file ssb_filename was changed and it imports the ExplorerScript macro file with the absolute path
        of exps_abs_path.
        Let our context handle this.
        """
        self.file_context.on_exps_macro_ssb_changed(exps_abs_path, ssb_filename)

    def insert_hanger_halt_lines(self, ssb_filename: str, lines: list[tuple[SsbRoutineType, int, int]]):
        """Mark the current execution position for all running scripts.
        List is tuples (type, id, filename, opcode_addr)"""
        if self._still_loading:
            self._hanger_halt_lines_after_load = (ssb_filename, lines)
        else:
            expsb: GtkSource.Buffer = self._explorerscript_view.get_buffer()
            EditorTextMarkUtil.remove_all_line_marks(expsb, 'execution-line')
            for type, slot_id, opcode_addr in lines:
                EditorTextMarkUtil.add_line_mark_for_op(
                    expsb, ssb_filename, opcode_addr,
                    f'execution_{type.value}_{type.value}_{slot_id}', 'execution-line',
                    False  # TODO: Call breaking
                )

    def remove_hanger_halt_lines(self):
        """Remove the marks for the current script execution points"""
        if self._still_loading:
            self._hanger_halt_lines_after_load = None
        else:
            expsb: GtkSource.Buffer = self._explorerscript_view.get_buffer()
            EditorTextMarkUtil.remove_all_line_marks(expsb, 'execution-line')

    def focus_opcode(self, ssb_filename, opcode_addr):
        """Put a textmark representing an opcode into the center of view."""
        if self._still_loading:
            self._foucs_opcode_after_load = (ssb_filename, opcode_addr)
        else:
            expsv = self._explorerscript_view
            EditorTextMarkUtil.scroll_to_op(
                expsv.get_buffer(), expsv, ssb_filename, opcode_addr,
                False  # TODO: Call breaking
            )

    def save(self):
        """
        Save the script file. As a constraint only the ssbs or exps views should be editable, so in theory only one can
        have changes... - we save that one!
        """
        modified_buffer: GtkSource.Buffer
        save_text = None

        if self._explorerscript_view.get_buffer().get_modified():
            modified_buffer = self._explorerscript_view.get_buffer()
            save_text = modified_buffer.props.text
        if not save_text:
            return

        if modified_buffer.get_line_count() > 4000 or isinstance(self.file_context, ExpsMacroFileScriptFileContext):
            self._main_window.set_sensitive(False)

        self.file_context.save(save_text=save_text,
                               error_callback=self._save_done_error,
                               success_callback=partial(self._save_done, modified_buffer))


    def _save_done_error(self, exc_info, err):
        """Gtk callback after the saving has been done, but an error occured."""
        self._main_window.set_sensitive(True)
        prefix = ''
        if isinstance(err, ParseError):
            prefix = _('Parse error: ')
        self.parent.get_context().display_error(
            exc_info,
            f(_("The script file {self.filename} could not be saved.\n"
                "{prefix}{err}")),
            _("Error saving the script.")
        )

    def _save_done(self, modified_buffer: GtkSource.Buffer):
        """Gtk callback after the saving has been done."""
        modified_buffer.set_modified(False)
        self._waiting_for_reload = True

        # Resync the breakpoints at the Breakpoint Manager.
        breakpoints_to_resync: dict[str, list[int]] = {}
        for line in range(0, modified_buffer.get_line_count()):
            marks = EditorTextMarkUtil.get_line_marks_for(modified_buffer, line, 'breakpoint')
            if len(marks) > 0:
                for ssb_filename, opcode_offset in EditorTextMarkUtil.get_opcodes_in_line(modified_buffer, line):
                    if ssb_filename not in breakpoints_to_resync:
                        breakpoints_to_resync[ssb_filename] = []
                    breakpoints_to_resync[ssb_filename].append(opcode_offset)

        for ssb_filename, b_points in breakpoints_to_resync.items():
            assert self.parent.file_manager is not None
            emulator_debug_breakpoints_resync(ssb_filename, b_points, self.parent.file_manager.get(ssb_filename))

        self._main_window.set_sensitive(True)

    def load_views(self, exps_bx: Gtk.Box):
        self._activate_spinner(exps_bx)

        (exps_ovl, self._explorerscript_view, self._explorerscript_revealer,
         self._explorerscript_search, self._explorerscript_search_context) = self._create_editor()

        # SPELL CHECK
        self.toggle_spellchecker(self.parent.parent.settings.get_spellcheck_enabled())

        self._load_explorerscript_completion()

        def load__gtk__process_loaded(text, language):
            ovl = exps_ovl
            bx = assert_not_none(exps_bx)
            view = self._explorerscript_view
            for child in bx.get_children():
                bx.remove(child)
            buffer: GtkSource.Buffer = view.get_buffer()
            undo_manager: GtkSource.UndoManager = assert_not_none(buffer.get_undo_manager())
            undo_manager.begin_not_undoable_action()
            buffer.set_text(text)
            buffer.set_modified(False)
            undo_manager.end_not_undoable_action()
            buffer.set_language(self._lm.get_language(language))
            buffer.set_highlight_syntax(True)

            bx.pack_start(ovl, True, True, 0)

        def load__gtk__exps_hash_error(force_decompile: Callable, force_load: Callable):
            if self._show_ssbs_es_changed_warning():
                # Re-generate the ExplorerScript
                force_decompile()
            else:
                # Force load the file
                force_load()

        def load__gtk__exps_exception(exc_info, exception):
            self.parent.get_context().display_error(
                exc_info,
                f(_("There was an error while loading the ExplorerScript "
                    "source code. The source will not be available.\n"
                    "Please close and reopen the tab.\n\n"
                    "{exception}"))
            )

        def load_gtk__after():
            self.file_context.request_ssbs_state()
            if self._still_loading:
                self._after_views_loaded()

        self.file_context.load(load_view_callback=load__gtk__process_loaded,
                               after_callback=load_gtk__after,
                               exps_exception_callback=load__gtk__exps_exception,
                               exps_hash_changed_callback=load__gtk__exps_hash_error,)

    def _after_views_loaded(self):
        self._still_loading = False
        if self._foucs_opcode_after_load:
            self.focus_opcode(*self._foucs_opcode_after_load)
        if self._on_break_pulled_after_load:
            self.on_break_pulled(*self._on_break_pulled_after_load)
        if self._hanger_halt_lines_after_load:
            self.insert_hanger_halt_lines(*self._hanger_halt_lines_after_load)

    def add_breakpoint(self, line_number: int, view: GtkSource.View):
        buffer: GtkSource.Buffer = view.get_buffer()
        for ssb_filename, opcode_offset in EditorTextMarkUtil.get_opcodes_in_line(buffer, line_number - 1):
            emulator_debug_breakpoint_add(ssb_filename, opcode_offset)

    def remove_breakpoint(self, mark: GtkSource.Mark):
        ssb_filename, opcode_offset = EditorTextMarkUtil.extract_opcode_data_from_line_mark(mark)
        emulator_debug_breakpoint_remove(ssb_filename, opcode_offset)

    def on_breakpoint_added(self, ssb_filename, opcode_offset):
        buffer: GtkSource.Buffer = self._explorerscript_view.get_buffer()
        EditorTextMarkUtil.add_breakpoint_line_mark(buffer, ssb_filename, opcode_offset)

    def on_breakpoint_removed(self, ssb_filename, opcode_offset):
        buffer: GtkSource.Buffer = self._explorerscript_view.get_buffer()
        EditorTextMarkUtil.remove_breakpoint_line_mark(buffer, ssb_filename, opcode_offset)

    def reload_breakpoints(self, ssb_filename):
        """
        The given ssb file is clear for reload (saved & no longer loaded in Ground Engine).
        Reload all breakpoints.
        """
        buffer: GtkSource.Buffer = self._explorerscript_view.get_buffer()
        # Remove all breakpoints
        EditorTextMarkUtil.remove_all_line_marks(buffer, CATEGORY_BREAKPOINT)

        # Re-add all breakpoints
        for opcode_offset in emulator_breakpoints_get_saved_in_ram_for(ssb_filename):
            self.on_breakpoint_added(ssb_filename, opcode_offset)

    def insert_opcode_text_mark(self, ssb_filename: str,
                                opcode_offset: int, line: int, column: int, is_for_macro_call=False):
        view = self._explorerscript_view
        EditorTextMarkUtil.create_opcode_mark(
            view.get_buffer(), ssb_filename, opcode_offset, line, column, is_for_macro_call
        )

    def clear_opcode_text_marks(self):
        view = self._explorerscript_view
        EditorTextMarkUtil.remove_all_line_marks(view.get_buffer(), CATEGORY_OPCODE)

    # Signal & event handlers
    def on_ssbs_state_change(self, breakable: bool, _ram_state_up_to_date: bool):
        """Fully rebuild the active info bar message based on the current state of the SSB."""
        info_bar = builder_get_assert(self.builder, Gtk.InfoBar, 'code_editor_box_es_bar')

        if not breakable:
            self._refill_info_bar(
                info_bar, Gtk.MessageType.WARNING,
                _("An old version of this script is still loaded in RAM. Debugging is disabled for this file, until it is reloaded.")
            )
            return

        info_bar.set_message_type(Gtk.MessageType.OTHER)
        info_bar.set_revealed(False)

    def on_sourceview_line_mark_activated(self, widget: GtkSource.View, textiter: Gtk.TextIter, event: Gdk.Event):
        marks = widget.get_buffer().get_source_marks_at_iter(textiter)

        # No mark? Add!
        if len(marks) < 1:
            self.add_breakpoint(textiter.get_line() + 1, widget)
        else:
            # Mark? Remove breakpoint!
            for mark in marks:
                self.remove_breakpoint(mark)
        return True

    def on_sourcebuffer_delete_range(self, buffer: GtkSource.Buffer, start: Gtk.TextIter, end: Gtk.TextIter):
        if start.get_line() != end.get_line() or start.get_chars_in_line() == 0:
            i = start.copy()
            ms = []
            while i.get_offset() <= end.get_offset():
                ms += buffer.get_source_marks_at_iter(i, 'breakpoint')
                if not i.forward_char():
                    break
            for m in ms:
                self.remove_breakpoint(m)
        return True

    def on_search_entry_focus_out_event(self, widget: Gtk.SearchEntry, *args):
        view = self._explorerscript_view
        revealer = self._explorerscript_revealer
        revealer.set_reveal_child(False)
        view.grab_focus()

    def on_search_entry_search_changed(self, widget: Gtk.SearchEntry):
        view = self._explorerscript_view
        context = self._explorerscript_search_context
        buffer: Gtk.TextBuffer = view.get_buffer()

        settings: GtkSource.SearchSettings = context.get_settings()
        settings.set_search_text(widget.get_text())
        found, match_start, match_end = context.forward(buffer.get_iter_at_offset(buffer.props.cursor_position))[:3]
        if found:
            buffer.select_range(match_start, match_end)
            self._explorerscript_view.scroll_to_iter(match_start, 0.1, False, 0.5, 0.5)

    def on_search_up_button_clicked(self, widget: Gtk.Button, search: Gtk.SearchEntry):
        view = self._explorerscript_view
        context = self._explorerscript_search_context
        buffer: Gtk.TextBuffer = view.get_buffer()

        settings: GtkSource.SearchSettings = context.get_settings()
        settings.set_search_text(search.get_text())
        found, match_start, match_end, wrap = context.backward(buffer.get_iter_at_offset(buffer.props.cursor_position))[:4]
        if found:
            buffer.select_range(match_start, match_end)
            self._explorerscript_view.scroll_to_iter(match_start, 0.1, False, 0.5, 0.5)

    def on_search_down_button_clicked(self, widget: Gtk.Button, search: Gtk.SearchEntry):
        view = self._explorerscript_view
        context = self._explorerscript_search_context
        buffer: Gtk.TextBuffer = view.get_buffer()

        settings: GtkSource.SearchSettings = context.get_settings()
        settings.set_search_text(search.get_text())
        cursor = buffer.get_iter_at_offset(buffer.props.cursor_position)
        found, match_start, match_end, wrap = context.forward(cursor)
        if found:
            if match_start.get_offset() == cursor.get_offset():
                # Repeat once, to really get down
                found, match_start, match_end, wrap = context.forward(match_end)
            if found:
                buffer.select_range(match_start, match_end)
                self._explorerscript_view.scroll_to_iter(match_start, 0.1, False, 0.5, 0.5)

    def on_sr_dialog_close(self, dialog: Gtk.Dialog, *args):
        self._loaded_search_window = None
        dialog.hide()
        return True

    def on_sr_search_setting_regex_toggled(self, btn: Gtk.CheckButton, *args):
        assert self._active_search_context is not None
        s: GtkSource.SearchSettings = self._active_search_context.get_settings()
        s.set_regex_enabled(btn.get_active())

    def on_sr_search_setting_wrap_around_toggled(self, btn: Gtk.CheckButton, *args):
        assert self._active_search_context is not None
        s: GtkSource.SearchSettings = self._active_search_context.get_settings()
        s.set_wrap_around(btn.get_active())

    def on_sr_search_setting_match_words_toggled(self, btn: Gtk.CheckButton, *args):
        assert self._active_search_context is not None
        s: GtkSource.SearchSettings = self._active_search_context.get_settings()
        s.set_at_word_boundaries(btn.get_active())

    def on_sr_search_setting_case_sensitive_toggled(self, btn: Gtk.CheckButton, *args):
        assert self._active_search_context is not None
        s: GtkSource.SearchSettings = self._active_search_context.get_settings()
        s.set_case_sensitive(btn.get_active())

    def on_sr_search_clicked(self, btn: Gtk.Button, *args):
        assert self._active_search_context
        buffer: Gtk.TextBuffer = self._active_search_context.get_buffer()
        settings: GtkSource.SearchSettings = self._active_search_context.get_settings()

        settings.set_search_text(builder_get_assert(self.builder, Gtk.Entry, 'sr_search_text').get_text())
        cursor = buffer.get_iter_at_offset(buffer.props.cursor_position)
        search_down = not builder_get_assert(self.builder, Gtk.CheckButton, 'sr_search_setting_search_backwards').get_active()
        if search_down:
            found, match_start, match_end, wrap = self._active_search_context.forward(cursor)
        else:
            found, match_start, match_end, wrap = self._active_search_context.backward(cursor)
        if found:
            if search_down and match_start.get_offset() == cursor.get_offset():
                # Repeat once, to really get down
                found, match_start, match_end, wrap = self._active_search_context.forward(match_end)
            buffer.select_range(match_start, match_end)
            self._explorerscript_view.scroll_to_iter(match_start, 0.1, False, 0.5, 0.5)

    def on_sr_replace_clicked(self, btn: Gtk.Button, *args):
        assert self._active_search_context
        buffer: Gtk.TextBuffer = self._active_search_context.get_buffer()
        settings: GtkSource.SearchSettings = self._active_search_context.get_settings()

        settings.set_search_text(builder_get_assert(self.builder, Gtk.Entry, 'sr_search_text').get_text())
        cursor = buffer.get_iter_at_offset(buffer.props.cursor_position)
        search_down = not builder_get_assert(self.builder, Gtk.CheckButton, 'sr_search_setting_search_backwards').get_active()
        if search_down:
            found, match_start, match_end, wrap = self._active_search_context.forward(cursor)
        else:
            found, match_start, match_end, wrap = self._active_search_context.backward(cursor)
        if found:
            # No running twice this time, because if we search forward2 we take the current pos.
            self._active_search_context.replace(match_start, match_end, builder_get_assert(self.builder, Gtk.Entry, 'sr_replace_text').get_text(), -1)

    def on_sr_replace_all_clicked(self, btn: Gtk.Button, *args):
        assert self._active_search_context
        settings: GtkSource.SearchSettings = self._active_search_context.get_settings()

        settings.set_search_text(builder_get_assert(self.builder, Gtk.Entry, 'sr_search_text').get_text())
        self._active_search_context.replace_all(builder_get_assert(self.builder, Gtk.Entry, 'sr_replace_text').get_text(), -1)

    def on_text_buffer_modified(self, buffer: Gtk.TextBuffer, *args):
        if self._modified_handler:
            self._modified_handler(self, buffer.get_modified())

    # Breapoint Buttons
    def on_code_editor_cntrls_resume_clicked(self, btn: Gtk.Button, *args):
        self.parent.pull_break__resume()

    def on_code_editor_cntrls_step_into_clicked(self, btn: Gtk.Button, *args):
        self.parent.pull_break__step_into()

    def on_code_editor_cntrls_step_over_clicked(self, btn: Gtk.Button, *args):
        self.parent.pull_break__step_over()

    def on_code_editor_cntrls_step_out_clicked(self, btn: Gtk.Button, *args):
        self.parent.pull_break__step_out()

    def on_code_editor_cntrls_step_next_clicked(self, btn: Gtk.Button, *args):
        self.parent.pull_break__step_next()

    def on_code_editor_cntrls_breaks_toggled(self, btn: Gtk.ToggleButton, *args):
        self.parent.parent.global_state__breaks_disabled = btn.get_active()

    def on_code_editor_cntrls_goto_scene_clicked(self,  *args):
        self.file_context.goto_scene(self.parent.get_context())

    def on_code_editor_cntrls_open_textbox_tool_clicked(self, value):
        webbrowser.open_new_tab(TEXTBOX_TOOL_URL)

    def toggle_breaks_disabled(self, value):
        builder_get_assert(self.builder, Gtk.ToggleToolButton, 'code_editor_cntrls_breaks').set_active(value)

    def toggle_spellchecker(self, value):
        try:
            if self._spellchecker_loaded:
                if value:
                    if self._explorerscript_spellcheck:
                        self._explorerscript_spellcheck.enable()
                else:
                    if self._explorerscript_spellcheck:
                        self._explorerscript_spellcheck.disable()
            elif value:
                self._spellchecker_loaded = True
                self._explorerscript_spellcheck = SpellChecker(self._explorerscript_view, 'en_US')
                # Do not correct any special words (Operations, keywords, Pokémon names, constants, etc.)
                # TODO THIS IS SUPER SLOW UNDER WINDOWS.
                #for word in self.parent.get_context().get_special_words():
                #    for part in word.split('_'):
                #        spellchecker.add_to_dictionary(part)
        except BaseException as ex:
            logger.error("Failed toggling/loading spellchecker: ", exc_info=ex)

    # Menu actions
    def menu__cut(self):
        v = self._explorerscript_view
        b: GtkSource.Buffer = v.get_buffer()
        b.cut_clipboard(Gtk.Clipboard.get(Gdk.Atom.intern('CLIPBOARD', False)), v.get_editable())

    def menu__copy(self):
        v = self._explorerscript_view
        b: GtkSource.Buffer = v.get_buffer()
        b.copy_clipboard(Gtk.Clipboard.get(Gdk.Atom.intern('CLIPBOARD', False)))

    def menu__paste(self):
        v = self._explorerscript_view
        b: GtkSource.Buffer = v.get_buffer()
        b.paste_clipboard(Gtk.Clipboard.get(Gdk.Atom.intern('CLIPBOARD', False)), None, v.get_editable())

    def menu__undo(self):
        um = self._explorerscript_view.get_buffer().get_undo_manager()
        if um and um.can_undo():
            um.undo()

    def menu__redo(self):
        um = self._explorerscript_view.get_buffer().get_undo_manager()
        if um and um.can_redo():
            um.redo()

    def menu__search(self):
        widget = self._explorerscript_view
        # SEARCH
        revealer = self._explorerscript_revealer
        search = self._explorerscript_search
        revealer.set_reveal_child(True)
        search.grab_focus()

    def menu__replace(self):
        widget = self._explorerscript_view
        # REPLACE
        if not self._loaded_search_window:
            self._active_search_context = self._explorerscript_search_context
            search_settings: GtkSource.SearchSettings = self._active_search_context.get_settings()
            self._loaded_search_window = builder_get_assert(self.builder, Gtk.Dialog, 'sr_dialog')
            builder_get_assert(self.builder, Gtk.CheckButton, 'sr_search_setting_case_sensitive').set_active(
                search_settings.get_case_sensitive())
            builder_get_assert(self.builder, Gtk.CheckButton, 'sr_search_setting_match_words').set_active(
                search_settings.get_at_word_boundaries())
            builder_get_assert(self.builder, Gtk.CheckButton, 'sr_search_setting_regex').set_active(search_settings.get_regex_enabled())
            builder_get_assert(self.builder, Gtk.CheckButton, 'sr_search_setting_wrap_around').set_active(search_settings.get_wrap_around())
            self._loaded_search_window.set_title(f(_('Search and Replace in {self.filename}')))
            self._loaded_search_window.show_all()

    def switch_style_scheme(self, scheme):
        self._active_scheme = scheme
        if self._explorerscript_view is not None:
            self._explorerscript_view.get_buffer().set_style_scheme(self._active_scheme)
        self._mrk_attrs__execution_line.set_background(self._mix_breakpoint_colors('def:note', 21, 234, '#6D5900'))
        self._mrk_attrs__breaked_line.set_background(self._mix_breakpoint_colors('def:note', 81, 174, '#6D5900'))
        self._mrk_attrs__breakpoint.set_background(self._mix_breakpoint_colors('def:error', 51, 204, '#6D0D00'))

    # Utility
    def _mix_breakpoint_colors(self, mix_style_name, mix_style_alpha, text_style_alpha, fallback_color):
        """Mix the default background color with the error color to get a nice breakpoint bg color"""
        background_mix_style = None
        text_mix_bg_style = None
        try:
            background_mix_style = assert_not_none(self._active_scheme.get_style(mix_style_name)).props.background
        except (AttributeError, AssertionError):
            pass
        if background_mix_style is None:
            background_mix_style = fallback_color
        breakpoint_bg = color_hex_to_rgb(background_mix_style, mix_style_alpha)
        try:
            text_mix_bg_style = assert_not_none(self._active_scheme.get_style('text')).props.background
        except (AttributeError, AssertionError):
            pass
        if text_mix_bg_style is None:
            text_mix_bg_style = '#ffffff'
        text_bg = color_hex_to_rgb(text_mix_bg_style, text_style_alpha)
        return Gdk.RGBA(*get_mixed_color(
            breakpoint_bg, text_bg
        ))

    def _create_editor(self) -> tuple[Gtk.Overlay, GtkSource.View, Gtk.Revealer, Gtk.SearchEntry, GtkSource.SearchContext]:
        ovl: Gtk.Overlay = Gtk.Overlay.new()
        sw: Gtk.ScrolledWindow = Gtk.ScrolledWindow.new()
        view: GtkSource.View = GtkSource.View.new()

        view.set_mark_attributes('breakpoint', self._mrk_attrs__breakpoint, 1)
        view.set_mark_attributes('execution-line', self._mrk_attrs__execution_line, 10)
        view.set_mark_attributes('breaked-line', self._mrk_attrs__breaked_line, 100)

        buffer: GtkSource.Buffer = view.get_buffer()
        gutter: GtkSource.Gutter = view.get_gutter(Gtk.TextWindowType.LEFT)
        view.set_show_line_numbers(True)
        view.set_show_line_marks(True)
        view.set_auto_indent(True)
        view.set_insert_spaces_instead_of_tabs(True)
        view.set_indent_width(4)
        view.set_show_right_margin(True)
        view.set_indent_on_tab(True)
        view.set_highlight_current_line(True)
        view.set_smart_backspace(True)
        view.set_smart_home_end(GtkSource.SmartHomeEndType.BEFORE)
        view.set_monospace(True)
        buffer.set_highlight_matching_brackets(True)
        buffer.set_style_scheme(self._active_scheme)

        gutter.insert(PlayIconRenderer(view), -100)

        view.connect("line-mark-activated", self.on_sourceview_line_mark_activated)
        buffer.connect("delete-range", self.on_sourcebuffer_delete_range)

        buffer.connect("modified-changed", self.on_text_buffer_modified)

        sw.add(view)
        ovl.add(sw)

        # SEARCH
        rvlr: Gtk.Revealer = Gtk.Revealer.new()
        rvlr.get_style_context().add_class('backdrop')
        rvlr.set_valign(Gtk.Align.START)
        rvlr.set_halign(Gtk.Align.END)
        search_frame: Gtk.Frame = Gtk.Frame.new()
        search_frame.set_margin_top(2)
        search_frame.set_margin_bottom(2)
        search_frame.set_margin_left(2)
        search_frame.set_margin_right(2)
        hbox: Gtk.Box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        search: Gtk.SearchEntry = Gtk.SearchEntry.new()
        search.set_size_request(260, -1)
        up_button: Gtk.Button = Gtk.Button.new_from_icon_name('skytemple-go-up-symbolic', Gtk.IconSize.BUTTON)
        up_button.set_can_focus(False)
        down_button: Gtk.Button = Gtk.Button.new_from_icon_name('skytemple-go-down-symbolic', Gtk.IconSize.BUTTON)
        down_button.set_can_focus(False)

        search.connect('search-changed', self.on_search_entry_search_changed)
        search.connect('focus-out-event', self.on_search_entry_focus_out_event)
        up_button.connect('clicked', self.on_search_up_button_clicked, search)
        down_button.connect('clicked', self.on_search_down_button_clicked, search)

        hbox.pack_start(search, False, True, 0)
        hbox.pack_start(up_button, False, True, 0)
        hbox.pack_start(down_button, False, True, 0)
        search_frame.add(hbox)
        rvlr.add(search_frame)
        ovl.add_overlay(rvlr)

        search_context = GtkSource.SearchContext.new(buffer)
        search_context.get_settings().set_wrap_around(True)
        # END SEARCH

        ovl.show_all()
        return ovl, view, rvlr, search, search_context

    @staticmethod
    def _activate_spinner(bx):
        spinner: Gtk.Spinner = Gtk.Spinner.new()
        spinner.show()
        spinner.start()
        bx.pack_start(spinner, True, False, 0)

    def _load_explorerscript_completion(self):
        view = self._explorerscript_view
        completion: GtkSource.Completion = view.get_completion()

        completion.add_provider(GtkSourceCompletionSsbConstants(self.rom_data))
        completion.add_provider(GtkSourceCompletionSsbFunctions(
            filter_special_exps_opcodes(self.rom_data.script_data.op_codes)
        ))
        completion.add_provider(GtkSourceCompletionExplorerScriptStatements())
        CalltipEmitter(
            self._explorerscript_view,
            self.rom_data.script_data.op_codes,
            self.mapname,  # type: ignore
            *self.file_context.get_scene_name_and_type(),  # type: ignore
            self.parent.get_context()  # type: ignore
        )
        StringEventEmitter(self._explorerscript_view, self.parent.get_context())

    @staticmethod
    def _refill_info_bar(info_bar: Gtk.InfoBar, message_type: Gtk.MessageType, text: str):
        info_bar.set_message_type(message_type)
        content: Gtk.Box = info_bar.get_content_area()
        for c in content.get_children():
            content.remove(c)
        lbl: Gtk.Label = Gtk.Label.new(text)
        lbl.set_line_wrap(True)
        content.add(lbl)
        info_bar.set_revealed(True)
        info_bar.show_all()

    def _show_ssbs_es_changed_warning(self):
        md = self.parent.parent.context.message_dialog(
            self._main_window,
            Gtk.DialogFlags.MODAL, Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.NONE,
            f(_("The ExplorerScript source code does not match the compiled script that is present in the ROM.\n"
                "Do you want to keep your ExplorerScript source code, or reload (decompile) it from ROM?\n"
                "Warning: If you choose to reload, you will lose your file, including all comments in it.")),
            title=_("ExplorerScript Inconsistency")
        )
        md.add_button(_('Reload from ROM'), Gtk.ResponseType.YES)
        md.add_button(_('Keep ExplorerScript source code'), Gtk.ResponseType.NO)

        response = md.run()
        md.destroy()

        if response == Gtk.ResponseType.YES:
            return True
        return False


def get_mixed_color(color_rgba1, color_rgba2):
    red   = (color_rgba1[0] * (255 - color_rgba2[3]) + color_rgba2[0] * color_rgba2[3]) / 255
    green = (color_rgba1[1] * (255 - color_rgba2[3]) + color_rgba2[1] * color_rgba2[3]) / 255
    blue  = (color_rgba1[2] * (255 - color_rgba2[3]) + color_rgba2[2] * color_rgba2[3]) / 255
    return int(red) / 255, int(green) / 255, int(blue) / 255, 1.0


def color_hex_to_rgb(hexx, alpha):
    return tuple(int(hexx.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)


class PlayIconRenderer(GtkSource.GutterRendererPixbuf):
    """Renders a play"""
    def __init__(self, view, **properties):
        super().__init__(**properties)
        self.view: GtkSource.View = view
        self.empty = Gdk.pixbuf_get_from_surface(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1), 0, 0, 1, 1)
        self.set_size(12 * 3)
        self.set_padding(5, 3)
        icon_theme: Gtk.IconTheme = Gtk.IconTheme.get_for_screen(self.view.get_screen())
        self._icon_actor = icon_theme.load_icon(ICON_ACTOR[:-9] + '-gutter', 12, Gtk.IconLookupFlags.FORCE_SIZE).copy()  # type: ignore
        self._icon_object = icon_theme.load_icon(ICON_OBJECT[:-9] + '-gutter', 12, Gtk.IconLookupFlags.FORCE_SIZE).copy()  # type: ignore
        self._icon_performer = icon_theme.load_icon(ICON_PERFORMER[:-9] + '-gutter', 12, Gtk.IconLookupFlags.FORCE_SIZE).copy()  # type: ignore
        self._icon_global_script = icon_theme.load_icon(ICON_GLOBAL_SCRIPT[:-9] + '-gutter', 12, Gtk.IconLookupFlags.FORCE_SIZE).copy()  # type: ignore

    def do_query_data(self, start: Gtk.TextIter, end: Gtk.TextIter, state: GtkSource.GutterRendererState):
        view: GtkSource.View = cast(GtkSource.View, self.get_view())
        buffer: GtkSource.Buffer = view.get_buffer()
        execution_marks = buffer.get_source_marks_at_line(start.get_line(), 'execution-line')
        breaked_marks = buffer.get_source_marks_at_line(start.get_line(), 'breaked-line')

        if len(breaked_marks) > 0:
            type_id = -1
            slot_id = -1
            if len(execution_marks) > 0:
                _, type_id, slot_id = EXECUTION_LINE_PATTERN.match(execution_marks[0].get_name()).groups()  # type: ignore
            self.set_pixbuf(create_breaked_line_icon(
                int(type_id), int(slot_id), self._icon_actor, self._icon_object, self._icon_performer, self._icon_global_script
            ))
            return
        if len(execution_marks) > 0:
            _, type_id, slot_id = EXECUTION_LINE_PATTERN.match(execution_marks[0].get_name()).groups()  # type: ignore
            # Don't show for global
            self.set_pixbuf(create_execution_line_icon(
                int(type_id), int(slot_id), self._icon_actor, self._icon_object, self._icon_performer, self._icon_global_script
            ))
            return
        self.set_pixbuf(self.empty)
