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
import os
from typing import Optional, Union, Dict

from explorerscript.source_map import MacroSourceMapping
from skytemple_files.common.project_file_manager import ProjectFileManager
from skytemple_ssb_debugger.model.ssb_files.file import SsbLoadedFile


class BreakpointFileState:
    """
    Additional information about the debugger state, when halted (eg. if halted on maco and the source file that
    is stopped in).
    """

    # The debugger is halted on a macro call
    BREAK_AT_CALL = 0
    # The debugger is halted on a regular opcode
    BREAK_REGULAR = 1
    # A source file may contain both situations described above.
    BREAK_BOTH = 2
    # A source file contains no breakpoints
    BREAK_NONE = -1

    def __init__(self, ssb_filename: str, opcode_addr: int):
        self.ssb_filename = ssb_filename
        self.opcode_addr = opcode_addr
        self._halted_state = self.BREAK_REGULAR
        self._handler_filename = ssb_filename
        self._current_macro_variables: Optional[Dict[str, Union[str, int]]] = None

    @property
    def halted_on_call(self):
        return self._halted_state == self.BREAK_AT_CALL

    @halted_on_call.setter
    def halted_on_call(self, value):
        self._halted_state = self.BREAK_AT_CALL if value else self.BREAK_REGULAR

    @property
    def handler_filename(self):
        return self._handler_filename

    @property
    def current_macro_variables(self) -> Optional[Dict[str, Union[str, int]]]:
        return self._current_macro_variables

    def process(self, loaded_ssb: SsbLoadedFile, opcode_offset: int, use_explorerscript, project_fm: ProjectFileManager):
        """Set the handler_filename and halted_on_call properties depending
        on what opcode is currently being halted at in the source map."""
        try:
            source_map = loaded_ssb.exps.source_map if use_explorerscript else loaded_ssb.ssbs.source_map
            mapping = source_map.get_op_line_and_col(opcode_offset)
            if isinstance(mapping, MacroSourceMapping):
                if mapping.called_in is not None:
                    self.halted_on_call = True
                    if mapping.called_in[0] is not None:
                        self._handler_filename = self._make_epxs_absolute(
                            project_fm, loaded_ssb.filename, mapping.called_in[0]
                        )
                elif mapping.relpath_included_file is not None:
                    self._handler_filename = self._make_epxs_absolute(
                        project_fm, loaded_ssb.filename, mapping.relpath_included_file
                    )
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
