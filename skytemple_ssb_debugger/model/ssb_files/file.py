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
import logging
from typing import TYPE_CHECKING, List, Optional

from explorerscript.source_map import SourceMapPositionMark
from skytemple_files.common.project_file_manager import ProjectFileManager
from skytemple_files.script.ssb.model import Ssb
from skytemple_ssb_debugger.model.ssb_files.explorerscript import ExplorerScriptFile
from skytemple_ssb_debugger.model.ssb_files.ssb_script import SsbScriptFile

if TYPE_CHECKING:
    from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager

logger = logging.getLogger(__name__)


class SsbLoadedFile:
    def __init__(self, filename: str, model: Ssb,
                 ssb_file_manager: Optional['SsbFileManager'], project_file_manager: 'ProjectFileManager'):
        self.filename = filename
        self.ssb_model = model
        # TODO: we really have to fix this weird coupling. SsbLoadedFile should not need a file manager reference
        #       and the saving of SsbScript and ExplorerScript should not be within the SSBS/EXPS sub models.
        self.file_manager: Optional['SsbFileManager'] = ssb_file_manager
        self.project_file_manager: 'ProjectFileManager' = project_file_manager
        self.ssbs: SsbScriptFile = SsbScriptFile(self)
        self.exps: ExplorerScriptFile = ExplorerScriptFile(self)

        # The SSB file is currently open in an editor.
        self._opened_in_editor = False
        # The SSB file is currently loaded in RAM by the Ground Engine.
        self._opened_in_ground_engine = False
        # The state in RAM differs from the currently saved SSB to ROM.
        self._ram_state_up_to_date = True
        # The file is not debuggable at the moment, because an old state is
        # loaded in RAM and old breakpoint mappings
        # are not available (because the source view for it was closed).
        self._not_breakable = False

        self._event_handlers_manager = []
        self._event_handlers_editor = []

        self._event_handlers_property_change = []

    @property
    def position_markers(self) -> Optional[List[SourceMapPositionMark]]:
        """
        Returns the position markers. Either from the ExplorerScript file or the SSB model,
        if ExplorerScript is not available.
        """
        exps_sm = self.exps.source_map
        if not exps_sm.is_empty:
            return exps_sm.get_position_marks__direct()
        if not self.ssbs.source_map:
            self.ssbs.load()
        # TODO: From Macros
        return self.ssbs.source_map.get_position_marks__direct()


    @property
    def opened_in_editor(self):
        return self._opened_in_editor

    @opened_in_editor.setter
    def opened_in_editor(self, value):
        self._opened_in_editor = value
        self._trigger_property_change('opened_in_editor', value)

    @property
    def opened_in_ground_engine(self):
        return self._opened_in_ground_engine

    @opened_in_ground_engine.setter
    def opened_in_ground_engine(self, value):
        self._opened_in_ground_engine = value
        self._trigger_property_change('opened_in_ground_engine', value)

    @property
    def ram_state_up_to_date(self):
        return self._ram_state_up_to_date

    @ram_state_up_to_date.setter
    def ram_state_up_to_date(self, value):
        self._ram_state_up_to_date = value
        self._trigger_property_change('ram_state_up_to_date', value)

    @property
    def not_breakable(self):
        return self._not_breakable

    @not_breakable.setter
    def not_breakable(self, value):
        self._not_breakable = value
        self._trigger_property_change('not_breakable', value)

    def register_reload_event_manager(self, on_ssb_reload):
        self._event_handlers_manager.append(on_ssb_reload)

    def unregister_reload_event_manager(self, on_ssb_reload):
        try:
            self._event_handlers_manager.remove(on_ssb_reload)
        except ValueError:
            pass

    def register_reload_event_editor(self, on_ssb_reload):
        self._event_handlers_editor.append(on_ssb_reload)

    def unregister_reload_event_editor(self, on_ssb_reload):
        try:
            self._event_handlers_editor.remove(on_ssb_reload)
        except ValueError:
            pass

    def signal_editor_reload(self):
        logger.debug(f"{self.filename}: Reload triggered.")
        # Breakpoint manager update it's breakpoint
        for handler in self._event_handlers_manager:
            handler(self)
        # Editors updates it's marks and uses the updated breakpoints.
        for handler in self._event_handlers_editor:
            handler(self)

    def register_property_callback(self, cb):
        self._event_handlers_property_change.append(cb)

    def unregister_property_callback(self, cb):
        self._event_handlers_property_change.remove(cb)

    def _trigger_property_change(self, name, value):
        for cb in self._event_handlers_property_change:
            cb(self, name, value)
