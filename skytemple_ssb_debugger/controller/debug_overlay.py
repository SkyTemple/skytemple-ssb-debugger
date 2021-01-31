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
from threading import Lock
from typing import Iterable

import cairo

from skytemple_files.script.ssa_sse_sss.position import TILE_SIZE
from skytemple_ssb_debugger.controller.debugger import DebuggerController
from skytemple_ssb_debugger.emulator_thread import FRAMES_PER_SECOND
from skytemple_ssb_debugger.threadsafe import synchronized, threadsafe_emu_nonblocking_coro
from skytemple_files.common.i18n_util import f, _

ALPHA_T = 0.7
COLOR_ACTOR = (1.0, 0, 1.0, ALPHA_T)
COLOR_OBJECTS = (1.0, 0.627, 0, ALPHA_T)
COLOR_PERFORMER = (0, 1.0, 1.0, ALPHA_T)
COLOR_EVENTS = (0, 0, 1.0, 0.4)
COLOR_BLACK = (0, 0, 0, ALPHA_T)
COLOR_POS_MARKERS = (0, 1.0, 0, ALPHA_T)
REDRAW_DELAY = 2


debug_overlay_lock = Lock()


class DebugOverlayController:
    def __init__(self, debugger: DebuggerController):
        self.debugger = debugger

        self.enabled = False
        self.visible = False

        self._refresh_cache = True
        self._cache_running = False
        self._cache_redrawing_registered = False
        self._actor_bbox_cache = []
        self._object_bbox_cache = []
        self._perf_bbox_cache = []
        self._event_bbox_cache = []
        self._camera_pos_cache = (0, 0)
        self._boost = False

    def toggle(self, state):
        self.enabled = state

    @synchronized(debug_overlay_lock)
    def draw(self, ctx: cairo.Context, display_id: int):
        if self._boost:
            self._draw_boost(ctx, display_id)
            return
        # TODO: Support other display drawing.
        if display_id == 1 and self.enabled and self.debugger:
            if self._refresh_cache and not self._cache_redrawing_registered:
                self._cache_redrawing_registered = True
                threadsafe_emu_nonblocking_coro(self.debugger.emu_thread, self._update_cache())

            if self._cache_running:
                # Draw
                for bbox in self._actor_bbox_cache:
                    ctx.set_source_rgba(*COLOR_ACTOR)
                    ctx.rectangle(
                        bbox[0], bbox[1],
                        bbox[2] - bbox[0], bbox[3] - bbox[1]
                    )
                    ctx.fill()
                for bbox in self._object_bbox_cache:
                    ctx.set_source_rgba(*COLOR_OBJECTS)
                    ctx.rectangle(
                        bbox[0], bbox[1],
                        bbox[2] - bbox[0], bbox[3] - bbox[1]
                    )
                    ctx.fill()
                for bbox in self._perf_bbox_cache:
                    ctx.set_source_rgba(*COLOR_PERFORMER)
                    ctx.rectangle(
                        bbox[0], bbox[1],
                        bbox[2] - bbox[0], bbox[3] - bbox[1]
                    )
                    ctx.fill()
                for bbox in self._event_bbox_cache:
                    ctx.set_source_rgba(*COLOR_EVENTS)
                    ctx.rectangle(
                        bbox[0], bbox[1],
                        bbox[2] - bbox[0], bbox[3] - bbox[1]
                    )
                    ctx.fill()

                if self.debugger.ground_engine_state:
                    ground_state = self.debugger.ground_engine_state
                    for ssb in ground_state.loaded_ssb_files:
                        if ssb is not None:
                            for mark in ground_state.ssb_file_manager.get(ssb.file_name).position_markers:
                                x_absolute = (mark.x_with_offset * TILE_SIZE) - self._camera_pos_cache[0]
                                y_absolute = (mark.y_with_offset * TILE_SIZE) - self._camera_pos_cache[1]
                                ctx.set_source_rgba(*COLOR_POS_MARKERS)
                                ctx.rectangle(
                                    # They are centered.
                                    x_absolute - 4, y_absolute - 4,
                                    TILE_SIZE, TILE_SIZE
                                )
                                ctx.fill_preserve()
                                ctx.set_source_rgb(0, 0, 0)
                                ctx.set_line_width(1)
                                ctx.stroke()
                                ctx.set_source_rgba(*COLOR_POS_MARKERS)
                                ctx.move_to(x_absolute, y_absolute + 18)
                                ctx.select_font_face("cairo:monospace", cairo.FONT_SLANT_NORMAL,
                                                    cairo.FONT_WEIGHT_NORMAL)
                                ctx.set_font_size(8)
                                ctx.text_path(mark.name)
                                ctx.fill_preserve()
                                ctx.set_source_rgb(0, 0, 0)
                                ctx.set_line_width(0.3)
                                ctx.stroke()

    def break_pulled(self):
        """The debugger is stopped, the emulator is frozen."""
        self._refresh_cache = False

    def break_released(self):
        """The debugger is no longer stopped."""
        self._refresh_cache = True

    async def _update_cache(self):
        # Refresh the cache
        with debug_overlay_lock:
            ges = self.debugger.ground_engine_state
            if ges:
                self._cache_running = ges.running
                if self._cache_running:
                    self._actor_bbox_cache = []
                    self._object_bbox_cache = []
                    self._perf_bbox_cache = []
                    self._event_bbox_cache = []
                    for actor in not_none(ges.actors):
                        self._actor_bbox_cache.append(actor.get_bounding_box_camera(ges.map))
                    for object in not_none(ges.objects):
                        self._object_bbox_cache.append(object.get_bounding_box_camera(ges.map))
                    for performer in not_none(ges.performers):
                        self._perf_bbox_cache.append(performer.get_bounding_box_camera(ges.map))
                    for event in not_none(ges.events):
                        self._event_bbox_cache.append(event.get_bounding_box_camera(ges.map))
                    self._camera_pos_cache = (ges.map.camera_x_pos, ges.map.camera_y_pos)

        if self._refresh_cache and not self._boost:
            await asyncio.sleep(1 / FRAMES_PER_SECOND * REDRAW_DELAY, loop=self.debugger.emu_thread.loop)
            threadsafe_emu_nonblocking_coro(self.debugger.emu_thread, self._update_cache())
        else:
            self._cache_redrawing_registered = False

    def set_boost(self, state):
        self._boost = state

    def _draw_boost(self, ctx: cairo.Context, display_id: int):
        if display_id == 0:
            ctx.set_source_rgb(1.0, 0, 0)
            ctx.move_to(10, 20)
            ctx.set_font_size(20)
            ctx.show_text(_("BOOST"))  # TRANSLATORS: Shown in enulator when boosting / fast-forward
            ctx.set_font_size(12)
            ctx.move_to(10, 30)
            ctx.show_text(_("Debugging disabled."))


def not_none(it: Iterable):
    for i in it:
        if i is not None:
            yield i
