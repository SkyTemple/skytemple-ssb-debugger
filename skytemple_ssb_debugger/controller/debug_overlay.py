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
from typing import Iterable

import cairo

from desmume.emulator import DeSmuME
from skytemple_ssb_debugger.controller.debugger import DebuggerController

ALPHA_T = 0.7
COLOR_ACTOR = (255, 0, 255, ALPHA_T)
COLOR_OBJECTS = (255, 160, 0, ALPHA_T)
COLOR_PERFORMER = (0, 255, 255, ALPHA_T)
COLOR_EVENTS = (0, 0, 255, 100)
COLOR_BLACK = (0, 0, 0, ALPHA_T)
COLOR_POS_MARKERS = (0, 255, 0, ALPHA_T)


class DebugOverlayController:
    def __init__(self, emu: DeSmuME, debugger: DebuggerController):
        self.emu = emu
        self.debugger = debugger

        self.enabled = False
        self.visible = False

    def toggle(self, state):
        self.enabled = state

    def draw(self, ctx: cairo.Context, display_id: int):
        # TODO: Support other display drawing.
        if display_id == 1 and self.enabled and self.debugger and self.debugger.ground_engine_state.running:
            ges = self.debugger.ground_engine_state
            for actor in not_none(ges.actors):
                ctx.set_source_rgba(*COLOR_ACTOR)
                bbox = actor.get_bounding_box_camera(ges.map)
                ctx.rectangle(
                    bbox[0], bbox[1],
                    bbox[2] - bbox[0], bbox[3] - bbox[1]
                )
                ctx.fill()
            for object in not_none(ges.objects):
                ctx.set_source_rgba(*COLOR_OBJECTS)
                bbox = object.get_bounding_box_camera(ges.map)
                ctx.rectangle(
                    bbox[0], bbox[1],
                    bbox[2] - bbox[0], bbox[3] - bbox[1]
                )
                ctx.fill()
            for performer in not_none(ges.performers):
                ctx.set_source_rgba(*COLOR_PERFORMER)
                bbox = performer.get_bounding_box_camera(ges.map)
                ctx.rectangle(
                    bbox[0], bbox[1],
                    bbox[2] - bbox[0], bbox[3] - bbox[1]
                )
                ctx.fill()
            for event in not_none(ges.events):
                ctx.set_source_rgba(*COLOR_EVENTS)
                bbox = event.get_bounding_box_camera(ges.map)
                ctx.rectangle(
                    bbox[0], bbox[1],
                    bbox[2] - bbox[0], bbox[3] - bbox[1]
                )
                ctx.fill()
            # TODO: Position markers


def not_none(it: Iterable):
    for i in it:
        if i is not None:
            yield i