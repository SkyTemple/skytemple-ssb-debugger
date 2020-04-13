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
import threading
from enum import Enum

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


breakpoint_state_state_lock = threading.Lock()


class BreakpointState:
    """
    The current state of the stepping mechanism of the debugger.
    If is_stopped(), the code execution of the emulator thread is currently on hold
    in skytemple_ssb_debugger.controller.debugger.DebuggerController.hook__breaking_point.

    These objects are not reusable. They can not transition back to the initial STOPPED state.
    """

    @synchronized(breakpoint_state_state_lock)
    def __init__(self, hanger_id: int):
        self.condition = threading.Condition()
        self.hanger_id = hanger_id
        self._state: BreakpointStateType = BreakpointStateType.STOPPED
        # Hook callbacks to call, when somewhere the break is released.
        self._release_hooks = []

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
