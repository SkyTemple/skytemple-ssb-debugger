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
import logging
import traceback
from threading import Lock
from typing import Optional, TYPE_CHECKING, Dict, List, Iterable

import gi

from explorerscript.source_map import SourceMapPositionMark
from skytemple_files.script.ssb.constants import SsbConstant
from skytemple_ssb_emulator import emulator_shutdown

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from ndspy.rom import NintendoDSRom

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.project_file_manager import ProjectFileManager
from skytemple_files.common.script_util import ScriptFiles, load_script_files, SCRIPT_DIR
from skytemple_files.common.types.file_types import FileType
from skytemple_files.common.util import get_rom_folder, get_ppmdu_config_for_rom, Capturable
from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext, EXPS_KEYWORDS
from skytemple_ssb_debugger.model.ssb_files.file import SsbLoadedFile

if TYPE_CHECKING:
    from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager
logger = logging.getLogger(__name__)
file_load_lock = Lock()


class StandaloneDebuggerControlContext(AbstractDebuggerControlContext):
    """Context for running the debugger as a standalone application."""

    def __init__(self, main_window: Gtk.Window):
        self._rom: Optional[NintendoDSRom] = None
        self._rom_filename: Optional[str] = None
        self._project_fm: Optional[ProjectFileManager] = None
        self._static_data: Optional[Pmd2Data] = None
        self._open_files: Dict[str, SsbLoadedFile] = {}
        self._main_window = main_window

    def allows_interactive_file_management(self) -> bool:
        return True

    def before_quit(self) -> bool:
        return True

    def on_quit(self):
        Gtk.main_quit()
        emulator_shutdown()

    def on_focus(self):
        pass

    def on_blur(self):
        pass

    def on_selected_string_changed(self, string: str):
        pass

    def show_ssb_script_editor(self) -> bool:
        return True

    def open_rom(self, filename: str):
        self._rom = NintendoDSRom.fromFile(filename)
        self._rom_filename = filename
        self._project_fm = ProjectFileManager(filename)
        self._static_data = get_ppmdu_config_for_rom(self._rom)
        self._open_files = {}

    def get_project_dir(self) -> str:
        assert self._project_fm is not None
        return self._project_fm.dir()

    def load_script_files(self) -> ScriptFiles:
        assert self._rom is not None
        folder = get_rom_folder(self._rom, SCRIPT_DIR)
        assert folder is not None
        return load_script_files(folder)

    def is_project_loaded(self) -> bool:
        return self._rom is not None

    def get_rom_filename(self) -> str:
        self._check_loaded()
        assert self._rom_filename is not None
        return self._rom_filename

    def save_rom(self):
        self._check_loaded()
        assert self._rom_filename is not None and self._rom is not None
        self._rom.saveToFile(self._rom_filename, updateDeviceCapacity=True)

    def get_static_data(self) -> Pmd2Data:
        self._check_loaded()
        assert self._static_data is not None
        return self._static_data

    def get_project_filemanager(self) -> ProjectFileManager:
        self._check_loaded()
        assert self._project_fm is not None
        return self._project_fm

    def get_ssb(self, filename, ssb_file_manager: 'SsbFileManager') -> 'SsbLoadedFile':
        assert self._project_fm is not None and self._rom is not None
        with file_load_lock:
            self._check_loaded()
            if filename not in self._open_files:
                try:
                    ssb_bin = self._rom.getFileByName(filename)
                except ValueError as err:
                    raise FileNotFoundError(str(err)) from err
                self._open_files[filename] = SsbLoadedFile(
                    filename, FileType.SSB.deserialize(ssb_bin, self._static_data),
                    ssb_file_manager, self._project_fm
                )
                self._open_files[filename].exps.ssb_hash = ssb_file_manager.hash(ssb_bin)
            return self._open_files[filename]

    def on_script_edit(self, filename):
        pass

    def save_ssb(self, filename, ssb_model, ssb_file_manager: 'SsbFileManager'):
        assert self._rom is not None
        with file_load_lock:
            self._check_loaded()
            self._rom.setFileByName(
                filename, FileType.SSB.serialize(ssb_model, self._static_data)
            )
            self.save_rom()

    def _check_loaded(self):
        if self._rom is None:
            raise RuntimeError("No ROM is currently loaded.")

    def open_scene_editor(self, type_of_scene, filename):
        self._scene_editing_not_supported()

    def open_scene_editor_for_map(self, map_name):
        self._scene_editing_not_supported()

    def edit_position_mark(self, mapname: str, scene_name: str, scene_type: str, pos_marks: List[SourceMapPositionMark],
                           pos_mark_to_edit: int) -> bool:
        self.display_error(
            None,
            f"Visual Position Mark editing is not supported in the standalone version of "
            f"SkyTemple Script Engine Debugger.\n"
            f"Please open the debugger through the SkyTemple main application "
            f"instead."
        )
        return False

    def _scene_editing_not_supported(self):
        self.display_error(
            None,
            f"Scene editing is not supported in the standalone version of "
            f"SkyTemple Script Engine Debugger.\n"
            f"Please open the debugger through the SkyTemple main application "
            f"instead.",
            "Action not supported"
        )

    def display_error(
            self, exc_info, error_message,
            error_title='SkyTemple Script Engine Debugger - Error',
            *, context: Optional[Dict[str, Capturable]] = None
    ):
        logger.error(error_message, exc_info=exc_info)
        exc_info_str = ''
        if exc_info:
            exc_info_str = '\n' + ''.join(traceback.format_exception(exc_info[0], value=exc_info[1], tb=exc_info[2]))
        md = self.message_dialog(self._main_window,
                                 Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                                 Gtk.ButtonsType.OK,
                                 f"{error_message}{exc_info_str}",
                                 title=error_title)
        md.set_position(Gtk.WindowPosition.CENTER)
        md.run()
        md.destroy()

    def capture_error(
            self, exc_info,
            *, context: Optional[Dict[str, Capturable]] = None
    ):
        pass

    def get_special_words(self) -> Iterable[str]:
        """
        Just returns the script operations and constants,
        more data is only supported by the main SkyTemple application
        """
        assert self._static_data is not None
        yield from self._static_data.script_data.op_codes__by_name.keys()
        yield from (x.name.replace('$', '') for x in SsbConstant.collect_all(self._static_data.script_data))
        yield from EXPS_KEYWORDS

    @staticmethod
    def message_dialog(
        parent: Optional[Gtk.Window],
        dialog_flags: Gtk.DialogFlags,
        message_type: Gtk.MessageType,
        buttons_type: Gtk.ButtonsType,
        text: str,
        **kwargs
    ):
        kwargs.update({
            'destroy_with_parent': (dialog_flags & Gtk.DialogFlags.DESTROY_WITH_PARENT) > 0,
            'modal': (dialog_flags & Gtk.DialogFlags.MODAL) > 0,
            'use_header_bar': (dialog_flags & Gtk.DialogFlags.USE_HEADER_BAR) > 0,
            'message_type': message_type,
            'buttons': buttons_type,
            'text': text
        })
        if parent is not None:
            kwargs['parent'] = parent
        return Gtk.MessageDialog(**kwargs)
