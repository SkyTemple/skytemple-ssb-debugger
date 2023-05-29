#  Copyright 2020-2023 Capypara and the SkyTemple Contributors
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
from __future__ import annotations
from math import radians
from typing import Optional, Callable

import cairo
from gi.repository import Gtk, GLib
from skytemple_ssb_emulator import SCREEN_PIXEL_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT, emulator_display_buffer_as_rgbx

FRAMES_PER_SECOND = 60


class AsyncSoftwareRenderer:
    def __init__(self, top_screen: Gtk.Widget, bottom_screen: Gtk.Widget,
                 after_render_hook: Optional[Callable[[cairo.Context, int], None]] = None):
        self._boost = False
        self._upper_image: Optional[cairo.ImageSurface] = None
        self._lower_image: Optional[cairo.ImageSurface] = None
        self._after_render_hook = after_render_hook
        self.top_screen = top_screen
        self.bottom_screen = bottom_screen
        self._screen_rotation_degrees = 0
        self._scale = 1.0
        self.decode_screen()

    def screen(self, base_w, base_h, ctx: cairo.Context, display_id: int):
        if self._upper_image is not None and self._lower_image is not None:
            if display_id == 0:
                self.decode_screen()

            ctx.translate(base_w * self._scale / 2, base_h * self._scale / 2)
            ctx.rotate(-radians(self._screen_rotation_degrees))
            if self._screen_rotation_degrees == 90 or self._screen_rotation_degrees == 270:
                ctx.translate(-base_h * self._scale / 2, -base_w * self._scale / 2)
            else:
                ctx.translate(-base_w * self._scale / 2, -base_h * self._scale / 2)
            ctx.scale(self._scale, self._scale)
            if display_id == 0:
                ctx.set_source_surface(self._upper_image)
            else:
                ctx.set_source_surface(self._lower_image)
            ctx.get_source().set_filter(cairo.Filter.NEAREST)
            ctx.paint()

            if self._after_render_hook:
                self._after_render_hook(ctx, display_id)

    def decode_screen(self):
        gpu_framebuffer = memoryview(bytearray(emulator_display_buffer_as_rgbx()))
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

    def reshape(self, draw: Gtk.DrawingArea, display_id: int):
        pass

    def set_boost(self, state):
        self._boost = state

    def set_scale(self, value):
        self._scale = value

    def get_scale(self):
        return self._scale

    def get_screen_rotation(self):
        return self._screen_rotation_degrees

    def set_screen_rotation(self, value):
        self._screen_rotation_degrees = value
