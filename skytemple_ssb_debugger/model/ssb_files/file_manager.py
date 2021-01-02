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
import hashlib
import logging
import os
from functools import partial
from typing import TYPE_CHECKING, List, Tuple, Set

from explorerscript.included_usage_map import IncludedUsageMap
from skytemple_files.common.types.file_types import FileType
from skytemple_files.common.util import open_utf8
from skytemple_files.script.ssb.script_compiler import ScriptCompiler
from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_ssb_debugger.model.ssb_files.file import SsbLoadedFile
from skytemple_ssb_debugger.threadsafe import threadsafe_now_or_gtk_nonblocking

if TYPE_CHECKING:
    from skytemple_ssb_debugger.controller.debugger import DebuggerController

logger = logging.getLogger(__name__)


class SsbFileManager:
    def __init__(self, context: AbstractDebuggerControlContext, debugger: 'DebuggerController'):
        self.debugger = debugger
        self.context: AbstractDebuggerControlContext = context

    @property
    def project_fm(self):
        return self.context.get_project_filemanager()

    def get(self, filename: str) -> SsbLoadedFile:
        """Get a file. If loaded by editor or ground engine, use the open_* methods instead!"""
        return self.context.get_ssb(filename, self)

    def save_from_ssb_script(self, filename: str, code: str) -> bool:
        """
        Save an SSB model from SSBScript. It's existing model and source map will be updated.
        If the file was not loaded in the ground engine, and is thus ready
        to reload for the editors, True is returned. You may call self.force_reload()
        when you are ready (to trigger ssb reload event).
        Otherwise False is returned and the event will be triggered later automatically.

        :raises: ParseError: On parsing errors
        :raises: SsbCompilerError: On logical compiling errors (eg. unknown opcodes / constants)
        """
        logger.debug(f"{filename}: Saving from SSBScript")
        self.get(filename)
        compiler = ScriptCompiler(self.context.get_static_data())
        f = self.get(filename)
        f.ssb_model, f.ssbs.source_map = compiler.compile_ssbscript(code)
        logger.debug(f"{filename}: Saving to ROM")
        self.context.save_ssb(filename, f.ssb_model, self)
        # After save:
        return self._handle_after_save(filename)

    def save_from_explorerscript(self, ssb_filename: str, code: str) -> Tuple[bool, Set[str]]:
        """
        Save an SSB model from ExplorerScript. It's existing model and source map will be updated.

        Returns a tuple of ready_to_reload (see next) and the set of included absolute exps file names.

        If the file was not loaded in the ground engine, and is thus ready
        to reload for the editors, True is returned. You may call self.force_reload()
        when you are ready (to trigger ssb reload event).
        Otherwise False is returned and the event will be triggered later automatically.

        ssb_filename is the SSB file name! The exps file is auto-detected using this.

        :raises: ParseError: On parsing errors
        :raises: SsbCompilerError: On logical compiling errors (eg. unknown opcodes / constants)
        """
        logger.debug(f"{ssb_filename}: Saving from ExplorerScript")
        project_fm = self.context.get_project_filemanager()

        # Just in case of a crash/hang: Prematurely write ExplorerScript to file
        logger.debug(f"{ssb_filename}: Pre-Save")
        project_fm.explorerscript_save(ssb_filename, code, None)

        project_dir = self.context.get_project_dir()
        static_data = self.context.get_static_data()
        logger.debug(f"{ssb_filename}: Init Compiler")
        compiler = ScriptCompiler(static_data)
        logger.debug(f"{ssb_filename}: Get SSB")
        f = self.get(ssb_filename)
        exps_filename = f.exps.full_path
        original_source_map = f.exps.source_map
        logger.debug(f"{ssb_filename}: Compile")
        f.ssb_model, f.exps.source_map = compiler.compile_explorerscript(
            code, exps_filename, lookup_paths=[self.context.get_project_macro_dir()]
        )

        logger.debug(f"{ssb_filename}: Serialize")
        ssb_new_bin = FileType.SSB.serialize(f.ssb_model, static_data)

        # Write ExplorerScript to file
        logger.debug(f"{ssb_filename}: Save")
        project_fm.explorerscript_save(ssb_filename, code, f.exps.source_map)

        # Update the hash of the ExplorerScript file
        logger.debug(f"{ssb_filename}: Hash")
        new_hash = self.hash(ssb_new_bin)
        f.exps.ssb_hash = new_hash
        logger.debug(f"{ssb_filename}: Save Hash")
        project_fm.explorerscript_save_hash(ssb_filename, new_hash)

        # Update the inclusion maps of included files.
        logger.debug(f"{ssb_filename}: Build IM")
        new_inclusion_list = IncludedUsageMap(f.exps.source_map, exps_filename)
        diff = IncludedUsageMap(original_source_map, exps_filename) - new_inclusion_list
        pd_w_pathsetp = project_dir + os.path.sep
        logger.debug(f"{ssb_filename}: Diff IMs")
        for removed_path in diff.removed:
            project_fm.explorerscript_include_usage_remove(removed_path.replace(pd_w_pathsetp, ''), ssb_filename)
        for added_path in diff.added:
            project_fm.explorerscript_include_usage_add(added_path.replace(pd_w_pathsetp, ''), ssb_filename)

        # Save ROM
        logger.debug(f"{ssb_filename}: Save ROM")
        self.context.save_ssb(ssb_filename, f.ssb_model, self)
        # After save:
        logger.debug(f"{ssb_filename}: After Save")
        result = self._handle_after_save(ssb_filename), new_inclusion_list.included_files
        logger.debug(f"{ssb_filename}: Done")
        return result

    def save_explorerscript_macro(self, abs_exps_path: str, code: str,
                                  changed_ssbs: List[SsbLoadedFile]) -> Tuple[List[bool], List[Set[str]]]:
        """
        Saves an ExplorerScript macro file. This will save the source file for the macro and also recompile all SSB
        models in the list of changed_ssbs.
        Returned is a list of "ready_to_reload" from save_from_explorerscript and a list of sets for ALL included files
        of those ssb files.
        """
        logger.debug(f"{abs_exps_path}: Saving ExplorerScript macro")
        # Write ExplorerScript to file
        with open_utf8(abs_exps_path, 'w') as f:
            f.write(code)

        ready_to_reloads = []
        included_files_list = []
        project_fm = self.context.get_project_filemanager()
        for ssb in changed_ssbs:
            # Skip non-existing or not up to date exps:
            if not project_fm.explorerscript_exists(ssb.filename) or \
                    not project_fm.explorerscript_hash_up_to_date(ssb.filename, ssb.exps.ssb_hash):
                ready_to_reloads.append(False)
                included_files_list.append(set())
            else:
                exps_source, _ = project_fm.explorerscript_load(ssb.filename, sourcemap=False)
                ready_to_reload, included_files = self.save_from_explorerscript(ssb.filename, exps_source)
                ready_to_reloads.append(ready_to_reload)
                included_files_list.append(included_files)

        return ready_to_reloads, included_files_list

    def force_reload(self, filename: str):
        """
        Force a SSB reload event to be triggered. You MUST only call this after one of the save
        methods have returned True.
        """
        logger.debug(f"{filename}: Force reload")
        self.get(filename).signal_editor_reload()

    def open_in_editor(self, filename: str):
        self.get(filename)
        logger.debug(f"{filename}: Opened in editor")
        self.get(filename).opened_in_editor = True
        return self.get(filename)

    def open_in_ground_engine(self, filename: str):
        self.get(filename)
        logger.debug(f"{filename}: Opened in Ground Engine")
        self.get(filename).opened_in_ground_engine = True
        # The file was reloaded in RAM:
        if not self.get(filename).ram_state_up_to_date:
            self.get(filename).ram_state_up_to_date = True
            self.get(filename).not_breakable = False
            self.get(filename).signal_editor_reload()

        return self.get(filename)

    def close_in_editor(self, filename: str, warning_callback):
        """
        # - If the file was closed and the old text marks are no longer available, disable
        #   debugging for that file until reload [show warning before close]
        """
        if not self.get(filename).ram_state_up_to_date:
            if not warning_callback():
                return False
            self.get(filename).not_breakable = True
        logger.debug(f"{filename}: Closed in editor")
        self.get(filename).opened_in_editor = False
        return True

    def close_in_ground_engine(self, filename: str):
        """
        # - If the file is no longer loaded in Ground Engine: Regenerate text marks from source map.
        Is threadsafe.
        """
        self.get(filename).opened_in_ground_engine = False
        self.get(filename).not_breakable = False
        if not self.get(filename).ram_state_up_to_date:
            threadsafe_now_or_gtk_nonblocking(lambda: self.get(filename).signal_editor_reload())
        self.get(filename).ram_state_up_to_date = True
        logger.debug(f"{filename}: Closed in Ground Engine")
        pass

    def _handle_after_save(self, filename: str):
        """
        # - If the file is no longer loaded in Ground Engine: Regenerate text marks from source map.
        Returns whether a reload is possible.
        """
        def set_ram_state(state):
            self.get(filename).ram_state_up_to_date = state

        if not self.get(filename).opened_in_ground_engine:
            threadsafe_now_or_gtk_nonblocking(partial(set_ram_state, True))
            logger.debug(f"{filename}: Can be reloaded")
            return True
        else:
            threadsafe_now_or_gtk_nonblocking(partial(set_ram_state, False))

        logger.debug(f"{filename}: Can NOT be reloaded")
        return False

    def hash_for(self, filename: str):
        return self.hash(self.get(filename).ssb_model.original_binary_data)

    @staticmethod
    def hash(binary_data: bin):
        return hashlib.sha256(binary_data).hexdigest()

    def mark_invalid(self, filename: str):
        """Mark a file as not breakable, because source mappings are not available."""
        self.get(filename).ram_state_up_to_date = False
        self.get(filename).not_breakable = True
