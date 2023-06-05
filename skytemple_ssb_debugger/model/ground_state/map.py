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

from typing import Optional

from range_typed_integers import u32
from skytemple_files.common.util import read_u32

from skytemple_ssb_debugger.model.ground_state import AbstractEntity


class Map(AbstractEntity):
    @property
    def _block_size(self):
        # This is not the actual size, increase this if we need to read more!
        return u32(0x208)

    @property
    def _validity_offset(self) -> Optional[u32]:
        return None

    @property
    def camera_x_pos(self):
        """Returns the center position of the camera"""
        return read_u32(self.buffer, 0x200)

    @property
    def camera_y_pos(self):
        """Returns the center position of the camera"""
        return read_u32(self.buffer, 0x204)
