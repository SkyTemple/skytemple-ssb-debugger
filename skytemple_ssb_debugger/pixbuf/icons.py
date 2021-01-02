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
import math

import cairo
from gi.repository import Gdk

from skytemple_ssb_debugger.controller.debug_overlay import COLOR_ACTOR, COLOR_OBJECTS, COLOR_PERFORMER


def create_breakpoint_icon():
    w = h = 24
    circle_radius = 8
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surface)

    cr.arc(w / 2, h / 2, circle_radius, 0, 2 * math.pi)

    cr.set_source_rgb(1.0, 0, 0)
    cr.fill()

    pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, w, h)
    return pixbuf


def create_breaked_line_icon(type_id, slot_id, icon_actor, icon_object, icon_performer, icon_gs):
    h = 12
    w = h * 3
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surface)

    _common_line_icons(cr, type_id, slot_id, icon_actor, icon_object, icon_performer, icon_gs)

    # Play Icon
    cr.move_to(12 * 2, 0)
    cr.line_to(w, h/2)
    cr.line_to(12 * 2, h)
    cr.close_path()
    cr.set_source_rgb(1.0, 0, 0)
    cr.fill_preserve()

    pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, w, h)
    return pixbuf


def create_execution_line_icon(type_id, slot_id, icon_actor, icon_object, icon_performer, icon_gs):
    h = 12
    w = h * 3
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surface)

    _common_line_icons(cr, type_id, slot_id, icon_actor, icon_object, icon_performer, icon_gs)

    # Play Icon
    cr.move_to(12 * 2, 0)
    cr.line_to(w, h/2)
    cr.line_to(12 * 2, h)
    cr.close_path()
    cr.set_source_rgb(129 / 255, 105 / 255, 43 / 255)
    cr.fill_preserve()

    pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, w, h)
    return pixbuf


def _common_line_icons(cr, type_id, slot_id, icon_actor, icon_object, icon_performer, icon_gs):
    # Slot Type
    cr.translate(10, -1)
    if type_id == 3:
        Gdk.cairo_set_source_pixbuf(cr, icon_actor, 0, 0)
        cr.paint()
        cr.set_source_rgb(*COLOR_ACTOR[:3])
    elif type_id == 4:
        Gdk.cairo_set_source_pixbuf(cr, icon_object, 0, 0)
        cr.paint()
        cr.set_source_rgb(*COLOR_OBJECTS[:3])
    elif type_id == 5:
        Gdk.cairo_set_source_pixbuf(cr, icon_performer, 0, 0)
        cr.paint()
        cr.set_source_rgb(*COLOR_PERFORMER[:3])
    else:
        Gdk.cairo_set_source_pixbuf(cr, icon_gs, 0, 0)
        cr.paint()
        cr.set_source_rgb(255, 255, 255)
    cr.translate(-10, 1)

    # Slot ID
    if slot_id > -1 and type_id > 1:
        cr.move_to(0, 11)
        cr.select_font_face("cairo:monospace", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(12)
        cr.show_text(str(slot_id))
