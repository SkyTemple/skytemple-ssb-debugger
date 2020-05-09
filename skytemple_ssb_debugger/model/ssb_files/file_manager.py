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
import hashlib
import os
from typing import Dict, TYPE_CHECKING

from ndspy.rom import NintendoDSRom

from explorerscript.included_usage_map import IncludedUsageMap
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_files.common.project_file_manager import ProjectFileManager
from skytemple_files.common.types.file_types import FileType
from skytemple_files.script.ssb.script_compiler import ScriptCompiler
from skytemple_ssb_debugger.model.ssb_files.file import SsbLoadedFile
from skytemple_ssb_debugger.threadsafe import threadsafe_now_or_gtk_nonblocking

if TYPE_CHECKING:
    from skytemple_ssb_debugger.controller.debugger import DebuggerController


MACROS_DIR_NAME = 'macros'


class SsbFileManager:
    def __init__(self, rom: NintendoDSRom, rom_data: Pmd2Data, rom_filename: str,
                 debugger: 'DebuggerController', project_fm: ProjectFileManager):
        self.rom = rom
        self.rom_data = rom_data
        self.rom_filename = rom_filename
        self.debugger = debugger
        self.project_fm = project_fm
        # TODO: Mechanism to close files again!
        self._open_files: Dict[str, SsbLoadedFile] = {}

    def get(self, filename: str) -> SsbLoadedFile:
        """Get a file. If loaded by editor or ground engine, use the open_* methods instead!"""
        if filename not in self._open_files:
            ssb_bin = self.rom.getFileByName(filename)
            self._open_files[filename] = SsbLoadedFile(
                filename, FileType.SSB.deserialize(ssb_bin), self, self.project_fm
            )
            self._open_files[filename].exps.ssb_hash = self._hash(ssb_bin)
        return self._open_files[filename]

    def save_from_ssb_script(self, filename: str, code: str):
        """
        Save an SSB model from SSBScript. It's existing model and source map will be updated.
        If the file was not loaded in the ground engine, and is thus ready
        to reload for the editors, True is returned. You may call self.force_reload()
        when you are ready (to trigger ssb reload event).
        Otherwise False is returned and the event will be triggered later automatically.

        :raises: ParseError: On parsing errors
        :raises: SsbCompilerError: On logical compiling errors (eg. unknown opcodes / constants)
        """
        # TODO: Put save functions in new classes
        self.get(filename)
        compiler = ScriptCompiler(self.rom_data)
        f = self._open_files[filename]
        f.ssb_model, f.ssbs.source_map = compiler.compile_ssbscript(code)
        self.rom.setFileByName(
            filename, FileType.SSB.serialize(f.ssb_model)
        )
        self.rom.saveToFile(self.rom_filename)
        # After save:
        return self._handle_after_save(filename)

    def save_from_explorerscript(self, ssb_filename: str, code: str):
        """
        Save an SSB model from ExplorerScript. It's existing model and source map will be updated.
        If the file was not loaded in the ground engine, and is thus ready
        to reload for the editors, True is returned. You may call self.force_reload()
        when you are ready (to trigger ssb reload event).
        Otherwise False is returned and the event will be triggered later automatically.

        ssb_filename is the SSB file name! The exps file is auto-detected using this.

        :raises: ParseError: On parsing errors
        :raises: SsbCompilerError: On logical compiling errors (eg. unknown opcodes / constants)
        """
        # TODO: Put save functions in new classes
        project_dir = self.project_fm.dir()
        exps_filename = os.path.join(
            project_dir, self.project_fm.explorerscript_get_path_for_ssb(ssb_filename)
        )
        self.get(ssb_filename)
        compiler = ScriptCompiler(self.rom_data)
        f = self._open_files[ssb_filename]
        original_source_map = f.exps.source_map
        f.ssb_model, f.exps.source_map = compiler.compile_explorerscript(
            code, exps_filename, lookup_paths=[self.project_fm.dir(MACROS_DIR_NAME)]
        )
        ssb_new_bin = FileType.SSB.serialize(f.ssb_model)

        # Write ExplorerScript to file
        self.project_fm.explorerscript_save(ssb_filename, code, f.exps.source_map)

        # Update the hash of the ExplorerScript file
        new_hash = self._hash(ssb_new_bin)
        f.exps.ssb_hash = new_hash
        self.project_fm.explorerscript_save_hash(ssb_filename, new_hash)

        # Update the inclusion maps of included files.
        diff = IncludedUsageMap(original_source_map, exps_filename) - IncludedUsageMap(f.exps.source_map, exps_filename)
        for removed_path in diff.removed:
            self.project_fm.explorerscript_include_usage_remove(removed_path.replace(project_dir, ''), ssb_filename)
        for added_path in diff.added:
            self.project_fm.explorerscript_include_usage_add(added_path.replace(project_dir, ''), ssb_filename)

        # TODO: (in new method):
            # TODO: Save all included files.
            # TODO: Only save to ROM if actually a ssb file.

        # Save ROM
        self.rom.setFileByName(
            ssb_filename, ssb_new_bin
        )
        self.rom.saveToFile(self.rom_filename)
        # After save:
        return self._handle_after_save(ssb_filename)

    def force_reload(self, filename: str):
        """
        Force a SSB reload event to be triggered. You MUST only call this after one of the save
        methods have returned True.
        """
        print(f"{filename}: Force reload")
        self._open_files[filename].signal_editor_reload()

    def open_in_editor(self, filename: str):
        self.get(filename)
        print(f"{filename}: Opened in editor")
        self._open_files[filename].opened_in_editor = True
        return self._open_files[filename]

    def open_in_ground_engine(self, filename: str):
        self.get(filename)
        print(f"{filename}: Opened in Ground Engine")
        self._open_files[filename].opened_in_ground_engine = True
        # The file was reloaded in RAM:
        if not self._open_files[filename].ram_state_up_to_date:
            self._open_files[filename].ram_state_up_to_date = True
            self._open_files[filename].not_breakable = False
            self._open_files[filename].signal_editor_reload()

        return self._open_files[filename]

    def close_in_editor(self, filename: str, warning_callback):
        """
        # - If the file was closed and the old text marks are no longer available, disable
        #   debugging for that file until reload [show warning before close]
        """
        if not self._open_files[filename].ram_state_up_to_date:
            if not warning_callback():
                return False
            self._open_files[filename].not_breakable = True
        print(f"{filename}: Closed in editor")
        self._open_files[filename].opened_in_editor = False
        return True

    def close_in_ground_engine(self, filename: str):
        """
        # - If the file is no longer loaded in Ground Engine: Regenerate text marks from source map.
        Is threadsafe.
        """
        self.get(filename)
        self._open_files[filename].opened_in_ground_engine = False
        self._open_files[filename].not_breakable = False
        if not self._open_files[filename].ram_state_up_to_date:
            threadsafe_now_or_gtk_nonblocking(lambda: self._open_files[filename].signal_editor_reload())
        self._open_files[filename].ram_state_up_to_date = True
        print(f"{filename}: Closed in Ground Engine")
        pass

    def _handle_after_save(self, filename: str):
        """
        # - If the file is no longer loaded in Ground Engine: Regenerate text marks from source map.
        Returns whether a reload is possible.
        """
        self._open_files[filename].ram_state_up_to_date = False
        if not self._open_files[filename].opened_in_ground_engine:
            self._open_files[filename].ram_state_up_to_date = True
            print(f"{filename}: Can be reloaded")
            return True
        print(f"{filename}: Can NOT be reloaded")
        return False

    def hash_for(self, filename: str):
        self.get(filename)
        return self._hash(self._open_files[filename].ssb_model.original_binary_data)

    @staticmethod
    def _hash(binary_data: bin):
        return hashlib.sha256(binary_data).hexdigest()

    def mark_invalid(self, filename: str):
        """Mark a file as not breakable, because source mappings are not available."""
        self.get(filename)
        self._open_files[filename].ram_state_up_to_date = False
        self._open_files[filename].not_breakable = True
