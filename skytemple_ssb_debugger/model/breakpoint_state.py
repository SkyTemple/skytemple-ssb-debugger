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
import threading
from enum import Enum
from typing import Optional

from skytemple_ssb_debugger.model.breakpoint_file_state import BreakpointFileState
from skytemple_ssb_debugger.model.script_runtime_struct import ScriptRuntimeStruct
from skytemple_ssb_debugger.threadsafe import synchronized


class BreakpointStateType(Enum):
    # INITIAL STATE: The breakpoint is being stopped at.
    STOPPED = 0
    # FINAL STATES: What happened / what to do next? - See the corresponding methods of BreakpointState.
    FAIL_HARD = 1
    RESUME = 2
    STEP_OVER = 3
    STEP_INTO = 4
    STEP_OUT = 5
    STEP_NEXT = 6
    # Manually step to an opcode offset of the SSB file currently stopped for.
    STEP_MANUAL = 10


breakpoint_state_state_lock = threading.Lock()
file_state_lock = threading.Lock()
manual_step_opcode_offset_lock = threading.Lock()


class BreakpointState:
    """
    The current state of the stepping mechanism of the debugger.
    If is_stopped(), the code execution of the emulator thread is currently on hold
    in skytemple_ssb_debugger.controller.debugger.DebuggerController.hook__breaking_point.

    The object may optionally have a file state object, which describes more about the debugger state
    for this breakpoint (eg. which source file is breaked in, if breaked on macro call)

    These objects are not reusable. They can not transition back to the initial STOPPED state.
    """

    @synchronized(breakpoint_state_state_lock)
    def __init__(self, hanger_id: int, script_struct: ScriptRuntimeStruct):
        self.condition = threading.Condition()
        self.hanger_id = hanger_id
        self.script_struct = script_struct
        self._manual_step_opcode_offset: Optional[int] = None
        self._state: BreakpointStateType = BreakpointStateType.STOPPED
        self._file_state: Optional[BreakpointFileState] = None
        # Hook callbacks to call, when somewhere the break is released.
        self._release_hooks = []

    @synchronized(file_state_lock)
    def set_file_state(self, file_state: BreakpointFileState):
        self._file_state = file_state

    def get_file_state(self) -> Optional[BreakpointFileState]:
        return self._file_state

    @property
    @synchronized(manual_step_opcode_offset_lock)
    def manual_step_opcode_offset(self):
        return self._manual_step_opcode_offset

    @manual_step_opcode_offset.setter
    @synchronized(manual_step_opcode_offset_lock)
    def manual_step_opcode_offset(self, value):
        self._manual_step_opcode_offset = value

    # TO BE CALLED BY EMULATOR THREAD:

    def acquire(self):
        self.condition.acquire()

    def wait(self, timeout=None):
        return self.condition.wait(timeout)

    def release(self):
        self.condition.release()

    @property
    @synchronized(breakpoint_state_state_lock)
    def state(self):
        return self._state

    # TO BE CALLED BY MAIN THREAD:

    def add_release_hook(self, hook):
        return self._release_hooks.append(hook)

    def is_stopped(self):
        return self.state == BreakpointStateType.STOPPED

    def fail_hard(self):
        """Immediately abort debugging and don't break again it this tick."""
        self.state = BreakpointStateType.FAIL_HARD
        self._wakeup()

    def resume(self):
        """Resume normal code execution."""
        self.state = BreakpointStateType.RESUME
        self._wakeup()

    def step_into(self):
        """Step into the current call (if it's a call that creates a call stack), otherwise same as step over."""
        self.state = BreakpointStateType.STEP_INTO
        self._wakeup()
        self._wakeup()

    def step_over(self):
        """Step over the current call (remain in the current script file + skip debugging any calls to subroutines)."""
        self.state = BreakpointStateType.STEP_OVER
        self._wakeup()

    def step_out(self):
        """Step out of the current routine, if there's a call stack, otherwise same as resume."""
        self.state = BreakpointStateType.STEP_OUT
        self._wakeup()

    def step_next(self):
        """Break at the next opcode, even if it's for a different script target."""
        self.state = BreakpointStateType.STEP_NEXT
        self._wakeup()

    def step_manual(self, opcode_offset: int):
        """Transition to the STEP_MANUAL state and set the opcode to halt at."""
        self.state = BreakpointStateType.STEP_MANUAL
        self.manual_step_opcode_offset = opcode_offset
        self._wakeup()

    def transition(self, state_type: BreakpointStateType):
        """Transition to the specified state. Can not transition to STOPPED."""
        if state_type == BreakpointStateType.STOPPED:
            raise ValueError("Can not transition breakpoint state to stopped.")
        self.state = state_type
        self._wakeup()

    def _wakeup(self):
        self.condition.acquire()
        self.condition.notify_all()
        self.condition.release()
        for hook in self._release_hooks:
            hook(self)

    # INTERNAL ONLY, should not be set from outside.

    @state.setter
    @synchronized(breakpoint_state_state_lock)
    def state(self, value):
        self._state = value
