"""Testing module, to inspect ground entity structs."""
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

import binascii
from functools import partial

from desmume.emulator import DeSmuME
from skytemple_ssb_debugger.sandbox.sandbox import hook__primary_opcode_parsing, hook__debug_print, \
    hook__debug_print_script_engine, hook__debug_enable_branch, start_of_call_to_opcode_parsing, debug_print_start, \
    point_to_print_print_debug, point_where_branch_debug_decides, debug_print2_start

"""
0x2111f10
0x2112160
"""


def print_hex(mem_accessor, start, len, offs):
    print(
        f"{offs}: 0x{start + (len * offs):7x}: {binascii.hexlify(mem_accessor[start + (len * offs):start + (len * (offs + 1))]).decode('ascii')}"
    )


def find_next_free_id(emu: DeSmuME, list_start, list_entry_len, index_to_check, compare_against):
    current_pos = list_start + index_to_check
    current_val = emu.memory.signed.read_short(current_pos)
    print(f">Check: {current_val}")
    i = 0
    while current_val > compare_against:
        current_pos += list_entry_len
        current_val = emu.memory.signed.read_short(current_pos)
        print(f">Check: {current_val}")
        i += 1
    return i


def find_next_free_id_live(emu: DeSmuME):
    where_to_look = emu.memory.unsigned.read_long(pnt_to_act_list)
    return find_next_free_id(emu, where_to_look, act_list_entry_len, 0x38, 0)


def find_next_free_id_object(emu: DeSmuME):
    where_to_look = emu.memory.unsigned.read_long(pnt_to_obj_list)
    return find_next_free_id(emu, where_to_look, obj_list_entry_len, 6, -1)


def find_next_free_id_performer(emu: DeSmuME):
    return find_next_free_id(emu, emu.memory.unsigned.read_long(pnt_to_prf_list), prf_list_entry_len, 6, -1)


def find_next_free_id_event(emu: DeSmuME):
    return find_next_free_id(emu, emu.memory.unsigned.read_long(pnt_to_evt_list), evt_list_entry_len, 2, -1)


def hook__live_add(emu: DeSmuME, address, size):
    id = find_next_free_id_live(emu) - 1
    print(f"HOOK LIVE ADD - ID: {id}")
    for i in range(0, 5):
        print_hex(emu.memory.unsigned, emu.memory.unsigned.read_long(pnt_to_act_list), act_list_entry_len, i)


def hook__live_delete(emu: DeSmuME, address, size):
    id = find_next_free_id_live(emu)
    print(f"HOOK LIVE DELETE - ID: {id}")
    for i in range(0, 5):
        print_hex(emu.memory.unsigned, emu.memory.unsigned.read_long(pnt_to_act_list), act_list_entry_len, i)


def hook__object_add(emu: DeSmuME, address, size):
    id = find_next_free_id_object(emu) - 1
    print(f"HOOK OBJECT ADD - ID: {id}")
    for i in range(0, 5):
        print_hex(emu.memory.unsigned, emu.memory.unsigned.read_long(pnt_to_obj_list), obj_list_entry_len, i)


def hook__object_delete(emu: DeSmuME, address, size):
    id = find_next_free_id_object(emu)
    print(f"HOOK OBJECT DELETE - ID: {id}")
    for i in range(0, 5):
        print_hex(emu.memory.unsigned, emu.memory.unsigned.read_long(pnt_to_obj_list), obj_list_entry_len, i)


def hook__performer_add(emu: DeSmuME, address, size):
    id = find_next_free_id_performer(emu) - 1
    print(f"HOOK PERFORMER ADD - ID: {id}")
    for i in range(0, 5):
        print_hex(emu.memory.unsigned, emu.memory.unsigned.read_long(pnt_to_prf_list), prf_list_entry_len, i)


def hook__performer_delete(emu: DeSmuME, address, size):
    id = find_next_free_id_performer(emu)
    print(f"HOOK PERFORMER DELETE - ID: {id}")
    for i in range(0, 5):
        print_hex(emu.memory.unsigned, emu.memory.unsigned.read_long(pnt_to_prf_list), prf_list_entry_len, i)


def hook__event_add(emu: DeSmuME, address, size):
    id = find_next_free_id_event(emu) - 1
    print(f"HOOK EVENT ADD - ID: {id}")
    for i in range(0, 5):
        print_hex(emu.memory.unsigned, emu.memory.unsigned.read_long(pnt_to_evt_list), evt_list_entry_len, i)


def hook__event_delete(emu: DeSmuME, address, size):
    id = find_next_free_id_event(emu)
    print(f"HOOK EVENT DELETE - ID: {id}")
    for i in range(0, 5):
        print_hex(emu.memory.unsigned, emu.memory.unsigned.read_long(pnt_to_evt_list), evt_list_entry_len, i)


# US: 0x02324CFC
pnt_to_act_list = 0x0232583C
act_list_entry_len = 0x250
act_list_max_entries = 24
# US: 0x02324D00
pnt_to_obj_list = 0x02325840
obj_list_entry_len = 0x218
obj_list_max_entries = 16
# US: 0x02324D04
pnt_to_prf_list = 0x02325844
prf_list_entry_len = 0x214
prf_list_max_entries = 16
# US: 0x02324D08
pnt_to_evt_list = 0x02325848
evt_list_entry_len = 0x20
evt_list_max_entries = 32

# US: TODO
end_of_fn_ground__live__add = 0x022f8818
end_of_fn_ground__live__add_len = 0x564
# US: TODO
end_of_fn_ground__live__delete = 0x022f8f18
end_of_fn_ground__live__delete_len = 0x3C
# US: TODO
end_of_fn_ground__object__add = 0x022fc864
end_of_fn_ground__object__add_len = 0x3F8
# US: TODO
end_of_fn_ground__object__delete = 0x022fcdec
end_of_fn_ground__object__delete_len = 0x3C
# US: TODO
end_of_fn_ground__performer__add = 0x022fe0cc
end_of_fn_ground__performer__add_len = 0x338
# US: TODO
end_of_fn_ground__performer__delete = 0x022fe58c
end_of_fn_ground__performer__delete_len = 0x3C
# US: TODO
end_of_fn_ground__event__add = 0x022ff438
end_of_fn_ground__event__add_len = 0x158
# US: TODO
end_of_fn_ground__event__delete = 0x022ff608
end_of_fn_ground__event__delete_len = 0x28

if __name__ == '__main__':
    emu = DeSmuME("../../../../desmume/desmume/src/frontend/interface/.libs/libdesmume.so")

    emu.open("../../../skyworkcopy_edit.nds")
    win = emu.create_sdl_window(use_opengl_if_possible=True)

    emu.volume_set(0)

    emu.memory.register_exec(end_of_fn_ground__live__add + end_of_fn_ground__live__add_len, partial(hook__live_add, emu))
    emu.memory.register_exec(end_of_fn_ground__live__delete + end_of_fn_ground__live__delete_len, partial(hook__live_delete, emu))
    emu.memory.register_exec(end_of_fn_ground__object__add + end_of_fn_ground__object__add_len, partial(hook__object_add, emu))
    emu.memory.register_exec(end_of_fn_ground__object__delete + end_of_fn_ground__object__delete_len, partial(hook__object_delete, emu))
    emu.memory.register_exec(end_of_fn_ground__performer__add + end_of_fn_ground__performer__add_len, partial(hook__performer_add, emu))
    emu.memory.register_exec(end_of_fn_ground__performer__delete + end_of_fn_ground__performer__delete_len, partial(hook__performer_delete, emu))
    emu.memory.register_exec(end_of_fn_ground__event__add + end_of_fn_ground__event__add_len, partial(hook__event_add, emu))
    emu.memory.register_exec(end_of_fn_ground__event__delete + end_of_fn_ground__event__delete_len, partial(hook__event_delete, emu))

    emu.memory.register_exec(start_of_call_to_opcode_parsing, partial(hook__primary_opcode_parsing, emu))
    emu.memory.register_exec(debug_print_start, partial(hook__debug_print, 1, emu))
    emu.memory.register_exec(debug_print2_start, partial(hook__debug_print, 0, emu))
    emu.memory.register_exec(point_to_print_print_debug, partial(hook__debug_print_script_engine, emu))
    emu.memory.register_exec(point_where_branch_debug_decides, partial(hook__debug_enable_branch, emu))
    #emu.memory.register_exec(start_of_get_script_id_name, partial(hook__get_script_id_name, emu))

    while not win.has_quit():
        win.process_input()
        emu.cycle()
        win.draw()
