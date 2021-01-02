"""
Utility functions for easier thread-safe asynchronous / synchronous calling.
This module happens, when you forget that you might need multiple threads before starting a project...
"""
import functools
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
import inspect
import sys
import traceback
from threading import current_thread
from typing import Callable

from gi.repository import GLib

# If true, we check which threads call the threadsafe methods. They can only be called
# by the other respective other thread, otherwise there will be deadlocks or Exceptions.
THREAD_DEBUG = False


async def cb_coroutine_wrapper(cb):
    return cb()


def threadsafe_gtk_nonblocking(cb: Callable) -> None:
    """Non-blocking call on the GTK thread. Must be called from emulator thread. No return value available."""
    if THREAD_DEBUG:
        from skytemple_ssb_debugger.emulator_thread import EmulatorThread
        if current_thread() != EmulatorThread.instance()._thread_instance:
            raise RuntimeError("Wrong threadsafe_gtk_nonblocking call.")

    def resolve_callback():
        cb()
        return False

    GLib.idle_add(resolve_callback)


def threadsafe_now_or_gtk_nonblocking(cb: Callable) -> None:
    """If on GTK thread: Run now blocking. Else delegate to threadsafe_gtk_nonblocking."""
    from skytemple_ssb_debugger.emulator_thread import EmulatorThread
    if current_thread() != EmulatorThread.instance()._thread_instance:
        cb()
    else:
        threadsafe_gtk_nonblocking(cb)


def threadsafe_emu(emu_thread, cb: Callable):
    """
    Blocking call on the emulator thread. If run from emulator thread, cb is just executed.
    The return value is the return value of cb.
    """
    if current_thread() == emu_thread._thread_instance:
        return cb()

    return emu_thread.run_task(cb_coroutine_wrapper(cb)).result()


def threadsafe_emu_nonblocking(emu_thread, cb) -> None:
    """Non-blocking call on the emulator thread. Must be called from GTK thread. No return value available."""
    if THREAD_DEBUG:
        if current_thread() == emu_thread._thread_instance:
            raise RuntimeError("Wrong threadsafe_emu_nonblocking call.")

    emu_thread.run_task(cb_coroutine_wrapper(cb))


def threadsafe_emu_nonblocking_coro(emu_thread, coro) -> None:
    """Non-blocking call on the emulator thread, coroutine version.
    Must be called from GTK thread. No return value available."""
    if THREAD_DEBUG:
        if current_thread() == emu_thread._thread_instance:
            raise RuntimeError("Wrong threadsafe_emu_nonblocking_coro call.")

    emu_thread.run_task(coro)


def synchronized(lock):
    """ Synchronization decorator """
    def wrap(f):
        @functools.wraps(f)
        def newFunction(*args, **kw):
            if THREAD_DEBUG:
                print(f'{current_thread()}: Trying to acquire {lock} ({f})')
                traceback.print_stack(file=sys.stdout)
            with lock:
                retval = f(*args, **kw)
            if THREAD_DEBUG:
                print(f'{current_thread()}: Done with {lock}')
            return retval
        return newFunction
    return wrap


def synchronized_now(lock):
    """
    Special Synchronization decorator.
    If the emulator threads tries to enter a function decorated like this and the lock is taken,
    it will immediately process pending tasks until the block is no longer locked.
    """
    from skytemple_ssb_debugger.emulator_thread import EmulatorThread

    def wrap(f):
        @functools.wraps(f)
        def newFunction(*args, **kw):
            if THREAD_DEBUG:
                print(f'{current_thread()}: Trying to acquire {lock} ({f})')
                traceback.print_stack(file=sys.stdout)
            if current_thread() == EmulatorThread.instance()._thread_instance:
                while not lock.acquire(False):
                    EmulatorThread.instance().run_one_pending_task()
                retval = f(*args, **kw)
                lock.release()
            else:
                with lock:
                    retval = f(*args, **kw)
            if THREAD_DEBUG:
                print(f'{current_thread()}: Done with {lock}')
            return retval
        return newFunction
    return wrap


def wrap_threadsafe_emu():
    """Wrap the entire method call in a threadsafe_emu call."""
    from .emulator_thread import EmulatorThread
    def decorator(f):

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if current_thread() == EmulatorThread.instance()._thread_instance:
                return f(*args, **kwargs)
            return threadsafe_emu(EmulatorThread.instance(), lambda: f(*args, **kwargs))

        return wrapper
    return decorator


def generate_emulator_proxy(emu_thread, obj_to_generate_for):
    """Generates a proxy object that proxies all it's methods to threadsafe_emu."""
    fields = {}

    def wrapper(original_method, *args, **kwargs):
        return threadsafe_emu(emu_thread, lambda: original_method(*args, **kwargs))

    for method in [attr for attr in dir(obj_to_generate_for) if inspect.ismethod(getattr(obj_to_generate_for, attr))]:
        fields[method] = functools.partial(wrapper, getattr(obj_to_generate_for, method))

    fields['__init__'] = lambda self: None

    return type(obj_to_generate_for.__class__.__name__ + 'Proxy', (obj_to_generate_for.__class__, ), fields)()
