"""Testing module, to find out what memory addresses contain."""
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

from functools import partial
from typing import Tuple, List, Optional

from desmume.emulator import DeSmuME
from skytemple_ssb_debugger.sandbox.sandbox import hook__primary_opcode_parsing, hook__debug_enable_branch, \
    start_of_call_to_opcode_parsing, point_where_branch_debug_decides


class AbstractMemoryProbe:
    pass


ProbeDef = Tuple[type(AbstractMemoryProbe), int, str, int]


class MemoryProbe(AbstractMemoryProbe):
    """Probes a single section of memory."""
    MEM_PROBE_PRINT_PREFIX = ">>>M-- "

    def __init__(self, manager: 'MemoryProbeManager', name: str, start: int, length: int):
        self.name = name
        self.start = start
        self.length = length
        self.manager = manager
        self.old_values1 = [-1 for _ in range(start, start + length)]
        self.old_values2 = [-1 for _ in range(start, start + length)]
        self.old_values4 = [-1 for _ in range(start, start + length)]
        for addr in manager.probe_register_memory(self, start, length):
            manager.emu.memory.register_write(addr, self.callback)

    def deactivate(self):
        self.manager.probe_unregister_memory(self, self.start, self.length)

    def callback(self, address, size):
        offset = address - self.start
        value = 0
        if size == 1:
            value = emu.memory.unsigned.read_byte(address)
            old_val_idx = self.old_values1
        elif size == 2:
            value = emu.memory.unsigned.read_short(address)
            old_val_idx = self.old_values2
        elif size == 4:
            value = emu.memory.unsigned.read_long(address)
            old_val_idx = self.old_values4
        else:
            raise RuntimeError("Invalid write length")
        if value != old_val_idx[offset]:
            # TODO: actually we would need to also refresh the other two arrays...
            old_val_idx[offset] = value
            # Debugging (reduce noise):
            if self.name == '*ACT' and (offset % 0x250 == 0x14c or offset % 0x250 == 0x1e4):
                return
            if self.name == '*UNK1' and offset == 0x24:
                return
            if self.name == '*OBJ' and (offset % 0x218 == 0x1ac):
                return
            self.print_s(f"+0x{offset:3x} [{size}] = 0x{value:0x} <- 0x0{self.manager.emu.memory.register_arm9.pc - 8:7x}")

    def __str__(self):
        return f"<{self.name}>"

    def print_s(self, string):
        self.print(str(self) + ": " + str(string))

    @classmethod
    def print(cls, string):
        print(cls.MEM_PROBE_PRINT_PREFIX + str(string))


class PointerProbe(AbstractMemoryProbe):
    """Probes a pointer to a section of memory. If the pointer changes,
    the probed target memory region is also changed."""

    def __init__(self, manager: 'MemoryProbeManager', name: str, pnt: int, length_of_target_region: int):
        self.name = name
        self.manager = manager
        self.pnt = pnt
        self.current_pnt_target = 0
        self.length_of_target_region = length_of_target_region
        self.probe: Optional[MemoryProbe] = None
        self.manager.emu.memory.register_write(self.pnt, self.callback, 4)
        self.register()

    def register(self):
        self.current_pnt_target = self.manager.emu.memory.unsigned.read_long(self.pnt)
        self.print_s(f"Pointer location changed -> 0x{self.current_pnt_target:0x}  <- 0x0{self.manager.emu.memory.register_arm9.pc - 8:7x}")

        if self.current_pnt_target == 0:
            self.probe = None
            self.print_s("NULL Pointer.")
        else:
            self.probe = MemoryProbe(self.manager, "*" + self.name, self.current_pnt_target, self.length_of_target_region)

    def unregister(self):
        if self.probe is not None:
            self.probe.deactivate()

    def callback(self, address, size):
        if size != 4:
            self.print_s("WARNING: Pointer write was not long.")
        self.unregister()
        self.register()

    def print_s(self, string):
        MemoryProbe.print(str(self) + ": " + str(string))

    def __str__(self):
        return f"<{self.name}>"


class MemoryProbeManager:
    """Manages all the memory probes"""
    def __init__(self, emu: 'DeSmuME', probe_defs: List[ProbeDef]):
        self.watched_memory_regions = {}
        self.emu = emu
        for probe_def in probe_defs:
            probe_def[0](self, probe_def[2], probe_def[1], probe_def[3])

    def probe_register_memory(self, probe: AbstractMemoryProbe, start: int, length: int) -> List[int]:
        """
        Register a list of addresses to watch, returns all addreeses not already watched.
        Prints warning for all already watched.
        """
        ok = []
        for addr in range(start, start + length):
            if addr not in self.watched_memory_regions:
                self.watched_memory_regions[addr] = probe
                ok.append(addr)
            else:
                MemoryProbe.print(f"Warning: {probe} wanted to watch 0x{start:0x}+0x{addr-start:0x}, "
                                  f"but it was already watched by {self.watched_memory_regions[addr]}")
        return ok

    def probe_unregister_memory(self, probe: AbstractMemoryProbe, start: int, length: int):
        for addr in range(start, start + length):
            if addr in self.watched_memory_regions and self.watched_memory_regions[addr] == probe:
                del self.watched_memory_regions[addr]
                self.emu.memory.register_write(addr, None)


if __name__ == '__main__':
    emu = DeSmuME("../../../../desmume/desmume/src/frontend/interface/.libs/libdesmume.so")

    emu.open("../../../skyworkcopy_edit.nds")
    win = emu.create_sdl_window(use_opengl_if_possible=True)

    emu.volume_set(0)

    """
    Interesting memory locations to watch:
    - 0x02325834: Pointer to: Script engine loader state -> POINTS TO MAIN SCRIPT STRUCT! [Length at least 0xf0?]
    - 0x02325838: Pointer to: ???               [12 bytes per ???]
    - 0x0232583C: Pointer to: Actor data?       [0x250 bytes per Actor] -> STARTING AT 0x38: Actor script struct
    - 0x02325840: Pointer to: Object data?      [0x218 per Object]      -> STARTING AT 0x3C: Object script struct
    - 0x02325844: Pointer to: Performer data?   [0x214 per Performer]   -> STARTING AT 0x3C: Perf. script struct
    - 0x02325848: Pointer to: Event data...?    [0x32 per event?]
    - 0x020a8890: Pointer to?: ? Related to actors?
    - 0x023226b0: Pointer to?: ? Related to actors?
    - 0x023257ac: Pointer to?: ? Used in fcn.022e683c  - Maybe something about SSB state?
    - 0x023257e4: Pointer to?: ? Used in fcn.022e88f8  - Maybe something about SSB state?
    - 0x02325800: Pointer to?: ? Used in fcn.022f28ac  - Seems to relate to map bg?
    - 0x02317424: Pointer to?: ? Used in fcn.022dd62c
    - 0x02094f50: Pointer to: Same as 0x020a8890
    - 0x02094f54: Pointer to?: ? Used in fcn.0200c2e4
    - 0x02094f5c: Pointer to?: ? Used in fcn.0200c2e4
    
    --
    
    - 0x211617c: Main script struct (might be dynamic?) [at least f0 entries]
    - 0x2111f48: Actor 0 script struct (mbd?)
    - 0x2112198: Actor 1 script struct (mbd?)
    
    - 0x023223ac: Something actor related. | EDIT: Main ScriptRuntime storage??? - Is the first field in all script structs.
    
    - 0x022fb3a4: (-ac) Something actor related.
    - 0x022fb3ac: Something actor related.
    
    - 0x022fb4a0: Something actor related.
    
    - 0x02130d4c: (-4e) Something actor related.
    - 0x0212b17c: Something actor related.
    
    -- Important during script ini (used by fcn.022dd004)
    - 0x023257a4 pointer
    - 0x023259c0 pointer
    
    -- Something SSB loading related:
    - 0x02325ab4
    - 0x023257c4 SSB file struct?
    
    -- Struct current script data (US 2324F74)
    - 0x02325ab4
    
    - 0x2120cc0: Groups of unionall.ssb
        
    THEORY: Script structs come right after their memory entries for actors, performers and objects (and possibly global script?!)
    //  struct ActorEntryMemory
    //      0x00 actorid
    //      0x02 direction
    //      0x03 xoffset
    //      0x04 yoffset
    //      0x05 actunk0x08
    //      0x06 actunk0x0A
    //      0x07 --
    //      0x08 scriptid
    
    //  struct PerformerEntryMemory
    //      0x00 perfid
    //      0x02 direction
    //      0x03 perfunk0x04
    //      0x04 perfunk0x06
    //      0x05 perfunk0x08
    //      0x06 perfunk0x0A
    //      0x07 perfunk0x0C
    //      0x08 perfunk0x0E    
    """
    emu.memory.register_exec(start_of_call_to_opcode_parsing, partial(hook__primary_opcode_parsing, emu))
    #emu.memory.register_exec(debug_print_start, partial(hook__debug_print, 1, emu))
    #emu.memory.register_exec(debug_print2_start, partial(hook__debug_print, 0, emu))
    #emu.memory.register_exec(point_to_print_print_debug, partial(hook__debug_print_script_engine, emu))
    emu.memory.register_exec(point_where_branch_debug_decides, partial(hook__debug_enable_branch, emu))
    #emu.memory.register_exec(start_of_get_script_id_name, partial(hook__get_script_id_name, emu))

    MemoryProbeManager(emu, [
        #(PointerProbe, 0x02325834, 'SELS',      0xF0),       # == _mainS
        ##(PointerProbe, 0x02325838, 'UNK1',      0x5C),
        ##(PointerProbe, 0x0232583C, 'ACT',       2 * 0x250),  # == starting with 0x38 -> _act0S
        ##(PointerProbe, 0x02325840, 'OBJ',       2 * 0x218),
        ##(PointerProbe, 0x02325844, 'PRF',       2 * 0x214),
        #(PointerProbe, 0x02325848, 'EVT',       2 * 0x32),
        ##(PointerProbe, 0x020a8890, 'act1',      0x20),       # == fn2e4_1
        ##(PointerProbe, 0x023226b0, 'act2',      0x20),
        #(MemoryProbe,  0x023257ac, 'fn83c_1',   0x04), #??? Overlaps with SSBFile1
        (PointerProbe, 0x023257e4, 'fn8f8_1',   0x20),
        (PointerProbe, 0x02325800, 'fn8ac_1',   0x220),
        (PointerProbe, 0x02317424, 'fn62c_1',   0x20),
        (PointerProbe, 0x02094f50, 'fn2e4_1',   0x20),
        (PointerProbe, 0x02094f54, 'fn2e4_2',   0x20),
        (PointerProbe, 0x02094f5C, 'fn2e4_3',   0x20),

        #(MemoryProbe,  0x0211617c, '_mainS',    0xF0),
        #(MemoryProbe,  0x02111f48, '_act0S',    0xF0),
        #(MemoryProbe,  0x02112198, '_act1S',    0xF0),
        #(MemoryProbe,  0x023223ac, 'SCRIPTRUNTIME',   0xF0),
        #(MemoryProbe,  0x022fb3a4, '_act0_S_0', 0x08),
        #(MemoryProbe,  0x022fb3a8, '_act0_S_1', 0x08),
        #(MemoryProbe,  0x022fb3ac, '_act0_S_2', 0x08),
        #(MemoryProbe,  0x022fb4a0, '_act0_S_3', 0x08),

        #(MemoryProbe, 0x023257a4, 'SSBFile1', 0x40),
        #(MemoryProbe, 0x023259c0, 'INIT2', 4),
        #(MemoryProbe, 0x02325ab0, 'INIT3', 4),  # used in 0x022e4f04
        #(MemoryProbe, 0x02325ad8, 'INIT4', 4),  # used in 0x022e8964
        # used in 0x022dd058:
        #(MemoryProbe, 0x023259d4, 'INIT058_1', 4),
        #(MemoryProbe, 0x023259e4, 'INIT058_2', 4),
        #(MemoryProbe, 0x02325a0c, 'INIT058_3', 4),

        #(MemoryProbe, 0x023259f4, 'INIT058_4', 4 * 4),
        #(MemoryProbe, 0x02325a5c, 'INIT058_5', 4 * 4),

        #(MemoryProbe, 0x02325ac2, 'SSBInit0',  0xE),
        #(MemoryProbe, 0x02325ab4, 'SSBInit1',  0xE),
        #(MemoryProbe, 0x020afc08, 'SSBInit2',  0x28),

        #(MemoryProbe, 0x023257c4, 'SSBFile2',  0x10),
        #(MemoryProbe, 0x023257b4, 'SSBFile3',  0x10),

        #(PointerProbe, 0x02318ff0, 'LoadUnk', 0x40),

        #(MemoryProbe, 0x2120cc0, 'unionall', 0xFF),

    ])

    while not win.has_quit():
        win.process_input()
        emu.cycle()
        win.draw()

    with open('/tmp/0x212ecc0.bin', 'wb') as f:
        f.write(emu.memory.unsigned[0x212ecc0:0x212ecc0+0xff])
