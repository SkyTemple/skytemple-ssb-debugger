"""Testing module, to find out how to map ssb files in memory back to disk."""
#  Copyright 2020-2021 Parakoopa and the SkyTemple Contributors
#
#  This file is part of SkyTemple.
#
#  SkyTemple is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.X
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
from skytemple_ssb_debugger.sandbox.sandbox import hook__primary_opcode_parsing, hook__debug_print, \
    hook__debug_enable_branch, start_of_call_to_opcode_parsing, debug_print_start, \
    point_where_branch_debug_decides, debug_print2_start

# Unionall group pointer set at:
unionall_set_pnt = 0x022e889c
# Other ssb group pointers set at:
other_set_pnt = 0x022e542c


def hook__unionall(emu: DeSmuME, address, size):
    print(f">>>>> unionall group header loaded at {emu.memory.register_arm9.r2}")


def hook__other(emu: DeSmuME, address, size):
    print(f">>>>> some ssb group header loaded at {emu.memory.register_arm9.r0}")


if __name__ == '__main__':
    emu = DeSmuME("../../../../desmume/desmume/src/frontend/interface/.libs/libdesmume.so")

    emu.open("../../../skyworkcopy_edit.nds")

    win = emu.create_sdl_window(use_opengl_if_possible=True)

    emu.volume_set(0)

    emu.memory.register_exec(start_of_call_to_opcode_parsing, partial(hook__primary_opcode_parsing, emu))
    emu.memory.register_exec(debug_print_start, partial(hook__debug_print, 1, emu))
    emu.memory.register_exec(debug_print2_start, partial(hook__debug_print, 0, emu))
    #emu.memory.register_exec(point_to_print_print_debug, partial(hook__debug_print_script_engine, emu))
    emu.memory.register_exec(point_where_branch_debug_decides, partial(hook__debug_enable_branch, emu))
    #emu.memory.register_exec(start_of_get_script_id_name, partial(hook__get_script_id_name, emu))
    emu.memory.register_exec(unionall_set_pnt, partial(hook__unionall, emu))
    emu.memory.register_exec(other_set_pnt, partial(hook__other, emu))

    while not win.has_quit():
        win.process_input()
        emu.cycle()
        win.draw()

    with open('/tmp/0x212ecc0.bin', 'wb') as f:
        f.write(emu.memory.unsigned[0x212ecc0:0x212ecc0+0xff])


# Unionall group pointer set at: 0x022e889c
# Other ssb group pointers set at: 0x022e542c
