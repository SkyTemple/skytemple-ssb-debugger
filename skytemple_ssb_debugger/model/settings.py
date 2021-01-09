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
import configparser
import logging
import os
import threading
from typing import Optional, Tuple, List

from desmume.controls import key_names
from desmume.emulator import Language
from skytemple_files.common.project_file_manager import ProjectFileManager
from skytemple_files.common.util import open_utf8
from skytemple_ssb_debugger.threadsafe import synchronized

settings_lock = threading.Lock()
CONFIG_DIR_NAME = 'debugger'
CONFIG_FILE_NAME = 'config.ini'

SECT_GENERAL = 'General'
SECT_WINDOW = 'Window'
SECT_KEYS = 'KEYS'
SECT_JOYKEYS = 'JOYKEYS'

KEY_STYLE_SCHEME = 'style_scheme'
KEY_ASSISTANT_SHOWN = 'assistant_shown'
KEY_EMULATOR_LANG = 'emulator_language'
KEY_SPELLCHECK = 'spellcheck_enabled'

KEY_WINDOW_SIZE_X = 'width'
KEY_WINDOW_SIZE_Y = 'height'
KEY_WINDOW_POS_X = 'pos_x'
KEY_WINDOW_POS_Y = 'pos_y'

TEXTBOX_TOOL_URL = 'http://textbox.skytemple.org/?ws'
logger = logging.getLogger(__name__)


class DebuggerSettingsStore:
    def __init__(self):
        self.config_dir = os.path.join(ProjectFileManager.shared_config_dir(), CONFIG_DIR_NAME)
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, CONFIG_FILE_NAME)
        self.loaded_config = configparser.ConfigParser()
        if os.path.exists(self.config_file):
            try:
                with open_utf8(self.config_file, 'r') as f:
                    self.loaded_config.read_file(f)
            except BaseException as err:
                logger.error("Error reading config, falling back to default.", exc_info=err)

    @synchronized(settings_lock)
    def get_style_scheme(self) -> Optional[str]:
        if SECT_GENERAL in self.loaded_config:
            if KEY_STYLE_SCHEME in self.loaded_config[SECT_GENERAL]:
                return self.loaded_config[SECT_GENERAL][KEY_STYLE_SCHEME]
        return None

    @synchronized(settings_lock)
    def set_style_scheme(self, scheme_id: str):
        if SECT_GENERAL not in self.loaded_config:
            self.loaded_config[SECT_GENERAL] = {}
        self.loaded_config[SECT_GENERAL][KEY_STYLE_SCHEME] = scheme_id
        self._save()

    @synchronized(settings_lock)
    def get_assistant_shown(self) -> bool:
        if SECT_GENERAL in self.loaded_config:
            if KEY_ASSISTANT_SHOWN in self.loaded_config[SECT_GENERAL]:
                return int(self.loaded_config[SECT_GENERAL][KEY_ASSISTANT_SHOWN]) > 0
        return False

    @synchronized(settings_lock)
    def set_assistant_shown(self, value: bool):
        if SECT_GENERAL not in self.loaded_config:
            self.loaded_config[SECT_GENERAL] = {}
        self.loaded_config[SECT_GENERAL][KEY_ASSISTANT_SHOWN] = '1' if value else '0'
        self._save()

    @synchronized(settings_lock)
    def get_window_size(self) -> Optional[Tuple[int, int]]:
        if SECT_WINDOW in self.loaded_config:
            if KEY_WINDOW_SIZE_X in self.loaded_config[SECT_WINDOW] and KEY_WINDOW_SIZE_Y in self.loaded_config[SECT_WINDOW]:
                return int(self.loaded_config[SECT_WINDOW][KEY_WINDOW_SIZE_X]), int(self.loaded_config[SECT_WINDOW][KEY_WINDOW_SIZE_Y])
        return None

    @synchronized(settings_lock)
    def set_window_size(self, dim: Tuple[int, int]):
        if SECT_WINDOW not in self.loaded_config:
            self.loaded_config[SECT_WINDOW] = {}
        self.loaded_config[SECT_WINDOW][KEY_WINDOW_SIZE_X] = str(dim[0])
        self.loaded_config[SECT_WINDOW][KEY_WINDOW_SIZE_Y] = str(dim[1])
        self._save()

    @synchronized(settings_lock)
    def get_window_position(self) -> Optional[Tuple[int, int]]:
        if SECT_WINDOW in self.loaded_config:
            if KEY_WINDOW_POS_X in self.loaded_config[SECT_WINDOW] and KEY_WINDOW_POS_Y in self.loaded_config[SECT_WINDOW]:
                return int(self.loaded_config[SECT_WINDOW][KEY_WINDOW_POS_X]), int(self.loaded_config[SECT_WINDOW][KEY_WINDOW_POS_Y])
        return None

    @synchronized(settings_lock)
    def set_window_position(self, pos: Tuple[int, int]):
        if SECT_WINDOW not in self.loaded_config:
            self.loaded_config[SECT_WINDOW] = {}
        self.loaded_config[SECT_WINDOW][KEY_WINDOW_POS_X] = str(pos[0])
        self.loaded_config[SECT_WINDOW][KEY_WINDOW_POS_Y] = str(pos[1])
        self._save()

    @synchronized(settings_lock)
    def get_emulator_keyboard_cfg(self) -> Optional[List[int]]:
        if SECT_KEYS in self.loaded_config:
            cfg = []
            for key_name in key_names:
                cfg.append(int(self.loaded_config[SECT_KEYS][key_name]))
            return cfg
        return None

    @synchronized(settings_lock)
    def set_emulator_keyboard_cfg(self, keys: List[int]):
        if SECT_KEYS not in self.loaded_config:
            self.loaded_config[SECT_KEYS] = {}
        for key_name, key_value in zip(key_names, keys):
            self.loaded_config[SECT_KEYS][key_name] = str(key_value)
        self._save()

    @synchronized(settings_lock)
    def get_emulator_joystick_cfg(self):
        if SECT_JOYKEYS in self.loaded_config:
            cfg = []
            for key_name in key_names:
                cfg.append(int(self.loaded_config[SECT_JOYKEYS][key_name]))
            return cfg
        return None

    @synchronized(settings_lock)
    def set_emulator_joystick_cfg(self, keys: List[int]):
        if SECT_JOYKEYS not in self.loaded_config:
            self.loaded_config[SECT_JOYKEYS] = {}
        for key_name, key_value in zip(key_names, keys):
            self.loaded_config[SECT_JOYKEYS][key_name] = str(key_value)
        self._save()

    @synchronized(settings_lock)
    def get_emulator_language(self) -> Optional[Language]:
        if SECT_GENERAL in self.loaded_config:
            if KEY_EMULATOR_LANG in self.loaded_config[SECT_GENERAL]:
                return Language(int(self.loaded_config[SECT_GENERAL][KEY_EMULATOR_LANG]))
        return None

    @synchronized(settings_lock)
    def set_emulator_language(self, lang: Language):
        if SECT_GENERAL not in self.loaded_config:
            self.loaded_config[SECT_GENERAL] = {}
        self.loaded_config[SECT_GENERAL][KEY_EMULATOR_LANG] = str(lang.value)
        self._save()

    @synchronized(settings_lock)
    def get_spellcheck_enabled(self) -> bool:
        if SECT_GENERAL in self.loaded_config:
            if KEY_SPELLCHECK in self.loaded_config[SECT_GENERAL]:
                return int(self.loaded_config[SECT_GENERAL][KEY_SPELLCHECK]) > 0
        return False

    @synchronized(settings_lock)
    def set_spellcheck_enabled(self, value: bool):
        if SECT_GENERAL not in self.loaded_config:
            self.loaded_config[SECT_GENERAL] = {}
        self.loaded_config[SECT_GENERAL][KEY_SPELLCHECK] = str(int(value))
        self._save()

    def _save(self):
        with open_utf8(self.config_file, 'w') as f:
            self.loaded_config.write(f)
