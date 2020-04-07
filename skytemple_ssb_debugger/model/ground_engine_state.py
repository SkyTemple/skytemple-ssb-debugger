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
import warnings
from typing import Optional, List, Tuple

from desmume.emulator import DeSmuME
from skytemple_files.common.ppmdu_config.data import Pmd2Data
from skytemple_ssb_debugger.model.ground_state.global_script import GlobalScript
from skytemple_ssb_debugger.model.ground_state.actor import Actor, ACTOR_BEGIN_SCRIPT_STRUCT
from skytemple_ssb_debugger.model.ground_state.map import Map
from skytemple_ssb_debugger.model.ground_state.event import Event, EVENT_EXISTS_CHECK_OFFSET
from skytemple_ssb_debugger.model.ground_state.loaded_ssb_file import LoadedSsbFile
from skytemple_ssb_debugger.model.ground_state.loaded_ssx_file import LoadedSsxFile
from skytemple_ssb_debugger.model.ground_state.object import Object, OBJECT_BEGIN_SCRIPT_STRUCT
from skytemple_ssb_debugger.model.ground_state.performer import Performer, PERFORMER_BEGIN_SCRIPT_STRUCT

TALK_HANGER_OFFSET = 3
MAX_SSX = 3
MAX_SSB = MAX_SSX + TALK_HANGER_OFFSET


class GroundEngineState:
    def __init__(self, emu: DeSmuME, rom_data: Pmd2Data, print_callback):
        self.emu = emu
        self.rom_data = rom_data
        self.logging_enabled = False

        self.pnt_map = rom_data.binaries['overlay/overlay_0011.bin'].pointers['GroundStateMap'].begin_absolute
        base_pnt = rom_data.binaries['overlay/overlay_0011.bin'].blocks['GroundStatePntrs'].begin_absolute
        self.pnt_main_script_struct = base_pnt
        #self.pnt_unk = base_pnt + 4
        self.pnt_actors = base_pnt + 8
        self.pnt_objects = base_pnt + 12
        self.pnt_performers = base_pnt + 16
        self.pnt_events = base_pnt + 20

        self._load_ssb_for = None

        self._running = False
        self._print_callback = print_callback

        self._loaded_ssx_files: List[Optional[LoadedSsxFile]] = []
        self._loaded_ssb_files: List[Optional[LoadedSsbFile]] = []
        self.reset()

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
        blk = self.emu.memory.unsigned.read_long(self.pnt_main_script_struct)
        return GlobalScript(self.emu.memory, self.rom_data, blk)

    @property
    def map(self) -> Map:
        blk = self.emu.memory.unsigned.read_long(self.pnt_map)
        return Map(self.emu.memory, self.rom_data, blk)

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
        info = self.rom_data.script_data.ground_state_structs['Actors']
        blk = self.emu.memory.unsigned.read_long(self.pnt_actors) + (index * info.entrylength)
        if self.emu.memory.signed.read_short(blk + ACTOR_BEGIN_SCRIPT_STRUCT) <= 0:
            return None
        return Actor(self.emu.memory, self.rom_data, blk)

    def get_object(self, index: int) -> Optional[Object]:
        info = self.rom_data.script_data.ground_state_structs['Objects']
        blk = self.emu.memory.unsigned.read_long(self.pnt_objects) + (index * info.entrylength)
        if self.emu.memory.signed.read_short(blk + OBJECT_BEGIN_SCRIPT_STRUCT) <= 0:
            return None
        return Object(self.emu.memory, self.rom_data, blk)

    def get_performer(self, index: int) -> Optional[Performer]:
        info = self.rom_data.script_data.ground_state_structs['Performers']
        blk = self.emu.memory.unsigned.read_long(self.pnt_performers) + (index * info.entrylength)
        if self.emu.memory.signed.read_short(blk + PERFORMER_BEGIN_SCRIPT_STRUCT) <= 0:
            return None
        return Performer(self.emu.memory, self.rom_data, blk)

    def get_event(self, index: int) -> Optional[Event]:
        info = self.rom_data.script_data.ground_state_structs['Events']
        blk = self.emu.memory.unsigned.read_long(self.pnt_events) + (index * info.entrylength)
        if self.emu.memory.signed.read_short(blk + EVENT_EXISTS_CHECK_OFFSET) <= 0:
            return None
        return Event(self.emu.memory, self.rom_data, blk)

    def collect(self) -> Tuple[GlobalScript, List[LoadedSsbFile], List[LoadedSsxFile], List[Actor], List[Object], List[Performer], List[Event]]:
        loaded_ssb_files = self.loaded_ssb_files
        loaded_ssx_files = self.loaded_ssx_files
        actors = [x for x in self.actors if x is not None]
        objects = [x for x in self.objects if x is not None]
        performers = [x for x in self.performers if x is not None]
        events = [x for x in self.events if x is not None]

        return self.global_script, loaded_ssb_files, loaded_ssx_files, actors, objects, performers, events

    def watch(self):
        ov11 = self.rom_data.binaries['overlay/overlay_0011.bin']

        self.emu.memory.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x3C, self.hook__ground_start)
        self.emu.memory.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x210, self.hook__ground_quit)
        self.emu.memory.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x598, self.hook__ground_map_change)
        self.emu.memory.register_exec(ov11.functions['SsbLoad1'].begin_absolute, self.hook__ssb_load)
        self.emu.memory.register_exec(ov11.functions['SsbLoad2'].begin_absolute, self.hook__ssb_load)
        self.emu.memory.register_exec(ov11.functions['StationLoadHanger'].begin_absolute + 0xC0, self.hook__ssx_load)
        self.emu.memory.register_exec(ov11.functions['ScriptStationLoadTalk'].begin_absolute, self.hook__talk_load)

    def remove_watches(self):
        ov11 = self.rom_data.binaries['overlay/overlay_0011.bin']

        self.emu.memory.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x3C, None)
        self.emu.memory.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x210, None)
        self.emu.memory.register_exec(ov11.functions['GroundMainLoop'].begin_absolute + 0x598, None)
        self.emu.memory.register_exec(ov11.functions['SsbLoad1'].begin_absolute, None)
        self.emu.memory.register_exec(ov11.functions['SsbLoad2'].begin_absolute, None)
        self.emu.memory.register_exec(ov11.functions['StationLoadHanger'].begin_absolute + 0xC0, None)
        self.emu.memory.register_exec(ov11.functions['ScriptStationLoadTalk'].begin_absolute, None)

    def hook__ground_start(self, address, size):
        self._print("Ground Start")
        self.reset()
        self._running = True

    def hook__ground_quit(self, address, size):
        self._print("Ground Quit")
        self._running = False

    def hook__ground_map_change(self, address, size):
        self._print("Ground Map Change")
        self.reset(keep_global=True)

    def hook__ssb_load(self, address, size):
        name = self.emu.memory.read_string(self.emu.memory.register_arm9.r1)
        load_for = self._load_ssb_for if self._load_ssb_for is not None else 0
        self._print(f"SSB Load {name} for hanger {load_for}")
        self._load_ssb_for = None

        if load_for > MAX_SSB:
            warnings.warn(f"Ground Engine debugger: Invalid hanger ID for ssb: {load_for}")
            return
        self._loaded_ssb_files[load_for] = (LoadedSsbFile(name, load_for))

    def hook__ssx_load(self, address, size):
        hanger = self.emu.memory.register_arm9.r2
        name = self.emu.memory.read_string(self.emu.memory.register_arm9.r3)
        self._print(f"SSX Load {name} for hanger {hanger}")
        self._load_ssb_for = hanger
        if hanger > MAX_SSX:
            warnings.warn(f"Ground Engine debugger: Invalid hanger ID for ssx: {hanger}")
            return

        self._loaded_ssx_files[hanger] = (LoadedSsxFile(name, hanger))

    def hook__talk_load(self, address, size):
        hanger = self.emu.memory.register_arm9.r0
        # TODO:
        #    If the hanger is 1 - 3, this is a load for SSA/SSE/SSS.
        #    Otherwise just take the number. It's unknown what the exact mechanism / side effects are here.
        if hanger <= TALK_HANGER_OFFSET:
            hanger += TALK_HANGER_OFFSET
        self._print(f"Talk Load for hanger {hanger}")
        self._load_ssb_for = hanger

    def _print(self, string):
        if self.logging_enabled:
            self._print_callback(f"Ground Event >> {string}")

    def reset(self, keep_global=False):
        self._loaded_ssx_files = [None for _ in range(0, MAX_SSX + 1)]
        if keep_global:
            glob = self._loaded_ssb_files[0]
        self._loaded_ssb_files = [None for _ in range(0, MAX_SSB + 1)]
        if keep_global:
            self._loaded_ssb_files[0] = glob

    def serialize(self):
        """Convert the state (that's not directly tied to the game's memory) to a dict for saving."""
        return {
            'running': self.running,
            'ssbs': [x.file_name if x is not None else None for x in self._loaded_ssb_files],
            'ssxs': [x.file_name if x is not None else None for x in self._loaded_ssx_files],
            'load_ssb_for': self._load_ssb_for
        }

    def deserialize(self, state: dict):
        """Load a saved state back from a dict"""
        self._running = state['running']
        self._load_ssb_for = state['load_ssb_for']
        self._loaded_ssb_files = [LoadedSsbFile(fn, hng) if fn is not None else None for hng, fn in enumerate(state['ssbs'])]
        self._loaded_ssx_files = [LoadedSsxFile(fn, hng) if fn is not None else None for hng, fn in enumerate(state['ssxs'])]
