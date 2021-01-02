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
from abc import ABC, abstractmethod
from typing import List, Optional, Callable, Tuple

from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_ssb_debugger.model.breakpoint_manager import BreakpointManager
from skytemple_ssb_debugger.model.ssb_files.file import SsbLoadedFile


class AbstractScriptFileContext(ABC):
    """TODO Doc"""
    def __init__(self):
        self._registered_ssbs: List[SsbLoadedFile] = []

        # Sends the general state of the ssb files for this context
        # (breakable, ram_state_up_to_date) -> None
        self._on_ssbs_state_change: Optional[Callable[[bool, bool], None]] = None
        # Notifies of a ssb being reloaded in RAM
        # (ssb_filename) -> None
        self._on_ssbs_reload: Optional[Callable[[str], None]] = None
        # Notifies of added opcodes to create markers for
        # (is_exps, ssb_filename, opcode_offset, line, column, is_temp, is_for_macro_call) -> None
        self._do_insert_opcode_text_mark: Optional[Callable[[bool, str, int, int, int, bool, bool], None]] = None

    def destroy(self):
        self._unregister_ssb_handlers()

    def register_ssbs_state_change_handler(self, on_ssbs_state_change: Callable[[bool, bool], None]):
        self._on_ssbs_state_change = on_ssbs_state_change

    def register_ssbs_reload_handler(self, on_ssbs_reload: Callable[[str], None]):
        self._on_ssbs_reload = on_ssbs_reload

    def register_insert_opcode_text_mark_handler(self,
                                                 handler: Optional[Callable[[bool, str, int, int, int, bool], None]]):
        self._do_insert_opcode_text_mark = handler

    @property
    @abstractmethod
    def ssb_filepath(self) -> Optional[str]:
        pass

    @property
    @abstractmethod
    def exps_filepath(self) -> str:
        pass

    @property
    @abstractmethod
    def breakpoint_manager(self) -> BreakpointManager:
        pass
        
    @abstractmethod
    def on_ssb_reload(self, loaded_ssb: SsbLoadedFile):
        pass
        
    @abstractmethod
    def on_ssb_property_change(self, loaded_ssb: SsbLoadedFile, name, value):
        pass

    @abstractmethod
    def request_ssbs_state(self):
        pass

    @abstractmethod
    def load(
        self,
        load_exps: bool, load_ssbs: bool,
        load_view_callback: Callable[[str, bool, str], None],
        after_callback: Callable[[], None],
        exps_exception_callback: Callable[[any, BaseException], None],
        exps_hash_changed_callback: Callable[[Callable, Callable], None],
        ssbs_not_available_callback: Callable[[], None]
    ):
        pass

    @abstractmethod
    def save(self, save_text: str, save_exps: bool,
             error_callback: Callable[[any, BaseException], None],
             success_callback: Callable[[], None]):
        pass

    @abstractmethod
    def on_ssb_changed_externally(self, ssb_filename, ready_to_reload):
        """
        A ssb file was re-compiled from outside of it's script editor.
        """

    @abstractmethod
    def on_exps_macro_ssb_changed(self, exps_abs_path, ssb_filename):
        """
        The ssb file ssb_filename was changed and it imports the ExplorerScript macro file with the absolute path
        of exps_abs_path.
        """

    @abstractmethod
    def goto_scene(self, debugger_context: AbstractDebuggerControlContext):
        pass

    def _register_ssb_handler(self, loaded_ssb: SsbLoadedFile):
        self._registered_ssbs.append(loaded_ssb)
        loaded_ssb.register_reload_event_editor(self.on_ssb_reload)
        loaded_ssb.register_property_callback(self.on_ssb_property_change)

    def _unregister_ssb_handlers(self):
        for loaded_ssb in self._registered_ssbs:
            loaded_ssb.unregister_reload_event_editor(self.on_ssb_reload)
            loaded_ssb.unregister_property_callback(self.on_ssb_property_change)

    @abstractmethod
    def get_scene_name_and_type(self) -> Tuple[Optional[str], Optional[str]]:
        pass
