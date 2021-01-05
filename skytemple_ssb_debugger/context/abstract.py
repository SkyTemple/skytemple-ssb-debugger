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
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, List, Iterable, Type

from gi.repository import Gtk

from explorerscript.source_map import SourceMapPositionMark
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.project_file_manager import ProjectFileManager
from skytemple_files.common.script_util import ScriptFiles

if TYPE_CHECKING:
    from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager
    from skytemple_ssb_debugger.model.ssb_files import SsbLoadedFile

PROJECT_DIR_SUBDIR_NAME = 'debugger'
PROJECT_DIR_MACRO_NAME = 'Macros'

# todo: refactor
EXPS_KEYWORDS = (
    "import",
    "coro",
    "def",
    "macro",
    "for_actor",
    "for_object",
    "for_performer",
    "alias",
    "previous",
    "not",
    "if",
    "elseif",
    "else",
    "forever",
    "with",
    "switch",
    "debug",
    "edit",
    "variation",
    "random",
    "sector",
    "menu2",
    "menu",
    "case",
    "default",
    "clear",
    "reset",
    "init",
    "scn",
    "dungeon_result",
    "adventure_log",
    "continue",
    "break",
    "break_loop",
    "return",
    "end",
    "hold",
    "jump",
    "while",
    "for",
    # Weak keywords
    "TRUE",
    "FALSE",
    "actor",
    "object",
    "performer",
    "value",
    "dungeon_mode",
)


class AbstractDebuggerControlContext(ABC):
    """
    Context that controls what options are available in the UI, where the UI get's it's data from,
    and hooks to handle some events.

    This is used to allow the debugger GUI to be available as a standalone application and as a UI managed by
    the SkyTemple main application.
    """

    @abstractmethod
    def allows_interactive_file_management(self) -> bool:
        """Returns whether or not this context allows the user to load ROMs via the UI"""

    @abstractmethod
    def before_quit(self) -> bool:
        """Handles quit requests. If False is returned, the quit is aborted."""

    @abstractmethod
    def on_quit(self):
        """Handles the quit of the debugger."""

    @abstractmethod
    def on_focus(self):
        """Event handler for the debugger gaining focus. May be triggered even if still in focus."""

    @abstractmethod
    def on_blur(self):
        """Event handler for the debugger losing focus. May be triggered even if already had no focus."""

    @abstractmethod
    def on_selected_string_changed(self, string: str):
        """
        Called when the user selected* a new string in a script editor or the selected string was
        modified.
        *=cursor placed inside of string
        """

    @abstractmethod
    def show_ssb_script_editor(self) -> bool:
        """Whether or not the tab for SSBScript editing should be shown in the editor."""

    @abstractmethod
    def open_rom(self, filename: str):
        """
        Opens a ROM project.
        May raise NotImplementedError if self.allows_interactive_file_management() returns False.
        """

    @abstractmethod
    def get_project_dir(self) -> str:
        """Returns the project directory."""

    def get_project_debugger_dir(self) -> str:
        """Returns the debugger directory inside the project."""
        dir = os.path.join(self.get_project_dir(), PROJECT_DIR_SUBDIR_NAME)
        os.makedirs(dir, exist_ok=True)
        return dir

    def get_project_macro_dir(self) -> str:
        """Returns the Macros directory inside the project."""
        dir = os.path.join(self.get_project_dir(), PROJECT_DIR_MACRO_NAME)
        os.makedirs(dir, exist_ok=True)
        return dir

    @abstractmethod
    def load_script_files(self) -> ScriptFiles:
        """Returns the information of the script files inside the ROM."""

    @abstractmethod
    def is_project_loaded(self) -> bool:
        """Returns whether or not a ROM is loaded."""

    @abstractmethod
    def get_rom_filename(self) -> str:
        """Returns the filename of the ROM loaded."""

    @abstractmethod
    def save_rom(self):
        """Saves the ROM."""

    @abstractmethod
    def get_static_data(self) -> Pmd2Data:
        """Returns the PPMDU configuration for the currently open ROM."""

    @abstractmethod
    def get_project_filemanager(self) -> ProjectFileManager:
        """Returns the project file manager for the currently open ROM."""

    @abstractmethod
    def get_ssb(self, filename, ssb_file_manager: 'SsbFileManager') -> 'SsbLoadedFile':
        """Returns the SSB with the given filename from the ROM."""

    @abstractmethod
    def on_script_edit(self, filename):
        """Event handler for when the debugger starts editing the specified script"""

    @abstractmethod
    def save_ssb(self, filename, ssb_model, ssb_file_manager: 'SsbFileManager'):
        """Updates an SSB model in the ROM and then saves the ROM."""

    @abstractmethod
    def open_scene_editor(self, type_of_scene, filename):
        """
        If possible, open the scene editor for the scene provided.
        Both the SSB filename or a SSA/SSS/SSE filename may used.
        On error show dialog.
        """

    @abstractmethod
    def open_scene_editor_for_map(self, map_name):
        """
        If possible, open the scene editor for the map provided.
        On error show dialog.
        """

    @abstractmethod
    def edit_position_mark(self, mapname: str, scene_name: str, scene_type: str,
                           pos_marks: List[SourceMapPositionMark], pos_mark_to_edit: int) -> bool:
        """
        Edit position marks of an SSB file inside a scene editor, using mapname as a
        background and the scene's entities for reference.
        Marks are edited in place.
        On error show dialog.
        On success returns True.
        """

    @abstractmethod
    def display_error(self, exc_info, error_message, error_title='SkyTemple Script Engine Debugger - Error'):
        """
        Display an error dialog for the user.
        :param exc_info: Return value of sys.exc_info inside the 'except' block. May be None if no exception is being
                         handled.
        :param error_message: The message to display to the user.
        :param error_title: The title of the dialog to display.
        """

    @abstractmethod
    def get_special_words(self) -> Iterable[str]:
        """
        Returns a list of special words which should be ignored by spellchecking.
        """

    @staticmethod
    @abstractmethod
    def message_dialog_cls() -> Type[Gtk.MessageDialog]:
        """Returns the class for use for MessageDialogs. Must extend Gtk.MessageDialog."""
