"""
Модуль управления плейлистами для MaksIPTV Player
Версия 0.13.0

Содержит PlaylistManager для загрузки, парсинга и управления плейлистами.
Реализует принцип единственной ответственности (SRP).
"""

import os
import re
from PyQt5.QtWidgets import QStyle


class PlaylistManager:
    """Менеджер для управления плейлистами

    Отвечает за загрузку, парсинг и управление плейлистами.
    Реализует принцип единственной ответственности (SRP).
    """

    def __init__(self):
        self.channels = []
        self.categories = {"Все каналы": []}
        self.category_icons = {}
        self._init_category_icons()

    def _init_category_icons(self):
        """Инициализирует иконки для категорий"""
        # Будет инициализировано позже, когда будет доступен QStyle
        pass

    def set_category_icons(self, style):
        """Устанавливает иконки для категорий"""
        self.category_icons = {
            "Фильмы": style.standardIcon(QStyle.SP_FileDialogDetailedView),
            "Спорт": style.standardIcon(QStyle.SP_FileDialogDetailedView),
            "Новости": style.standardIcon(QStyle.SP_FileDialogDetailedView),
            "Музыка": style.standardIcon(QStyle.SP_MediaVolume),
            "Детские": style.standardIcon(QStyle.SP_FileDialogDetailedView),
            "Развлекательные": style.standardIcon(QStyle.SP_FileDialogDetailedView),
            "Познавательные": style.standardIcon(QStyle.SP_FileDialogDetailedView),
            "Все каналы": style.standardIcon(QStyle.SP_DirIcon),
            "Без категории": style.standardIcon(QStyle.SP_DirLinkIcon),
        }

    def parse_playlist(self, file_path):
        """Парсит плейлист из файла"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Плейлист {file_path} не найден!")

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            self.channels = []
            self.categories = {"Все каналы": []}

            channel = None
            current_group = "Без категории"

            for line in lines:
                line = line.strip()
                if not line or line.startswith('#EXTM3U'):
                    continue
                elif line.startswith('#EXTINF:'):
                    channel = self._parse_extinf_line(line)
                elif line.startswith('#EXTGRP:'):
                    current_group = self._parse_extgrp_line(line)
                    if channel and 'name' in channel:
                        channel['category'] = current_group
                        self._ensure_category_exists(current_group)
                elif line.startswith('#EXTVLCOPT:'):
                    if channel:
                        self._parse_vlc_option(line, channel)
                elif channel and 'name' in channel and not line.startswith('#'):
                    # Это URL канала
                    channel['url'] = line
                    self.channels.append(channel)

                    # Добавляем канал в соответствующую категорию
                    category = channel['category']
                    self.categories[category].append(channel)
                    self.categories["Все каналы"].append(channel)

                    channel = None
                    current_group = "Без категории"

        except Exception as e:
            raise Exception(f"Ошибка при чтении плейлиста: {str(e)}")

    def _parse_extinf_line(self, line):
        """Парсит строку #EXTINF"""
        # Извлекаем группу
        group_match = re.search(r'group-title="([^"]*)"', line)
        group_title = group_match.group(1).strip() if group_match else "Без категории"
        if not group_title:
            group_title = "Без категории"

        # Извлекаем tvg-id
        tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
        tvg_id = tvg_id_match.group(1).strip() if tvg_id_match else ""

        # Извлекаем tvg-logo
        tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
        tvg_logo = tvg_logo_match.group(1).strip() if tvg_logo_match else ""

        # Извлекаем имя канала
        parts = line.split(',', 1)
        if len(parts) > 1:
            channel = {
                'name': parts[1].strip(),
                'options': {},
                'category': group_title,
                'tvg_id': tvg_id,
                'tvg_logo': tvg_logo
            }
            self._ensure_category_exists(group_title)
            return channel
        return None

    def _parse_extgrp_line(self, line):
        """Парсит строку #EXTGRP"""
        group = line[len('#EXTGRP:'):].strip()
        return group if group else "Без категории"

    def _parse_vlc_option(self, line, channel):
        """Парсит опции VLC"""
        opt = line[len('#EXTVLCOPT:'):].strip()
        if 'http-user-agent=' in opt:
            user_agent = opt.split('http-user-agent=')[1]
            channel['options']['user-agent'] = user_agent

    def _ensure_category_exists(self, category):
        """Убеждается, что категория существует"""
        if category not in self.categories:
            self.categories[category] = []

    def get_channels(self):
        """Возвращает список каналов"""
        return self.channels

    def get_categories(self):
        """Возвращает словарь категорий"""
        return self.categories

    def get_channel_by_index(self, index):
        """Возвращает канал по индексу"""
        if 0 <= index < len(self.channels):
            return self.channels[index]
        return None

    def sort_channels_alphabetically(self):
        """Сортирует каналы по алфавиту"""
        for category in self.categories:
            self.categories[category].sort(key=lambda x: x['name'])
        self.channels.sort(key=lambda x: x['name'])
