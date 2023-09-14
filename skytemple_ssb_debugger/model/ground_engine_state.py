#  Copyright 2020-2023 Capypara and the SkyTemple Contributors
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
from __future__ import annotations
import warnings
from itertools import chain
from typing import Optional, List, Tuple, Iterable, Callable, cast, no_type_check

from gi.repository import Gtk, GLib
from range_typed_integers import u32

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_emulator import emulator_register_exec_ground, emulator_register_ssb_load, \
    emulator_register_ssx_load, emulator_register_talk_load, emulator_register_unionall_load_addr_change, \
    emulator_unregister_ssb_load, emulator_unregister_ssx_load, emulator_unregister_talk_load, \
    emulator_unregister_unionall_load_addr_change, emulator_unionall_load_address_update, emulator_wait_one_cycle, \
    emulator_breakpoints_set_loaded_ssb_files, emulator_breakpoints_set_load_ssb_for

from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_ssb_emulator import BreakpointState

from skytemple_ssb_debugger.model.breakpoint_file_state import BreakpointFileState
from skytemple_ssb_debugger.model.ground_state import AbstractEntity
from skytemple_ssb_debugger.model.ground_state.actor import Actor
from skytemple_ssb_debugger.model.ground_state.event import Event
from skytemple_ssb_debugger.model.ground_state.global_script import GlobalScript
from skytemple_ssb_debugger.model.ground_state.map import Map
from skytemple_ssb_debugger.model.ground_state.object import Object
from skytemple_ssb_debugger.model.ground_state.performer import Performer
from skytemple_ssb_debugger.model.ground_state.ssb_file_in_ram import SsbFileInRam
from skytemple_ssb_debugger.model.ground_state.ssx_file_in_ram import SsxFileInRam
from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager

TALK_HANGER_OFFSET = 3
MAX_SSX = 3
MAX_SSB = MAX_SSX + TALK_HANGER_OFFSET
O11_BYTE_CHECK = bytes([0xf0, 0x4f, 0x2d, 0xe9, 0x34, 0xd0, 0x4d, 0xe2, 0x64, 0x2a, 0x9f, 0xe5])


class GroundEngineState:
    def __init__(
            self,
            rom_data: Pmd2Data,
            print_callback: Callable[[str], None],
            inform_ground_engine_start_cb: Callable[[], None],
            poll_emulator: Callable[[], None],
            ssb_file_manager: SsbFileManager,
            context: AbstractDebuggerControlContext
    ):
        super().__init__()
        self.rom_data = rom_data
        self.ssb_file_manager = ssb_file_manager
        self.context = context
        self.logging_enabled = False
        self._boost = False
        self._breaked = False

        self.pnt_map = rom_data.bin_sections.overlay11.data.GROUND_STATE_MAP.absolute_address
        base_pnt = rom_data.bin_sections.overlay11.data.GROUND_STATE_PTRS.absolute_address
        self.pnt_main_script_struct = base_pnt
        #self.pnt_unk = base_pnt + 4
        self.pnt_actors = base_pnt + 8
        self.pnt_objects = base_pnt + 12
        self.pnt_performers = base_pnt + 16
        self.pnt_events = base_pnt + 20
        self.pnt_unionall_load_addr = rom_data.bin_sections.overlay11.data.UNIONALL_RAM_ADDRESS.absolute_address

        self._load_ssb_for: Optional[int] = None

        self._running = False
        self._print_callback = print_callback
        self._poll_emulator = poll_emulator
        self._inform_ground_engine_start_cb = inform_ground_engine_start_cb

        self._global_script = GlobalScript(self.pnt_main_script_struct, u32(0), self.rom_data)
        self._map = Map(self.pnt_map, u32(0), self.rom_data)

        self._actors = []
        info = self.rom_data.script_data.ground_state_structs['Actors']
        for i in range(0, info.maxentries):
            self._actors.append(Actor(self.pnt_actors, u32(i * info.entrylength), self.rom_data))

        self._objects = []
        info = self.rom_data.script_data.ground_state_structs['Objects']
        for i in range(0, info.maxentries):
            self._objects.append(Object(self.pnt_objects, u32(i * info.entrylength), self.rom_data))

        self._performers = []
        info = self.rom_data.script_data.ground_state_structs['Performers']
        for i in range(0, info.maxentries):
            self._performers.append(Performer(self.pnt_performers, u32(i * info.entrylength), self.rom_data))

        self._events = []
        info = self.rom_data.script_data.ground_state_structs['Events']
        for i in range(0, info.maxentries):
            self._events.append(Event(self.pnt_events, u32(i * info.entrylength), self.rom_data))

        self._loaded_ssx_files: List[Optional[SsxFileInRam]] = []
        self._loaded_ssb_files: List[Optional[SsbFileInRam]] = []
        self.reset()

    @no_type_check
    def break_pulled(self, state: BreakpointState):
        """Set the breaked property of the SSB file in the state's hanger."""
        self._breaked = True
        self._loaded_ssb_files[state.hanger_id].breaked = True
        self._loaded_ssb_files[state.hanger_id].breaked__handler_file = cast(BreakpointFileState, state.file_state).handler_filename
        state.add_release_hook(self.break_released)

    @no_type_check
    def step_into_macro_call(self, state: BreakpointState):
        assert self._loaded_ssb_files[state.hanger_id] is not None
        self._loaded_ssb_files[state.hanger_id].breaked__handler_file = cast(BreakpointFileState, state.file_state).handler_filename

    def break_released(self, state: BreakpointState):
        """Reset the breaked property of loaded ssb files again."""
        self._breaked = False
        for x in self._loaded_ssb_files:
            if x is not None:
                x.breaked = False
                x.breaked__handler_file = None

    @property
    def running(self):
        return self._running

    @property
    def loaded_ssx_files(self):
        return self._loaded_ssx_files

    @property
    def loaded_ssb_files(self):
        return self._loaded_ssb_files

    @property
    def global_script(self) -> GlobalScript:
        return self._global_script

    @property
    def map(self) -> Map:
        return self._map

    @property
    def actors(self):
        for i in range(0, self.rom_data.script_data.ground_state_structs['Actors'].maxentries):
            yield self.get_actor(i)

    @property
    def objects(self):
        for i in range(0, self.rom_data.script_data.ground_state_structs['Objects'].maxentries):
            yield self.get_object(i)

    @property
    def performers(self):
        for i in range(0, self.rom_data.script_data.ground_state_structs['Performers'].maxentries):
            yield self.get_performer(i)

    @property
    def events(self):
        for i in range(0, self.rom_data.script_data.ground_state_structs['Events'].maxentries):
            yield self.get_event(i)

    def get_actor(self, index: int) -> Optional[Actor]:
        actor = self._actors[index]
        if actor.valid:
            return actor
        return None

    def get_object(self, index: int) -> Optional[Object]:
        obj = self._objects[index]
        if obj.valid:
            return obj
        return None

    def get_performer(self, index: int) -> Optional[Performer]:
        prf = self._performers[index]
        if prf.valid:
            return prf
        return None

    def get_event(self, index: int) -> Optional[Event]:
        evt = self._events[index]
        if evt.valid:
            return evt
        return None

    def force_reload_ground_objects(self):
        all_entities: Iterable[AbstractEntity] = chain(
            self._actors, self._objects, self._performers, self._events, (self._global_script, self._map)
        )

        for obj in all_entities:
            obj.refresh()

        if not self._breaked:
            emulator_wait_one_cycle()
            emulator_wait_one_cycle()
        self._poll_emulator()


    def collect(self) -> Tuple[GlobalScript, List[SsbFileInRam], List[SsxFileInRam], List[Actor], List[Object], List[Performer], List[Event], Map]:
        loaded_ssb_files = self.loaded_ssb_files
        loaded_ssx_files = self.loaded_ssx_files

        self.force_reload_ground_objects()

        actors = [x for x in self.actors if x is not None]
        objects = [x for x in self.objects if x is not None]
        performers = [x for x in self.performers if x is not None]
        events = [x for x in self.events if x is not None]

        return self.global_script, loaded_ssb_files, loaded_ssx_files, actors, objects, performers, events, self.map

    def watch(self):
        ov11 = self.rom_data.bin_sections.overlay11

        emulator_register_exec_ground(ov11.functions.GroundMainLoop.absolute_address + 0x3C, self.hook__ground_start)
        emulator_register_exec_ground(ov11.functions.GroundMainLoop.absolute_address + 0x210, self.hook__ground_quit)
        emulator_register_exec_ground(ov11.functions.GroundMainLoop.absolute_address + 0x598, self.hook__ground_map_change)
        emulator_register_ssb_load([
            ov11.functions.SsbLoad1.absolute_address, ov11.functions.SsbLoad2.absolute_address
        ], self.hook__ssb_load)
        emulator_register_ssx_load([ov11.functions.StationLoadHanger.absolute_address + 0xC0], self.hook__ssx_load)
        emulator_register_talk_load(ov11.functions.ScriptStationLoadTalk.absolute_addresses, self.hook__talk_load)
        emulator_register_unionall_load_addr_change(self.pnt_unionall_load_addr)

    def remove_watches(self):
        ov11 = self.rom_data.bin_sections.overlay11

        emulator_register_exec_ground(ov11.functions.GroundMainLoop.absolute_address + 0x3C, None)
        emulator_register_exec_ground(ov11.functions.GroundMainLoop.absolute_address + 0x210, None)
        emulator_register_exec_ground(ov11.functions.GroundMainLoop.absolute_address + 0x598, None)
        emulator_unregister_ssb_load()
        emulator_unregister_ssx_load()
        emulator_unregister_talk_load()
        emulator_unregister_unionall_load_addr_change()

    def reset(self, keep_global=False, fully=False):
        if fully:
            self._running = False
        self._loaded_ssx_files = [None for _ in range(0, MAX_SSX + 1)]
        if keep_global:
            glob = self._loaded_ssb_files[0]
        for i, ssb in enumerate(self._loaded_ssb_files):
            if (i != 0 or not keep_global) and ssb is not None:
                self.ssb_file_manager.close_in_ground_engine(ssb.file_name)
        self._loaded_ssb_files = [None for _ in range(0, MAX_SSB + 1)]
        glob_fn = None
        if keep_global:
            self._loaded_ssb_files[0] = glob
            glob_fn = glob.file_name if glob is not None else None

        emulator_breakpoints_set_loaded_ssb_files(glob_fn, None, None, None, None, None, None)

    def serialize(self):
        """Convert the state (that's not directly tied to the game's memory) to a dict for saving."""
        return {
            'running': self.running,
            'ssbs': [
                [x.file_name, self.ssb_file_manager.hash_for(x.file_name)]
                if x is not None else None
                for x in self._loaded_ssb_files
            ],
            'ssxs': [x.file_name if x is not None else None for x in self._loaded_ssx_files],
            'load_ssb_for': self._load_ssb_for
        }

    def deserialize(self, state: dict):
        """Load a saved state back from a dict"""
        self._running = state['running']
        self._load_ssb_for = state['load_ssb_for']
        self._loaded_ssb_files = [
            SsbFileInRam(fn_and_hash[0], hng, fn_and_hash[1])
            if fn_and_hash is not None else None
            for hng, fn_and_hash in enumerate(state['ssbs'])
        ]
        emulator_breakpoints_set_load_ssb_for(int(self._load_ssb_for) if self._load_ssb_for is not None else None)
        emulator_breakpoints_set_loaded_ssb_files(
            *((x.file_name if x is not None else None) for x in self._loaded_ssb_files)
        )
        # - Load SSB file hashes from ground state file, if the hashes don't match on reload with the saved
        #   files, mark them as not up to date in RAM and show warning for affected files.
        were_invalid = []
        for f in self._loaded_ssb_files:
            if f is not None and f.hash != self.ssb_file_manager.hash_for(f.file_name):
                were_invalid.append(f.file_name)
        if len(were_invalid) > 0:
            n = '\n'
            md = self.context.message_dialog(
                None,
                Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.WARNING,
                Gtk.ButtonsType.OK,
                f"Some SSB script files that are loaded in RAM were changed. You can not debug "
                f"these files, until they are reloaded:\n{n.join(were_invalid)}",
                title="Warning!"
            )
            md.set_position(Gtk.WindowPosition.CENTER)
            # Some timing issues here.
            def run_and_destroy():
                md.run()
                md.destroy()
            GLib.idle_add(lambda: run_and_destroy())
        for ssb in self._loaded_ssb_files:
            if ssb is not None:
                self.ssb_file_manager.open_in_ground_engine(ssb.file_name)
                if ssb.file_name in were_invalid:
                    self.ssb_file_manager.mark_invalid(ssb.file_name)
        self._loaded_ssx_files = [SsxFileInRam(fn, hng) if fn is not None else None for hng, fn in enumerate(state['ssxs'])]

        # Also update the load address for unionall
        emulator_unionall_load_address_update()

    def _print(self, string):
        if self.logging_enabled and not self._boost:
            self._print_callback(f"Ground Event >> {string}")

    def hook__ground_start(self):
        self._print("Ground Start")
        self.reset()
        self._running = True
        self._inform_ground_engine_start_cb()

    def hook__ground_quit(self):
        self._print("Ground Quit")
        self._running = False

    def hook__ground_map_change(self):
        self._print("Ground Map Change")
        self.reset(keep_global=True)

    def hook__ssb_load(self, name: str):
        load_for = self._load_ssb_for if self._load_ssb_for is not None else 0
        self._print(f"SSB Load {name} for hanger {load_for}")
        self._load_ssb_for = None

        if load_for > MAX_SSB:
            warnings.warn(f"Ground Engine debugger: Invalid hanger ID for ssb: {load_for}")
            return
        self.ssb_file_manager.open_in_ground_engine(name)
        self._loaded_ssb_files[load_for] = (SsbFileInRam(name, load_for))

    def hook__ssx_load(self, hanger: int, name: str):
        self._print(f"SSX Load {name} for hanger {hanger}")
        self._load_ssb_for = hanger
        if hanger > MAX_SSX:
            warnings.warn(f"Ground Engine debugger: Invalid hanger ID for ssx: {hanger}")
            return

        self._loaded_ssx_files[hanger] = (SsxFileInRam(name, hanger))

    def hook__talk_load(self, hanger):
        # TODO:
        #    If the hanger is 1 - 3, this is a load for SSA/SSE/SSS.
        #    Otherwise just take the number. It's unknown what the exact mechanism / side effects are here.
        if hanger <= TALK_HANGER_OFFSET:
            hanger += TALK_HANGER_OFFSET
        self._print(f"Talk Load for hanger {hanger}")
        self._load_ssb_for = hanger

    def set_boost(self, state):
        self._boost = state
