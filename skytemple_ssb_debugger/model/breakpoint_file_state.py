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
from typing import Optional, Union, Dict, TYPE_CHECKING

from explorerscript.source_map import MacroSourceMapping
from skytemple_files.common.project_file_manager import ProjectFileManager
from skytemple_ssb_debugger.model.ssb_files.file import SsbLoadedFile

if TYPE_CHECKING:
    from skytemple_ssb_debugger.model.breakpoint_state import BreakpointState


class BreakpointFileState:
    """
    Additional information about the debugger state, when halted (eg. if halted on maco and the source file that
    is stopped in).

    This also manages the "exception" in debugging for when at macro calls or inside macro functions, by providing
    a method to simulate calling macros for the user and providing return address for macros to jump to, when
    pressing the UI buttons for it.
    """

    def __init__(self, ssb_filename: str, opcode_addr: int, parent: Optional['BreakpointState']):
        self.ssb_filename = ssb_filename
        self.opcode_addr = opcode_addr
        self.parent = parent
        self._halted_on_call = False
        self._handler_filename = ssb_filename
        self._inside_call_handler_filename = ssb_filename
        self._current_macro_variables: Optional[Dict[str, Union[str, int]]] = None
        self._step_over_addr = None
        self._step_out_addr = None

    @property
    def halted_on_call(self):
        """When halted at a macro call, pressing step into should not instruct the debugger to STEP_INTO as usual.
        Instead step_into_macro_call of this object should be called, and after this the UI should be updated
        to relect the new _handler_filename. After calling that function halted_on_call will return False, the
        op that's being halted on this the one INSIDE the macro, and the debugging can resume as normal."""
        return self._halted_on_call

    @property
    def handler_filename(self):
        return self._handler_filename

    @property
    def current_macro_variables(self) -> Optional[Dict[str, Union[str, int]]]:
        return self._current_macro_variables

    @property
    def step_over_addr(self) -> Optional[int]:
        """If set, the debugger should be instructed to do a STEP_MANUAL to this address when stepping over,
        instead of the regular STEP_OVER instruction."""
        return self._step_over_addr

    @property
    def step_out_addr(self) -> Optional[int]:
        """If set, the debugger should be instructed to do a STEP_MANUAL to this address when stepping out,
        instead of the regular STEP_OUT instruction."""
        return self._step_out_addr

    def step_into_macro_call(self):
        """Step into a macro call, see notes at halted_on_call."""
        self._halted_on_call = False
        self._handler_filename = self._inside_call_handler_filename
        self._step_out_addr = self._step_over_addr
        self._step_over_addr = None

    def process(self, loaded_ssb: SsbLoadedFile, opcode_offset: int, use_explorerscript, project_fm: ProjectFileManager):
        """Set the handler_filename and halted_on_call properties depending
        on what opcode is currently being halted at in the source map."""
        try:
            source_map = loaded_ssb.exps.source_map if use_explorerscript else loaded_ssb.ssbs.source_map
            mapping = source_map.get_op_line_and_col(opcode_offset)
            if isinstance(mapping, MacroSourceMapping):
                if mapping.called_in is not None:
                    self._halted_on_call = True
                    self._step_over_addr = mapping.return_addr
                    if mapping.called_in[0] is not None:
                        self._handler_filename = self._make_epxs_absolute(
                            project_fm, loaded_ssb.filename, mapping.called_in[0]
                        )
                    if mapping.relpath_included_file is not None:
                        self._inside_call_handler_filename = self._make_epxs_absolute(
                            project_fm, loaded_ssb.filename, mapping.relpath_included_file
                        )
                elif mapping.relpath_included_file is not None:
                    self._handler_filename = self._make_epxs_absolute(
                        project_fm, loaded_ssb.filename, mapping.relpath_included_file
                    )
                    self._step_out_addr = mapping.return_addr
                else:
                    self._step_out_addr = mapping.return_addr
                if mapping.parameter_mapping:
                    self._current_macro_variables = mapping.parameter_mapping
        except:
            # We ignore errors here, it's not really important, it just may lead to unexpected experiences
            # during debugging.
            # Todo: logging
            pass

    def _make_epxs_absolute(self, project_fm, ssb_rom_filename, relpath_included_file):
        abs_path_ssb_exps = project_fm.dir() + os.path.sep + project_fm.explorerscript_get_path_for_ssb(ssb_rom_filename)
        return os.path.abspath(os.path.join(os.path.dirname(abs_path_ssb_exps), relpath_included_file))
