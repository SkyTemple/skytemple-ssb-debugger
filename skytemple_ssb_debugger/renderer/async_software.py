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
from threading import Lock
from typing import Callable

import cairo
from gi.repository import Gtk, GLib

from desmume.emulator import SCREEN_PIXEL_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT
from desmume.frontend.gtk_drawing_impl.software import SoftwareRenderer
from skytemple_ssb_debugger.emulator_thread import EmulatorThread, FRAMES_PER_SECOND
from skytemple_ssb_debugger.threadsafe import synchronized

image_lock = Lock()


class AsyncSoftwareRenderer(SoftwareRenderer):
    """Asynchronous, thread-safe implementation of the Software renderer."""

    @synchronized(image_lock)
    def __init__(self, emu_thread: EmulatorThread,
                 top_screen: Gtk.Widget, bottom_screen: Gtk.Widget,
                 after_render_hook: Callable[[cairo.Context, int], None] = None):
        self._boost = False
        self._upper_image = None
        self._lower_image = None
        self.emu_thread = emu_thread
        self._after_render_hook = after_render_hook
        self.top_screen = top_screen
        self.bottom_screen = bottom_screen
        super().__init__(None, after_render_hook)

    @synchronized(image_lock)
    def screen(self, base_w, base_h, ctx: cairo.Context, display_id: int):
        if self._upper_image is not None and self._lower_image is not None:
            super().screen(base_w, base_h, ctx, display_id)

    def decode_screen(self):
        gpu_framebuffer = self.emu_thread.display_buffer_as_rgbx()
        self._upper_image = cairo.ImageSurface.create_for_data(
            gpu_framebuffer[:SCREEN_PIXEL_SIZE*4], cairo.FORMAT_RGB24, SCREEN_WIDTH, SCREEN_HEIGHT
        )

        self._lower_image = cairo.ImageSurface.create_for_data(
            gpu_framebuffer[SCREEN_PIXEL_SIZE*4:], cairo.FORMAT_RGB24, SCREEN_WIDTH, SCREEN_HEIGHT
        )

    def start(self):
        self.top_screen.queue_draw()
        self.bottom_screen.queue_draw()
        GLib.timeout_add(int(1000 / FRAMES_PER_SECOND), self._tick)

    def _tick(self):
        if self.top_screen is None or self.bottom_screen is None:
            return False
        self.top_screen.queue_draw()
        self.bottom_screen.queue_draw()
        return True

    def set_boost(self, state):
        self._boost = state
