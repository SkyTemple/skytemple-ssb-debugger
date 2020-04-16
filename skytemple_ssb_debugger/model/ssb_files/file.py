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
from typing import TYPE_CHECKING, Dict, List, Optional

from explorerscript.source_map import SourceMapPositionMark
from skytemple_files.script.ssa_sse_sss.position_marker import SsaPositionMarker
from skytemple_files.script.ssb.model import Ssb
from skytemple_ssb_debugger.model.ssb_files.explorerscript import ExplorerScriptFile
from skytemple_ssb_debugger.model.ssb_files.ssb_script import SsbScriptFile

if TYPE_CHECKING:
    from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager


class SsbLoadedFile:
    def __init__(self, filename: str, model: Ssb, file_manager: 'SsbFileManager'):
        self.filename = filename
        self.ssb_model = model
        self.ssbs = SsbScriptFile(self)
        self.exps = ExplorerScriptFile(self)
        self.file_manager: 'SsbFileManager' = file_manager

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

        self.register_property_callback(ssb_print_handler)

    @property
    def position_markers(self) -> Optional[List[SourceMapPositionMark]]:
        """
        Returns the position markers. Either from the ExplorerScript file or the SSB model,
        if ExplorerScript is not available.
        """
        if self.exps.loaded:
            pass  # todo!
            # return
        if not self.ssbs.source_map:
            self.ssbs.load()
        return self.ssbs.source_map.position_marks


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
        print(f"{self.filename}: Reload triggered.")
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


def ssb_print_handler(ssb, name, value):
    print(f'{ssb.filename}.{name} = {value}')
