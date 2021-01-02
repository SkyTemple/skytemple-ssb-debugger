"""Object that manages the emulator thread."""
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
import asyncio
import logging
import sys
from asyncio import Future
from threading import Thread, current_thread, Lock, Condition
from typing import Optional

import nest_asyncio

from desmume import controls
from desmume.emulator import DeSmuME
from skytemple_ssb_debugger.model.settings import DebuggerSettingsStore
from skytemple_ssb_debugger.threadsafe import THREAD_DEBUG, synchronized

logger = logging.getLogger(__name__)
TICKS_PER_FRAME = 17
FRAMES_PER_SECOND = 60


start_lock = Lock()
display_buffer_lock = Lock()
fps_frame_count_lock = Lock()
boost_lock = Lock()
thread_stop_condition = Condition()


class EmulatorThread(Thread):
    _instance = None
    _joy_was_init = False
    _kbcfg = None
    _jscfg = None
    _emu: Optional[DeSmuME] = None
    
    daemon = True

    @classmethod
    def instance(cls) -> 'EmulatorThread':
        if cls._instance is None:
            return None
        return cls._instance

    @classmethod
    def end(cls):
        if cls._instance:
            with thread_stop_condition:
                cls._instance.stop()
                cls._instance = None
                thread_stop_condition.wait()

    def __init__(self, parent, override_dll = None):
        if self.__class__._instance is not None:
            raise RuntimeError("Only one instance of EmulatorThread can exist at a time. "
                               "Be sure to call end() on old instances.")
        self.__class__._instance = self
        Thread.__init__(self)
        self.loop: asyncio.AbstractEventLoop = None
        if self.__class__._emu is None:
            self.__class__._emu = DeSmuME(override_dll)
        self._thread_instance = None
        self.registered_main_loop = False
        self.parent = parent
        self._display_buffer = None

        self._fps_frame_count = 0
        self._fps_sec_start = 0
        self._fps = 0
        self._ticks_prev_frame = 0
        self._ticks_cur_frame = 0
        self._boost = False

    def assign(self, parent):
        self.parent = parent
        return self

    @property
    def emu(self):
        if THREAD_DEBUG and current_thread() != self._thread_instance:
            raise RuntimeError("The emulator may only be accessed from withing the emulator thread")
        return self.__class__._emu

    @classmethod
    def destroy_lib(cls):
        """Destroy the emulator library."""
        if cls._instance is not None:
            raise RuntimeError("Destroying the DeSmuME library is unsafe while an "
                               "EmulatorThread instance is still running.")
        if cls._emu is not None:
            cls._emu.destroy()
            cls._emu = None

    def start(self):
        start_lock.acquire()
        super().start()

    def run(self):
        self._thread_instance = current_thread()
        self._display_buffer = self.emu.display_buffer_as_rgbx()
        self.loop = asyncio.new_event_loop()
        nest_asyncio.apply(self.loop)
        asyncio.set_event_loop(self.loop)
        start_lock.release()
        try:
            self.loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass

        with thread_stop_condition:
            thread_stop_condition.notifyAll()

    def run_one_pending_task(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop.run_forever()

    def stop(self):
        start_lock.acquire()
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        start_lock.release()

    def register_main_loop(self):
        start_lock.acquire()
        if not self.registered_main_loop:
            self.loop.call_soon_threadsafe(self._emu_cycle)
            self.registered_main_loop = True
        start_lock.release()

    def run_task(self, coro) -> Future:
        """Runs an asynchronous task"""
        start_lock.acquire()
        retval = asyncio.run_coroutine_threadsafe(self.coro_runner(coro), self.loop)
        start_lock.release()
        return retval

    def load_controls(self, settings: DebuggerSettingsStore):
        """Loads the control configuration and returns it."""
        assert current_thread() == self._thread_instance

        if self.__class__._kbcfg is None:
            default_keyboard, default_joystick = controls.load_default_config()
            configured_keyboard = settings.get_emulator_keyboard_cfg()
            configured_joystick = settings.get_emulator_joystick_cfg()

            self.__class__._kbcfg, self.__class__._jscfg = (
                configured_keyboard if configured_keyboard is not None else default_keyboard,
                configured_joystick if configured_joystick is not None else default_joystick
            )

            if supports_joystick():
                for i, jskey in enumerate(self.__class__._jscfg):
                    self.emu.input.joy_set_key(i, jskey)

    def get_kbcfg(self):
        return self.__class__._kbcfg

    def get_jscfg(self):
        return self.__class__._jscfg

    def set_kbcfg(self, value):
        self.__class__._kbcfg = value

    def set_jscfg(self, value):
        self.__class__._jscfg = value
        
    def joy_init(self):
        if supports_joystick() and not self.__class__._joy_was_init:
            self.emu.input.joy_init()
            self.__class__._joy_was_init = True

    def _emu_cycle(self):
        if not self.emu:
            self.registered_main_loop = False
            return False

        if self.emu.is_running():
            with fps_frame_count_lock:
                self._fps_frame_count += 1

                if not self._fps_sec_start:
                    self._fps_sec_start = self.emu.get_ticks()
                if self.emu.get_ticks() - self._fps_sec_start >= 1000:
                    self._fps_sec_start = self.emu.get_ticks()
                    self._fps = self._fps_frame_count
                    self._fps_frame_count = 0

            self.emu.cycle(supports_joystick())

            self._ticks_cur_frame = self.emu.get_ticks()

            ticks_to_wait = 0
            with boost_lock:
                if not self._boost:
                    if self._ticks_cur_frame - self._ticks_prev_frame < TICKS_PER_FRAME:
                        while self._ticks_cur_frame - self._ticks_prev_frame < TICKS_PER_FRAME:
                            self._ticks_cur_frame = self.emu.get_ticks()

                    # TODO: This can be done better.
                    ticks_to_wait = (1 / FRAMES_PER_SECOND) - (self._ticks_cur_frame - self._ticks_prev_frame - TICKS_PER_FRAME + 2) / 1000

                    if ticks_to_wait < 0:
                        ticks_to_wait = 0

            self._ticks_prev_frame = self.emu.get_ticks()

            self.loop.call_later(ticks_to_wait, self._emu_cycle)

            with display_buffer_lock:
                with boost_lock:
                    if not self._boost or self._fps_frame_count % 60 == 0:
                        self._display_buffer = self.emu.display_buffer_as_rgbx()
            return True

        with display_buffer_lock:
            with boost_lock:
                if not self._boost or self._fps_frame_count % 60 == 0:
                    self._display_buffer = self.emu.display_buffer_as_rgbx()
        self.registered_main_loop = False
        return False

    @staticmethod
    async def coro_runner(coro):
        """Wrapper class to use ensure_future, to deal with uncaught exceptions..."""
        try:
            return await asyncio.ensure_future(coro)
        except BaseException as ex:
            logger.error(f"Uncaught EmulatorThread task exception.", exc_info=ex)

    @synchronized(display_buffer_lock)
    def display_buffer_as_rgbx(self):
        return self._display_buffer

    @property
    @synchronized(fps_frame_count_lock)
    def current_frame_id(self):
        """The ID of the current frame. Warning: Resets every 1000 frames back to 0."""
        return self._fps_frame_count

    @classmethod
    def has_instance(cls):
        return cls._instance is not None

    @synchronized(boost_lock)
    def set_boost(self, state):
        self._boost = state


def supports_joystick():
    """Joystick doesn't work under macOS"""
    return not sys.platform.startswith('darwin')
