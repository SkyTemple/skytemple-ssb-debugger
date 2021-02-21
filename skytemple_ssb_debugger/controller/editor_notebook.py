"""Controller for the collection of all open ssb editors."""
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
import os
from typing import Dict, Optional, List, Tuple, TYPE_CHECKING

from gi.repository import Gtk, Pango

from explorerscript.ssb_converting.ssb_data_types import SsbRoutineType
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_debugger.controller.script_editor import ScriptEditorController
from skytemple_ssb_debugger.model.breakpoint_manager import BreakpointManager
from skytemple_ssb_debugger.model.breakpoint_state import BreakpointState, BreakpointStateType
from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager
from ..context.abstract import AbstractDebuggerControlContext
from ..model.breakpoint_file_state import BreakpointFileState
from ..model.script_file_context.abstract import AbstractScriptFileContext
from ..model.script_file_context.exps_macro import ExpsMacroFileScriptFileContext
from ..model.script_file_context.ssb_file import SsbFileScriptFileContext
from skytemple_files.common.i18n_util import f, _

if TYPE_CHECKING:
    from .main import MainController


class EditorNotebookController:
    def __init__(self, builder: Gtk.Builder, parent: 'MainController',
                 main_window: Gtk.Window, enable_explorerscript=True):
        self.builder = builder
        self.parent = parent
        self.file_manager: Optional[SsbFileManager] = None
        self.breakpoint_manager: Optional[BreakpointManager] = None
        self.rom_data: Optional[Pmd2Data] = None
        self._open_editors: Dict[str, ScriptEditorController] = {}
        self._notebook: Gtk.Notebook = builder.get_object('code_editor_notebook')
        self._cached_hanger_halt_lines = {}
        self._cached_file_bpnt_state: BreakpointFileState = None
        self.enable_explorerscript = enable_explorerscript
        self._main_window = main_window

    def init(self, file_manager: SsbFileManager, breakpoint_manager: BreakpointManager, rom_data: Pmd2Data):
        self.file_manager = file_manager
        self.rom_data = rom_data
        self.breakpoint_manager = breakpoint_manager
        self.breakpoint_manager.register_callbacks(self.on_breakpoint_added, self.on_breakpoint_removed)

    @property
    def currently_open(self) -> Optional[ScriptEditorController]:
        if self._notebook.get_current_page() > -1:
            wdg = self._notebook.get_nth_page(self._notebook.get_current_page())
            for c in self._open_editors.values():
                if c.get_root_object() == wdg:
                    return c
        return None

    def open_ssb(self, ssb_rom_path: str):
        context = SsbFileScriptFileContext(
            self.file_manager.open_in_editor(ssb_rom_path),
            self.parent.get_scene_type_for(ssb_rom_path),
            self.parent.get_scene_name_for(ssb_rom_path),
            self.breakpoint_manager, self
        )
        return self._open_common(ssb_rom_path, context, mapname=ssb_rom_path.split('/')[1])

    def open_exps_macro(self, abs_path: str):
        context = ExpsMacroFileScriptFileContext(
            abs_path, self.file_manager, self.breakpoint_manager, self
        )
        return self._open_common(abs_path, context)

    def _open_common(self, registered_fname: str, file_context: AbstractScriptFileContext, mapname: str = None):
        if self.file_manager:
            if registered_fname in self._open_editors:
                self._notebook.set_current_page(self._notebook.page_num(
                    self._open_editors[registered_fname].get_root_object()
                ))
            else:
                editor_controller = ScriptEditorController(
                    self, self._main_window, file_context,
                    self.rom_data, self.on_ssb_editor_modified, mapname, self.enable_explorerscript,
                    not self.get_context().show_ssb_script_editor()
                )
                for ssb_path, halt_lines in self._cached_hanger_halt_lines.items():
                    editor_controller.insert_hanger_halt_lines(ssb_path, halt_lines)
                if self._cached_file_bpnt_state is not None:
                    editor_controller.toggle_debugging_controls(True)
                    editor_controller.on_break_pulled(
                        self._cached_file_bpnt_state.ssb_filename,
                        self._cached_file_bpnt_state.opcode_addr,
                        self._cached_file_bpnt_state.halted_on_call
                    )
                current_page = self._notebook.get_current_page()
                root = editor_controller.get_root_object()
                self._open_editors[registered_fname] = editor_controller
                pnum = self._notebook.insert_page(
                    root, tab_label_close_button(
                        registered_fname, self.close_tab
                    ), current_page + 1
                )
                self._notebook.child_set_property(root, 'menu-label', registered_fname)
                self._notebook.set_tab_reorderable(root, True)
                self._notebook.set_current_page(pnum)

    def close_all_tabs(self):
        """Close all tabs. If any of the tabs was not closed, False is returned."""
        all_returned_true = True
        for filename in list(self._open_editors.keys()):
            if not self.close_tab(filename):
                all_returned_true = False
        return all_returned_true

    def close_open_tab(self):
        if self._notebook.get_current_page() > -1:
            wdg = self._notebook.get_nth_page(self._notebook.get_current_page())
            for filename, c in self._open_editors.items():
                if c.get_root_object() == wdg:
                    self.close_tab(filename)
                    return

    def close_tab(self, filename: str):
        """Close tab for filename. If the tab was not closed, False is returned."""
        if filename in self._open_editors:
            controller = self._open_editors[filename]
            pnum = self._notebook.page_num(controller.get_root_object())

            # SAVE WARNING!
            if controller.has_changes:
                response = self._show_are_you_sure(filename)
                if response == 1:
                    # Save first.
                    controller.save()
                    # TODO: we just cancel atm, because the saving is done async. It would probably be nice to also
                    #       exit, when it's done without error
                    return False
                if response == 0:
                    # okay, discard.
                    pass
                else:
                    return False

            # Signal closing to file manager and check if breaking will still be possible.
            def warning_callback():
                if self._show_warning_breaking() != Gtk.ResponseType.YES:
                    return False
                return True

            if filename[-4:] == '.ssb':
                if not self.file_manager.close_in_editor(filename, warning_callback):
                    return False

            self._notebook.remove_page(pnum)
            controller.destroy()
            del self._open_editors[filename]
            return True
            
    def focus_by_opcode_addr(self, ssb_filename: str,  opcode_addr: int):
        """
        Pull an editor into focus and tell it to jump to opcode_addr. 
        If the editor is not open, it's opened before.
        If a BreakpointFileState is currently registered (because the debugger is halted), then
        calling this method may open the ExplorerScript macro instead that handles the breakpoint,
        if applicable.
        """
        editor_filename = ssb_filename
        if self._cached_file_bpnt_state is not None:
            editor_filename = self._cached_file_bpnt_state.handler_filename
        is_opening_ssb = editor_filename[-4:] == '.ssb'
        if editor_filename not in self._open_editors:
            if is_opening_ssb:
                self.open_ssb(editor_filename)
            else:
                self.open_exps_macro(editor_filename)
        else:
            self._notebook.set_current_page(self._notebook.page_num(self._open_editors[editor_filename].get_root_object()))
        self._open_editors[editor_filename].focus_opcode(ssb_filename, opcode_addr)

    def break_pulled(self, state: BreakpointState):
        """The debugger paused. Enable debugger controls for file_name."""
        file_state = state.get_file_state()
        for editor in self._open_editors.values():
            editor.toggle_debugging_controls(True)
            editor.on_break_pulled(file_state.ssb_filename, file_state.opcode_addr, file_state.halted_on_call)
        self._cached_file_bpnt_state = file_state
        state.add_release_hook(self.break_released)

    def step_into_macro_call(self, state: BreakpointFileState):
        """The debugger paused. Enable debugger controls for file_name."""
        for editor in self._open_editors.values():
            editor.toggle_debugging_controls(True)
            editor.on_break_pulled(state.ssb_filename, state.opcode_addr, state.halted_on_call)

    def break_released(self, state: BreakpointState):
        """The debugger is no longer paused, disable all debugging controls."""
        for editor in self._open_editors.values():
            editor.toggle_debugging_controls(False)
            editor.on_break_released()
        self._cached_file_bpnt_state = None

    def insert_hanger_halt_lines(self, halt_lines: Dict[str, List[Tuple[SsbRoutineType, int, int]]]):
        """Mark the current execution position for all running scripts. Dict filename -> list (type, id, opcode_addr)"""
        for filename, lines in halt_lines.items():
            self._cached_hanger_halt_lines[filename] = lines
            if filename in self._open_editors.keys():
                self._open_editors[filename].insert_hanger_halt_lines(filename, lines)

    def remove_hanger_halt_lines(self):
        """Remove the marks for the current script execution points"""
        self._cached_hanger_halt_lines = {}
        for editor in self._open_editors.values():
            editor.remove_hanger_halt_lines()

    def on_breakpoint_added(self, ssb_filename, opcode_offset):
        for editor in self._open_editors.values():
            editor.on_breakpoint_added(ssb_filename, opcode_offset)

    def on_breakpoint_removed(self, filename, opcode_offset):
        for editor in self._open_editors.values():
            editor.on_breakpoint_removed(filename, opcode_offset)

    def on_ssb_editor_modified(self, controller: ScriptEditorController, modified: bool):
        lbl_box: Gtk.Box = self._notebook.get_tab_label(controller.get_root_object())
        lbl: Gtk.Label = lbl_box.get_children()[0]
        pathsep = os.path.sep
        if controller.filename.endswith('.ssb'):
            pathsep = '/'
        filename = controller.filename.split(pathsep)[-1]
        # TODO: Alert SkyTemple main UI somehow? (via FileManager?)
        if modified:
            lbl.set_markup(f'<i>{filename}*</i>')
        else:
            lbl.set_markup(f'{filename}')

    def on_ssb_changed_externally(self, ssb_filename, ready_to_reload):
        """
        A ssb file was re-compiled from outside of it's script editor.
        Tell all editors about that, so that they can react if their context manages the file.
        ready_to_reload is the return value from SsbFileManager.save_from_explorerscript for this script.
        """
        for editor in self._open_editors.values():
            editor.on_ssb_changed_externally(ssb_filename, ready_to_reload)

    def on_exps_macro_ssb_changed(self, exps_abs_path, ssb_filename):
        """
        The ssb file ssb_filename was changed and it imports the ExplorerScript macro file with the absolute path
        of exps_abs_path. Let the file contexts of the open editors handle this.
        """
        for editor in self._open_editors.values():
            editor.on_exps_macro_ssb_changed(exps_abs_path, ssb_filename)

    def pull_break__resume(self):
        self.parent.emu_resume(BreakpointStateType.RESUME)

    def pull_break__step_into(self):
        if self._cached_file_bpnt_state and self._cached_file_bpnt_state.halted_on_call:
            self.parent.step_into_macro_call(self._cached_file_bpnt_state)
            return
        self.parent.emu_resume(BreakpointStateType.STEP_INTO)

    def pull_break__step_over(self):
        if self._cached_file_bpnt_state and self._cached_file_bpnt_state.step_over_addr:
            return self.parent.emu_resume(BreakpointStateType.STEP_MANUAL, self._cached_file_bpnt_state.step_over_addr)
        self.parent.emu_resume(BreakpointStateType.STEP_OVER)

    def pull_break__step_out(self):
        if self._cached_file_bpnt_state and self._cached_file_bpnt_state.step_out_addr:
            return self.parent.emu_resume(BreakpointStateType.STEP_MANUAL, self._cached_file_bpnt_state.step_out_addr)
        self.parent.emu_resume(BreakpointStateType.STEP_OUT)

    def pull_break__step_next(self):
        self.parent.emu_resume(BreakpointStateType.STEP_NEXT)

    def toggle_breaks_disabled(self, value):
        for editor in self._open_editors.values():
            editor.toggle_breaks_disabled(value)

    def save_all(self):
        for editor in self._open_editors.values():
            editor.save()

    def switch_style_scheme(self, scheme):
        for editor in self._open_editors.values():
            editor.switch_style_scheme(scheme)

    def toggle_spellchecker(self, value):
        for editor in self._open_editors.values():
            editor.toggle_spellchecker(value)

    def get_context(self) -> AbstractDebuggerControlContext:
        return self.parent.context

    def on_page_changed(self, page_widget):
        """Trigger the context event for script editing"""
        current_open = None
        for c in self._open_editors.values():
            if c.get_root_object() == page_widget:
                current_open = c
                break
        if current_open is not None:
            self.get_context().on_script_edit(current_open.filename)

    def _show_are_you_sure(self, filename):
        dialog: Gtk.MessageDialog = self.parent.context.message_dialog_cls()(
            self._main_window,
            Gtk.DialogFlags.MODAL,
            Gtk.MessageType.WARNING,
            Gtk.ButtonsType.NONE, f(_("Do you want to save changes to {filename}?"))
        )
        dont_save: Gtk.Widget = dialog.add_button(_("Don't Save"), 0)
        dont_save.get_style_context().add_class('destructive-action')
        dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("_Save"), 1)
        dialog.format_secondary_text(_("If you don't save, your changes will be lost."))
        response = dialog.run()
        dialog.destroy()
        return response

    def _show_warning_breaking(self):
        md = self.parent.context.message_dialog_cls()(
            self._main_window,
            Gtk.DialogFlags.MODAL,
            Gtk.MessageType.WARNING,
            Gtk.ButtonsType.YES_NO,
            _("The file is still loaded in RAM! Currently you are still able to debug using the old cached "
              "information stored in the editor.\nIf you close the editor, you won't be able to debug this "
              "file until it is reloaded in RAM.\n\nDo you still want to close this file?"),
            title=_("Warning!")
        )

        response = md.run()
        md.destroy()
        return response


def tab_label_close_button(filename, close_callback):
    lbl = filename.split('/')[-1]
    if lbl[-4:] == '.ssb':
        lbl = lbl[:-4]
    else:
        lbl = lbl[:-5]
    label: Gtk.Label = Gtk.Label.new(lbl)
    label.set_ellipsize(Pango.EllipsizeMode.START)
    label.props.halign = Gtk.Align.CENTER
    label.set_tooltip_text(filename)
    label.set_width_chars(10)

    button: Gtk.Button = Gtk.Button.new_from_icon_name('window-close-symbolic', Gtk.IconSize.MENU)
    button.set_tooltip_text(_('Close'))
    button.set_relief(Gtk.ReliefStyle.NONE)
    button.set_focus_on_click(False)
    button.connect('clicked', lambda *args: close_callback(filename))

    box: Gtk.Box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 10)
    box.pack_start(label, True, True, 0)
    box.pack_start(button, True, False, 0)
    box.show_all()
    return box
