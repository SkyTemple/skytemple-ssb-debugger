"""Testing module, to build the script state."""
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

from desmume.emulator import DeSmuME
from skytemple_ssb_debugger.sandbox.sandbox import hook__debug_print, \
    hook__debug_print_script_engine, hook__debug_enable_branch, debug_print_start, \
    point_to_print_print_debug, point_where_branch_debug_decides, debug_print2_start


def hook__read_pos(emu: DeSmuME, address, size):
    print(f"Pos read @ 0x{emu.memory.register_arm9.pc-8:0x}")
    """
    0x15C:
    Pos read @ 0x22FC310
    Pos read @ 0x22F9ABC
    Pos read @ 0x22FC454
    """


def hook__print_fn_entry(emu: DeSmuME, address, size):
    print(f"@{address:0x}: LR: {emu.memory.register_arm9.lr:0x} - "
          f"R0: {emu.memory.register_arm9.lr:0x} - R1: {emu.memory.register_arm9.r1:0x} - R2: {emu.memory.register_arm9.r2:0x}")


if __name__ == '__main__':
    emu = DeSmuME("../../../../desmume/desmume/src/frontend/interface/.libs/libdesmume.so")

    emu.open("../../../skyworkcopy_edit.nds")
    emu.savestate.load_file("../../../skyworkcopy_edit.nds.ds1")
    with open('/tmp/1.bin', 'wb') as f:
        f.write(emu.memory.unsigned[0x02100000:0x021FFFFF])
        print(f"1:")
        print(f"x: 0x{emu.memory.unsigned.read_long(0x211206C):0x}")
        print(f"y: 0x{emu.memory.unsigned.read_long(0x211206C + 0x04):0x}")
    emu.savestate.load_file("../../../skyworkcopy_edit.nds.ds2")
    with open('/tmp/2.bin', 'wb') as f:
        f.write(emu.memory.unsigned[0x02100000:0x021FFFFF])
        print(f"2:")
        print(f"x: 0x{emu.memory.unsigned.read_long(0x211206C):0x}")
        print(f"y: 0x{emu.memory.unsigned.read_long(0x211206C + 0x04):0x}")
        # diff in x: 2100

    win = emu.create_sdl_window(use_opengl_if_possible=True)

    emu.volume_set(0)

    #emu.memory.register_read(0x211206C + 0x8, partial(hook__read_pos, emu), 4)
    emu.memory.register_read(0x02100000 + 0xd580 + 0x4, partial(hook__read_pos, emu), 4)
    emu.memory.register_exec(0x022f004c, partial(hook__print_fn_entry, emu))

    """
    r0 = 0x022f2bb8 <- 0x02325800
    
    0x022f004c
    r0 + 0x200 <- Camera X
    
    """

    #emu.memory.register_exec(start_of_call_to_opcode_parsing, partial(hook__primary_opcode_parsing, emu))
    emu.memory.register_exec(debug_print_start, partial(hook__debug_print, 1, emu))
    emu.memory.register_exec(debug_print2_start, partial(hook__debug_print, 0, emu))
    emu.memory.register_exec(point_to_print_print_debug, partial(hook__debug_print_script_engine, emu))
    emu.memory.register_exec(point_where_branch_debug_decides, partial(hook__debug_enable_branch, emu))
    #emu.memory.register_exec(start_of_get_script_id_name, partial(hook__get_script_id_name, emu))

    while not win.has_quit():
        win.process_input()
        emu.cycle()
        win.draw()
