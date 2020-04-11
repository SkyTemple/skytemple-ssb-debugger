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
import math

import cairo
from gi.repository import Gdk


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
