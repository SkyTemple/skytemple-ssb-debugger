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
from typing import Tuple, Optional, Iterable

from gi.repository import GObject
from gi.repository import GtkSource, Gtk

from skytemple_ssb_debugger.model.completion.util import common_do_match, common_do_populate
from skytemple_files.common.i18n_util import f, _

ALL_STATEMENTS = ['return', 'end', 'hold', 'if', 'elseif', 'else', 'with', 'actor', 'object', 'performer', 'jump',
                  'for', 'while', 'forever', 'break', 'break_loop', 'continue', 'case',
                  'default', 'clear', 'reset', 'init']


class GtkSourceCompletionExplorerScriptStatements(GObject.Object, GtkSource.CompletionProvider):
    def do_get_name(self) -> str:
        return _("Statements")

    def do_get_priority(self) -> int:
        return 0

    def do_activate_proposal(self, proposal: GtkSource.CompletionProposal, textiter: Gtk.TextIter) -> bool:
        return False

    def do_get_activation(self) -> GtkSource.CompletionActivation:
        return GtkSource.CompletionActivation.INTERACTIVE | GtkSource.CompletionActivation.USER_REQUESTED

    # def do_get_info_widget(self, proposal: GtkSource.CompletionProposal) -> Gtk.Widget:
    #     pass

    # def do_update_info(self, proposal: GtkSource.CompletionProposal, info: GtkSource.CompletionInfo):
    #     pass

    def do_get_interactive_delay(self) -> int:
        return -1

    def do_get_gicon(self):
        return None

    def do_get_icon(self):
        return None

    def do_get_icon_name(self):
        return None

    def do_get_start_iter(self, context: GtkSource.CompletionContext, proposal: GtkSource.CompletionProposal) -> Tuple[bool, Optional[Gtk.TextIter]]:
        return False, None

    def do_match(self, context: GtkSource.CompletionContext) -> bool:
        return common_do_match(self._filter, self._all, context)

    def do_populate(self, context: GtkSource.CompletionContext):
        return common_do_populate(self, self._filter, self._all, context)

    def _all(self) -> Iterable[GtkSource.CompletionProposal]:
        return [self._build_item(s) for s in ALL_STATEMENTS]

    def _filter(self, cond: str) -> Iterable[GtkSource.CompletionProposal]:
        return [self._build_item(s) for s in ALL_STATEMENTS if s.startswith(cond)]

    def _build_item(self, string) -> GtkSource.CompletionItem:
        item: GtkSource.CompletionItem = GtkSource.CompletionItem.new2()
        item.set_text(string)
        item.set_label(string)
        return item
