"""Controller for the collection of all open ssb editors."""
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
from typing import Dict, Optional

from gi.repository import Gtk, Pango

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.script_util import SCRIPT_DIR
from skytemple_ssb_debugger.controller.ssb_editor import SSBEditorController
from skytemple_ssb_debugger.model.breakpoint_manager import BreakpointManager
from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager


class CodeEditorController:
    def __init__(self, builder: Gtk.Builder):
        self.builder = builder
        self.file_manager: Optional[SsbFileManager] = None
        self.breakpoint_manager: Optional[BreakpointManager] = None
        self.rom_data: Optional[Pmd2Data] = None
        self._open_editors: Dict[str, SSBEditorController] = {}
        self._open_editors_by_page_num: Dict[int, SSBEditorController] = {}
        self._notebook: Gtk.Notebook = builder.get_object('code_editor_notebook')

    def init(self, file_manager: SsbFileManager, breakpoint_manager: BreakpointManager, rom_data: Pmd2Data):
        self.file_manager = file_manager
        self.rom_data = rom_data
        self.breakpoint_manager = breakpoint_manager
        self.breakpoint_manager.register_callbacks(self.on_breakpoint_added, self.on_breakpoint_removed)

    @property
    def currently_open(self) -> Optional[SSBEditorController]:
        if self._notebook.get_current_page() > -1:
            return self._open_editors_by_page_num[self._notebook.get_current_page()]
        return None

    def open(self, filename: str):
        if self.file_manager:
            if filename in self._open_editors:
                self._notebook.set_current_page(self._open_editors[filename])
            else:
                editor_controller = SSBEditorController(
                    self, self.breakpoint_manager, self.file_manager.open_in_editor(SCRIPT_DIR + '/' + filename),
                    self.rom_data, self.on_ssb_editor_modified
                )
                current_page = self._notebook.get_current_page()
                root = editor_controller.get_root_object()
                pnum = self._notebook.insert_page(
                    root, tab_label_close_button(
                        filename, self.close_tab
                    ), current_page + 1
                )
                self._notebook.child_set_property(root, 'menu-label', filename)
                self._notebook.set_tab_reorderable(root, True)
                self._notebook.set_current_page(pnum)
                self._open_editors[filename] = editor_controller
                self._open_editors_by_page_num[pnum] = editor_controller

    def close_tab(self, filename: str):
        if filename in self._open_editors:
            controller = self._open_editors[filename]
            pnum = self._notebook.page_num(controller.get_root_object())

            # SAVE WARNING!
            if controller.has_changes:
                response = self._show_are_you_sure(filename)
                if response == 1:
                    # Save first.
                    controller.save()
                if response == 0:
                    # okay, discard.
                    pass
                else:
                    return

            # Signal closing to file manager and check if breaking will still be possible.
            def warning_callback():
                if self._show_warning_breaking() != Gtk.ResponseType.YES:
                    return False
                return True

            if not self.file_manager.close_in_editor(SCRIPT_DIR + '/' + filename, warning_callback):
                return

            self._notebook.remove_page(pnum)
            controller.destroy()
            del self._open_editors[filename]
            del self._open_editors_by_page_num[pnum]

    def on_breakpoint_added(self, filename, routine_id, opcode_offset):
        if filename[7:] in self._open_editors:
            self._open_editors[filename[7:]].on_breakpoint_added(routine_id, opcode_offset)

    def on_breakpoint_removed(self, filename, routine_id, opcode_offset):
        if filename[7:] in self._open_editors:
            self._open_editors[filename[7:]].on_breakpoint_removed(routine_id, opcode_offset)

    def on_ssb_editor_modified(self, controller: SSBEditorController, modified: bool):
        lbl_box: Gtk.Box = self._notebook.get_tab_label(controller.get_root_object())
        lbl: Gtk.Label = lbl_box.get_children()[0]
        filename = controller.filename.split('/')[-1][:-4]
        # TODO: Alert SkyTemple main UI somehow? (via FileManager?)
        if modified:
            lbl.set_markup(f'<i>{filename}*</i>')
        else:
            lbl.set_markup(f'{filename}')

    def _show_are_you_sure(self, filename):
        dialog: Gtk.MessageDialog = Gtk.MessageDialog(
            None,
            Gtk.DialogFlags.MODAL,
            Gtk.MessageType.WARNING,
            Gtk.ButtonsType.NONE, f"Do you want to save changes to {filename}?"
        )
        dont_save: Gtk.Widget = dialog.add_button("Don't Save", 0)
        dont_save.get_style_context().add_class('destructive-action')
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", 1)
        dialog.format_secondary_text(f"If you don't save, your changes will be lost.")
        response = dialog.run()
        dialog.destroy()
        return response

    def _show_warning_breaking(self):
        md = Gtk.MessageDialog(
            None,
            Gtk.DialogFlags.MODAL,
            Gtk.MessageType.WARNING,
            Gtk.ButtonsType.YES_NO,
            f"The file is still loaded in RAM! Currently you are still able to debug using the old cached "
            f"information stored in the editor.\nIf you close the editor, you won't be able to debug this "
            f"file until it is reloaded in RAM.\n\nDo you still want to close this file?",
            title="Warning!"
        )

        response = md.run()
        md.destroy()
        return response


def tab_label_close_button(filename, close_callback):
    label: Gtk.Label = Gtk.Label.new(filename.split('/')[-1][:-4])
    label.set_ellipsize(Pango.EllipsizeMode.START)
    label.props.halign = Gtk.Align.CENTER
    label.set_tooltip_text(filename)
    label.set_width_chars(10)

    button: Gtk.Button = Gtk.Button.new_from_icon_name('window-close', Gtk.IconSize.MENU)
    button.set_tooltip_text('Close')
    button.set_relief(Gtk.ReliefStyle.NONE)
    button.set_focus_on_click(False)
    button.connect('clicked', lambda *args: close_callback(filename))

    box: Gtk.Box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 10)
    box.pack_start(label, True, True, 0)
    box.pack_start(button, True, False, 0)
    box.show_all()
    return box
