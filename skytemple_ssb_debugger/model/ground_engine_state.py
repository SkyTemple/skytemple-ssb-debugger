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
import warnings
from threading import Lock
from typing import Optional, List, Tuple

from gi.repository import Gtk, GLib

from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_debugger.context.abstract import AbstractDebuggerControlContext
from skytemple_ssb_debugger.emulator_thread import EmulatorThread
from skytemple_ssb_debugger.model.address_container import AddressContainer
from skytemple_ssb_debugger.model.breakpoint_state import BreakpointState
from skytemple_ssb_debugger.model.ground_state.actor import Actor
from skytemple_ssb_debugger.model.ground_state.event import Event
from skytemple_ssb_debugger.model.ground_state.global_script import GlobalScript
from skytemple_ssb_debugger.model.ground_state.map import Map
from skytemple_ssb_debugger.model.ground_state.object import Object
from skytemple_ssb_debugger.model.ground_state.performer import Performer
from skytemple_ssb_debugger.model.ground_state.ssb_file_in_ram import SsbFileInRam
from skytemple_ssb_debugger.model.ground_state.ssx_file_in_ram import SsxFileInRam
from skytemple_ssb_debugger.model.ssb_files.file_manager import SsbFileManager
from skytemple_ssb_debugger.threadsafe import threadsafe_gtk_nonblocking, threadsafe_emu, synchronized, synchronized_now

TALK_HANGER_OFFSET = 3
MAX_SSX = 3
MAX_SSB = MAX_SSX + TALK_HANGER_OFFSET
O11_BYTE_CHECK = bytes([0xf0, 0x4f, 0x2d, 0xe9, 0x34, 0xd0, 0x4d, 0xe2, 0x64, 0x2a, 0x9f, 0xe5])


ground_engine_lock = Lock()


class GroundEngineState:
    def __init__(self, emu_thread: EmulatorThread, rom_data: Pmd2Data, print_callback, inform_ground_engine_start_cb,
                 ssb_file_manager: SsbFileManager, context: AbstractDebuggerControlContext):
        super().__init__()
        self.emu_thread = emu_thread
        self.rom_data = rom_data
        self.ssb_file_manager = ssb_file_manager
        self.context = context
        self.logging_enabled = False
        self._boost = False

        self.pnt_map = rom_data.binaries['overlay/overlay_0011.bin'].pointers['GroundStateMap'].begin_absolute
        base_pnt = rom_data.binaries['overlay/overlay_0011.bin'].blocks['GroundStatePntrs'].begin_absolute
        self.pnt_main_script_struct = base_pnt
        #self.pnt_unk = base_pnt + 4
        self.pnt_actors = base_pnt + 8
        self.pnt_objects = base_pnt + 12
        self.pnt_performers = base_pnt + 16
        self.pnt_events = base_pnt + 20
        self.pnt_unionall_load_addr = rom_data.binaries['overlay/overlay_0011.bin'].pointers['UnionallRAMAddress'].begin_absolute
        self.unionall_load_addr = AddressContainer(0)

        self._load_ssb_for = None

        self._running = False
        self._print_callback = print_callback
        self._inform_ground_engine_start_cb = inform_ground_engine_start_cb

        self._global_script = GlobalScript(self.emu_thread, self.rom_data, self.pnt_main_script_struct, self.unionall_load_addr)
        self._map = Map(self.emu_thread, self.rom_data, self.pnt_map)

        self._actors = []
        info = self.rom_data.script_data.ground_state_structs['Actors']
        for i in range(0, info.maxentries):
            self._actors.append(Actor(self.emu_thread, self.rom_data, self.pnt_actors, i * info.entrylength, self.unionall_load_addr))

        self._objects = []
        info = self.rom_data.script_data.ground_state_structs['Objects']
        for i in range(0, info.maxentries):
            self._objects.append(Object(self.emu_thread, self.rom_data, self.pnt_objects, i * info.entrylength, self.unionall_load_addr))

        self._performers = []
        info = self.rom_data.script_data.ground_state_structs['Performers']
        for i in range(0, info.maxentries):
            self._performers.append(Performer(self.emu_thread, self.rom_data, self.pnt_performers, i * info.entrylength, self.unionall_load_addr))

        self._events = []
        info = self.rom_data.script_data.ground_state_structs['Events']
        for i in range(0, info.maxentries):
            self._events.append(Event(self.emu_thread, self.rom_data, self.pnt_events, i * info.entrylength))

        self._loaded_ssx_files: List[Optional[SsxFileInRam]] = []
        self._loaded_ssb_files: List[Optional[SsbFileInRam]] = []
        self.reset()

    @synchronized_now(ground_engine_lock)
    def break_pulled(self, state: BreakpointState):
        """Set the breaked property of the SSB file in the state's hanger."""
        self._loaded_ssb_files[state.hanger_id].breaked = True
        self._loaded_ssb_files[state.hanger_id].breaked__handler_file = state.get_file_state().handler_filename
        state.add_release_hook(self.break_released)

    def step_into_macro_call(self, state: BreakpointState):
        self._loaded_ssb_files[state.hanger_id].breaked__handler_file = state.get_file_state().handler_filename

    @synchronized_now(ground_engine_lock)
    def break_released(self, state: BreakpointState):
        """Reset the breaked property of loaded ssb files again."""
        for x in self._loaded_ssb_files:
            if x is not None:
                x.breaked = False
                x.breaked__handler_file = None

    @property
    def running(self):
        return self._running

    @property
    @synchronized_now(ground_engine_lock)
    def loaded_ssx_files(self):
        return self._loaded_ssx_files

    @property
    @synchronized_now(ground_engine_lock)
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

    def collect(self) -> Tuple[GlobalScript, List[SsbFileInRam], List[SsxFileInRam], List[Actor], List[Object], List[Performer], List[Event]]:
        loaded_ssb_files = self.loaded_ssb_files
        loaded_ssx_files = self.loaded_ssx_files
        actors = [x for x in self.actors if x is not None]
        objects = [x for x in self.objects if x is not None]
        performers = [x for x in self.performers if x is not None]
        events = [x for x in self.events if x is not None]

        return self.global_script, loaded_ssb_files, loaded_ssx_files, actors, objects, performers, events

    def watch(self):
        ov11 = self.rom_data.binaries['overlay/overlay_0011.bin']

        self.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x3C, self.hook__ground_start)
        self.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x210, self.hook__ground_quit)
        self.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x598, self.hook__ground_map_change)
        self.register_exec(ov11.functions['SsbLoad1'].begin_absolute, self.hook__ssb_load)
        self.register_exec(ov11.functions['SsbLoad2'].begin_absolute, self.hook__ssb_load)
        self.register_exec(ov11.functions['StationLoadHanger'].begin_absolute + 0xC0, self.hook__ssx_load)
        self.register_exec(ov11.functions['ScriptStationLoadTalk'].begin_absolute, self.hook__talk_load)
        threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.memory.register_write(
            self.pnt_unionall_load_addr, self.hook__write_unionall_address, 4
        ))

    def remove_watches(self):
        ov11 = self.rom_data.binaries['overlay/overlay_0011.bin']

        self.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x3C, None)
        self.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x210, None)
        self.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x598, None)
        self.register_exec(ov11.functions['SsbLoad1'].begin_absolute, None)
        self.register_exec(ov11.functions['SsbLoad2'].begin_absolute, None)
        self.register_exec(ov11.functions['StationLoadHanger'].begin_absolute + 0xC0, None)
        self.register_exec(ov11.functions['ScriptStationLoadTalk'].begin_absolute, None)

    def register_exec(self, pnt, cb):
        threadsafe_emu(self.emu_thread, lambda: self.emu_thread.emu.memory.register_exec(pnt, cb))

    @synchronized_now(ground_engine_lock)
    def reset(self, keep_global=False, fully=False):
        # ! Runs from either GTK or emu thread !
        if fully:
            self._running = False
        self._loaded_ssx_files = [None for _ in range(0, MAX_SSX + 1)]
        if keep_global:
            glob = self._loaded_ssb_files[0]
        for i, ssb in enumerate(self._loaded_ssb_files):
            if (i != 0 or not keep_global) and ssb is not None:
                self.ssb_file_manager.close_in_ground_engine(ssb.file_name)
        self._loaded_ssb_files = [None for _ in range(0, MAX_SSB + 1)]
        if keep_global:
            self._loaded_ssb_files[0] = glob

    @synchronized_now(ground_engine_lock)
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

    @synchronized_now(ground_engine_lock)
    def deserialize(self, state: dict):
        """Load a saved state back from a dict"""
        self._running = state['running']
        self._load_ssb_for = state['load_ssb_for']
        self._loaded_ssb_files = [
            SsbFileInRam(fn_and_hash[0], hng, fn_and_hash[1])
            if fn_and_hash is not None else None
            for hng, fn_and_hash in enumerate(state['ssbs'])
        ]
        # - Load SSB file hashes from ground state file, if the hashes don't match on reload with the saved
        #   files, mark them as not up to date in RAM and show warning for affected files.
        were_invalid = []
        for f in self._loaded_ssb_files:
            if f is not None and f.hash != self.ssb_file_manager.hash_for(f.file_name):
                were_invalid.append(f.file_name)
        if len(were_invalid) > 0:
            n = '\n'
            md = self.context.message_dialog_cls()(None,
                                                   Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.WARNING,
                                                   Gtk.ButtonsType.OK,
                                                   f"Some SSB script files that are loaded in RAM were changed. You can not debug "
                                                   f"these files, until they are reloaded:\n{n.join(were_invalid)}",
                                                   title="Warning!")
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
        threadsafe_emu(self.emu_thread, lambda: self.unionall_load_addr.set(self.emu_thread.emu.memory.unsigned.read_long(self.pnt_unionall_load_addr)))

    def _print(self, string):
        if self.logging_enabled and not self._boost:
            self._print_callback(f"Ground Event >> {string}")

    # >>> ALL CALLBACKS BELOW ARE RUNNING IN THE EMULATOR THREAD <<<

    def hook__ground_start(self, address, size):
        if not self.overlay11_loaded():
            return
        self._print("Ground Start")
        threadsafe_gtk_nonblocking(lambda: self.reset())
        ground_engine_lock.acquire()
        self._running = True
        ground_engine_lock.release()
        self._inform_ground_engine_start_cb()

    def hook__ground_quit(self, address, size):
        if not self.overlay11_loaded():
            return
        self._print("Ground Quit")
        ground_engine_lock.acquire()
        self._running = False
        ground_engine_lock.release()

    def hook__ground_map_change(self, address, size):
        if not self.overlay11_loaded():
            return
        self._print("Ground Map Change")
        self.reset(keep_global=True)

    @synchronized_now(ground_engine_lock)
    def hook__ssb_load(self, address, size):
        if not self.overlay11_loaded():
            return
        name = self.emu_thread.emu.memory.read_string(self.emu_thread.emu.memory.register_arm9.r1)
        load_for = self._load_ssb_for if self._load_ssb_for is not None else 0
        self._print(f"SSB Load {name} for hanger {load_for}")
        self._load_ssb_for = None

        if load_for > MAX_SSB:
            warnings.warn(f"Ground Engine debugger: Invalid hanger ID for ssb: {load_for}")
            return
        threadsafe_gtk_nonblocking(lambda: self.ssb_file_manager.open_in_ground_engine(name))
        self._loaded_ssb_files[load_for] = (SsbFileInRam(name, load_for))

    @synchronized(ground_engine_lock)
    def hook__ssx_load(self, address, size):
        if not self.overlay11_loaded():
            return
        hanger = self.emu_thread.emu.memory.register_arm9.r2
        name = self.emu_thread.emu.memory.read_string(self.emu_thread.emu.memory.register_arm9.r3)
        self._print(f"SSX Load {name} for hanger {hanger}")
        self._load_ssb_for = hanger
        if hanger > MAX_SSX:
            warnings.warn(f"Ground Engine debugger: Invalid hanger ID for ssx: {hanger}")
            return

        self._loaded_ssx_files[hanger] = (SsxFileInRam(name, hanger))

    @synchronized_now(ground_engine_lock)
    def hook__talk_load(self, address, size):
        if not self.overlay11_loaded():
            return
        hanger = self.emu_thread.emu.memory.register_arm9.r0
        # TODO:
        #    If the hanger is 1 - 3, this is a load for SSA/SSE/SSS.
        #    Otherwise just take the number. It's unknown what the exact mechanism / side effects are here.
        if hanger <= TALK_HANGER_OFFSET:
            hanger += TALK_HANGER_OFFSET
        self._print(f"Talk Load for hanger {hanger}")
        self._load_ssb_for = hanger

    @synchronized_now(ground_engine_lock)
    def hook__write_unionall_address(self, address, size):
        """Write the location of the unionall script into the container object for this"""
        if not self.overlay11_loaded():
            return
        self.unionall_load_addr.set(self.emu_thread.emu.memory.unsigned.read_long(self.pnt_unionall_load_addr))

    def overlay11_loaded(self):
        """TODO: Replace with a proper check..."""
        begin_offset = self.rom_data.binaries['overlay/overlay_0011.bin'].functions['GroundMainLoop'].begin_absolute
        return self.emu_thread.emu.memory.unsigned[begin_offset:begin_offset+len(O11_BYTE_CHECK)] == O11_BYTE_CHECK

    @synchronized(ground_engine_lock)
    def set_boost(self, state):
        self._boost = state
