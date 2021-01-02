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
import sys
import threading
from functools import partial
from typing import Callable, Optional, TYPE_CHECKING, Tuple

from gi.repository import GLib

from explorerscript.source_map import SourceMap, MacroSourceMapping
from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_ssb_debugger.model.breakpoint_manager import BreakpointManager
from skytemple_ssb_debugger.model.script_file_context.abstract import AbstractScriptFileContext
from skytemple_ssb_debugger.model.ssb_files.explorerscript import SsbHashError
from skytemple_ssb_debugger.model.ssb_files.file import SsbLoadedFile

if TYPE_CHECKING:
    from skytemple_ssb_debugger.controller.editor_notebook import EditorNotebookController
logger = logging.getLogger(__name__)


class SsbFileScriptFileContext(AbstractScriptFileContext):
    """Context for a script file that directly represents a single compiled SSB script."""

    def __init__(self, ssb_loaded_file: SsbLoadedFile, scene_type: str, scene_name: str,
                 breakpoint_manager: BreakpointManager, editor_notebook_controller: 'EditorNotebookController'):
        super().__init__()
        self._ssb_file = ssb_loaded_file
        self.scene_type = scene_type
        self.scene_name = scene_name
        self._register_ssb_handler(ssb_loaded_file)
        self._breakpoint_manager = breakpoint_manager
        self._editor_notebook_controller = editor_notebook_controller

    def destroy(self):
        super().destroy()

    @property
    def ssb_filepath(self) -> Optional[str]:
        return self._ssb_file.filename

    @property
    def exps_filepath(self) -> str:
        return self._ssb_file.exps.full_path

    @property
    def breakpoint_manager(self) -> BreakpointManager:
        return self._breakpoint_manager

    def on_ssb_reload(self, loaded_ssb: SsbLoadedFile):
        logger.debug(f"{loaded_ssb.filename}: Reloaded")
        if self._on_ssbs_state_change:
            self._on_ssbs_reload(loaded_ssb.filename)

    def on_ssb_property_change(self, loaded_ssb: SsbLoadedFile, name, value):
        logger.debug(f"{loaded_ssb.filename}: Property change")
        if self._on_ssbs_state_change:
            self._on_ssbs_state_change(not loaded_ssb.not_breakable, loaded_ssb.ram_state_up_to_date)

    def request_ssbs_state(self):
        logger.debug(f"State requested.")
        self._on_ssbs_state_change(not self._ssb_file.not_breakable, self._ssb_file.ram_state_up_to_date)
        self._on_ssbs_reload(self._ssb_file.filename)

    def load(
        self,
        load_exps: bool, load_ssbs: bool,
        load_view_callback: Callable[[str, bool, str], None],
        after_callback: Callable[[], None],
        exps_exception_callback: Callable[[any, BaseException], None],
        exps_hash_changed_callback: Callable[[Callable, Callable], None],
        ssbs_not_available_callback: Callable[[], None]
    ):
        logger.debug(f"Loading SSB file.")
        def gtk__chose_force_decompile():
            # we lazily load in the GTK thread now:
            try:
                logger.debug(f"Loading ExplorerScript: Force decompile.")
                self._ssb_file.exps.force_decompile()
            except Exception as ex:
                logger.error(f"Error on load.", exc_info=ex)
                exps_exception_callback(sys.exc_info(), ex)
            else:
                load_view_callback(self._ssb_file.exps.text, True, 'exps')

        def gtk__chose_force_load():
            # we lazily load in the GTK thread now:
            try:
                logger.debug(f"Loading ExplorerScript: Force.")
                self._ssb_file.exps.load(force=True)
            except Exception as ex:
                logger.error(f"Error on load.", exc_info=ex)
                exps_exception_callback(sys.exc_info(), ex)
            else:
                load_view_callback(self._ssb_file.exps.text, True, 'exps')

        def load_thread():
            # SSBS Load
            if load_ssbs:
                logger.debug(f"Loading SSBScript.")
                self._ssb_file.ssbs.load()
                GLib.idle_add(partial(
                    load_view_callback, self._ssb_file.ssbs.text, False, 'ssbs'
                ))

            # ExplorerScript Load
            if load_exps:
                try:
                    logger.debug(f"Loading ExplorerScript.")
                    self._ssb_file.exps.load()
                except SsbHashError:
                    logger.warning(f"Hash error on load.")
                    GLib.idle_add(partial(exps_hash_changed_callback, gtk__chose_force_decompile, gtk__chose_force_load))
                except Exception as ex:
                    logger.error(f"Error on load.", exc_info=ex)
                    exc_info = sys.exc_info()
                    GLib.idle_add(partial(exps_exception_callback, exc_info, ex))
                else:
                    GLib.idle_add(partial(
                        load_view_callback, self._ssb_file.exps.text, True, 'exps'
                    ))
            GLib.idle_add(partial(self._after_load, after_callback))

        threading.Thread(target=load_thread).start()

    def _after_load(self, after_callback: Callable[[], None]):
        logger.debug(f"Loaded. Loading in opcode marks.")
        if self._do_insert_opcode_text_mark:
            for is_exps, source_map in ((False, self._ssb_file.ssbs.source_map), (True, self._ssb_file.exps.source_map)):
                source_map: SourceMap
                if source_map is not None:
                    for opcode_offset, source_mapping in source_map:
                        if not isinstance(source_mapping, MacroSourceMapping) or source_mapping.relpath_included_file is None:
                            self._do_insert_opcode_text_mark(
                                is_exps, self._ssb_file.filename, opcode_offset,
                                source_mapping.line, source_mapping.column, False, False
                            )
                        # Also insert opcode text marks for macro calls
                        if isinstance(source_mapping, MacroSourceMapping) and source_mapping.called_in:
                            cin_fn, cin_line, cin_col = source_mapping.called_in
                            if cin_fn is None:
                                self._do_insert_opcode_text_mark(
                                    is_exps, self._ssb_file.filename, opcode_offset,
                                    cin_line, cin_col, False, True
                                )
        logger.debug(f"Loaded. Triggering callback.")
        after_callback()

    def save(self, save_text: str, save_exps: bool,
             error_callback: Callable[[any, BaseException], None],
             success_callback: Callable[[], None]):

        logger.debug(f"Saving SSB. From exps? {save_exps}")

        def save_thread():
            try:
                included_exps_files = None
                if save_exps:
                    ready_to_reload, included_exps_files = self._ssb_file.file_manager.save_from_explorerscript(
                        self._ssb_file.filename, save_text
                    )
                else:
                    ready_to_reload = self._ssb_file.file_manager.save_from_ssb_script(
                        self._ssb_file.filename, save_text
                    )
            except Exception as err:
                logger.error(f"Error on save.", exc_info=err)
                exc_info = sys.exc_info()
                GLib.idle_add(partial(error_callback, exc_info, err))
                return
            else:
                GLib.idle_add(partial(self._after_save, ready_to_reload, included_exps_files, success_callback))

        threading.Thread(target=save_thread).start()

    def _after_save(self, ready_to_reload, included_exps_files, success_callback: Callable[[], None]):
        if included_exps_files is not None:
            for exps_abs_path in included_exps_files:
                logger.debug(f"After save: Inform inclusion of macro {exps_abs_path}.")
                self._editor_notebook_controller.on_exps_macro_ssb_changed(exps_abs_path, self._ssb_file.filename)

        logger.debug(f"After save: Build temporary text marks for opcodes...")
        # Build temporary text marks for the new source map. We will replace
        # the real ones with those in on_ssb_reloaded
        if self._do_insert_opcode_text_mark:
            for is_exps, source_map in ((False, self._ssb_file.ssbs.source_map), (True, self._ssb_file.exps.source_map)):
                source_map: SourceMap
                if source_map is not None:
                    for opcode_offset, source_mapping in source_map:
                        if not isinstance(source_mapping, MacroSourceMapping) or source_mapping.relpath_included_file is None:
                            self._do_insert_opcode_text_mark(
                                is_exps, self._ssb_file.filename, opcode_offset,
                                source_mapping.line, source_mapping.column, True, False
                            )
                        # Also insert opcode text marks for macro calls
                        if isinstance(source_mapping, MacroSourceMapping) and source_mapping.called_in:
                            cin_fn, cin_line, cin_col = source_mapping.called_in
                            if cin_fn is None:
                                self._do_insert_opcode_text_mark(
                                    is_exps, self._ssb_file.filename, opcode_offset,
                                    cin_line, cin_col, True, True
                                )

        logger.debug(f"After save: Triggering callback...")
        success_callback()
        if ready_to_reload:
            logger.debug(f"After save: NOW READY TO RELOAD!")
            self._ssb_file.file_manager.force_reload(self._ssb_file.filename)

    def on_ssb_changed_externally(self, ssb_filename, ready_to_reload):
        if ssb_filename == self._ssb_file.filename:
            logger.debug(f"{ssb_filename} was changed externally, simulating save.")
            self._after_save(ready_to_reload, [], lambda: None)

    def on_exps_macro_ssb_changed(self, exps_abs_path, ssb_filename):
        # We don't manage a macro, so we don't care.
        pass

    def goto_scene(self, debugger_context: AbstractDebuggerControlContext):
        debugger_context.open_scene_editor(self.scene_type, self.scene_name)

    def get_scene_name_and_type(self) -> Tuple[Optional[str], Optional[str]]:
        return self.scene_name, self.scene_type
