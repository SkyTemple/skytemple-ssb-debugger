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
import json
import logging
import os
from typing import List, Tuple, Dict, Optional

from explorerscript.ssb_converting.ssb_data_types import SsbRoutineType
from skytemple_files.common.util import open_utf8
from skytemple_ssb_debugger.model.ssb_files.file import SsbLoadedFile
from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager

logger = logging.getLogger()


class BreakpointManager:
    def __init__(self, breakpoint_filename: str, file_manager: SsbFileManager):
        self._breakpoint_filename = breakpoint_filename
        self.file_manager = file_manager
        # This temporary breakpoint is set by the debugger while stepping
        # (is_in_unionall, opcode offset, script target type, script target slot)
        self._temporary_breakpoints: List[Tuple[Optional[bool], Optional[int], SsbRoutineType, int]] = []

        self.new_breakpoint_mapping: Dict[str, List[int]] = {}

        if not os.path.exists(breakpoint_filename):
            self.breakpoint_mapping: Dict[str, List[int]] = {}
        else:
            try:
                with open_utf8(breakpoint_filename, 'r') as f:
                    self.breakpoint_mapping = json.load(f)
            except ValueError:
                self.breakpoint_mapping = {}

        self._callbacks_added = []
        self._callbacks_remvoed = []

    def register_callbacks(self, open, remove):
        self._callbacks_added.append(open)
        self._callbacks_remvoed.append(remove)

    def resync(self, fn, list_breakpoints: List[int]):
        """
        Re-sync the breakpoints for this file.
        This is triggered, after a ssb file was saved.
        If the file is still open in the ground engine, the new state is written to file and a temporary
        dict, but is not used yet. The Breakpoint register registers itself as a callback for that SSB file
        and waits until it is no longer loaded in the ground engine.
        If the file is not open in the ground engine, the changes are applied immediately.

        Callbacks for adding are NOT called as for add.
        """
        logger.debug(f"{fn}: Breakpoint resync")
        ssb = self.file_manager.get(fn)
        mapping_to_write_to_file = self.breakpoint_mapping
        if ssb.ram_state_up_to_date:
            # We can just update.
            self.breakpoint_mapping[fn] = list_breakpoints
        else:
            # We need to use a temporary mapping for now!
            self.new_breakpoint_mapping[fn] = list_breakpoints
            ssb.register_reload_event_manager(self.wait_for_ssb_update)
            mapping_to_write_to_file = self.breakpoint_mapping.copy()
            mapping_to_write_to_file[fn] = list_breakpoints

        with open_utf8(self._breakpoint_filename, 'w') as f:
            # TODO: A breakpoint update in another file will just override this again...
            #       we should probably keep track of two full sets of the state (current ROM / current RAM)
            json.dump(mapping_to_write_to_file, f)

    def wait_for_ssb_update(self, ssb: SsbLoadedFile):
        if ssb.filename in self.new_breakpoint_mapping:
            # We can switch now update.
            self.breakpoint_mapping[ssb.filename] = self.new_breakpoint_mapping[ssb.filename]
            del self.new_breakpoint_mapping[ssb.filename]

            with open_utf8(self._breakpoint_filename, 'w') as f:
                json.dump(self.breakpoint_mapping, f)

        ssb.unregister_reload_event_manager(self.wait_for_ssb_update)

    def add(self, fn, op_off):
        logger.debug(f"{fn}: Breakpoint add: {op_off}")
        op_off = int(op_off)
        if fn not in self.breakpoint_mapping:
            self.breakpoint_mapping[fn] = []
        if self._get(self.breakpoint_mapping[fn], op_off) is not None:
            return
        self.breakpoint_mapping[fn].append(op_off)
        for cb in self._callbacks_added:
            cb(fn, op_off)
        with open_utf8(self._breakpoint_filename, 'w') as f:
            json.dump(self.breakpoint_mapping, f)

    def remove(self, fn, op_off):
        logger.debug(f"{fn}: Breakpoint remove: {op_off}")
        op_off = int(op_off)
        if fn not in self.breakpoint_mapping:
            return
        idx = self._get(self.breakpoint_mapping[fn], op_off)
        if idx is None:
            return
        del self.breakpoint_mapping[fn][idx]
        for cb in self._callbacks_remvoed:
            cb(fn, op_off)
        with open_utf8(self._breakpoint_filename, 'w') as f:
            json.dump(self.breakpoint_mapping, f)

    def has(self, fn: str,
            op_off: int, is_in_unionall: bool,
            script_target_type: SsbRoutineType, script_target_slot: int):
        """
        Checks if the breakpoint is in the active mapping or is the temporary breakpoint.
        script_target_* are only relevant for checking the temporary breakpoint.
        """
        for tbp in self._temporary_breakpoints:
            if tbp == (None, None, script_target_type, script_target_slot):
                return True
            if tbp == (None, op_off, script_target_type, script_target_slot):
                return True
            if tbp == (is_in_unionall, None, script_target_type, script_target_slot):
                return True
            if tbp == (is_in_unionall, op_off, script_target_type, script_target_slot):
                return True
        if fn not in self.breakpoint_mapping:
            return False
        if self.file_manager.get(fn).not_breakable:
            return False
        return op_off in self.breakpoint_mapping[fn]

    def saved_in_rom_get_for(self, fn):
        """Return the breakpoints that are saved in RAM for fn. These might be the tempoary breakpoints we stored!"""
        if fn in self.new_breakpoint_mapping:
            for opoff in self.new_breakpoint_mapping[fn]:
                yield opoff
        if fn in self.breakpoint_mapping:
            for opoff in self.breakpoint_mapping[fn]:
                yield opoff
        return

    def loaded_in_rom_get_for(self, fn):
        """Return the active loaded breakpoints for fn."""
        if fn in self.breakpoint_mapping:
            for opoff in self.breakpoint_mapping[fn]:
                yield opoff
        return

    def reset_temporary(self):
        logger.debug(f"Reset temporary")
        self._temporary_breakpoints = []

    def add_temporary(
            self, script_target_type: SsbRoutineType, script_target_slot: int, is_in_unionall=None, opcode_addr=None
    ):
        """
        Set a temporary breakpoint.
        is_in_unionall is optional:
        - If None, will break at any opcode for the script target
        - If True, will only break in unionall
        - If False, will not break in unionall, but all other scripts.

        opcode_addr is also optional, if set will only break at this opcode addr. Please note, that is_in_unionall
        is still checked in that case.

        See has.
        """
        logger.debug(f"Set temporary: {script_target_type}, {script_target_slot}, is_in_unionall={is_in_unionall}, opcode_addr={opcode_addr}")
        self._temporary_breakpoints.append((is_in_unionall, opcode_addr, script_target_type, script_target_slot))

    def _get(self, t, op_off):
        for idx, i_op_off in enumerate(t):
            if op_off == i_op_off:
                return idx
        return None
