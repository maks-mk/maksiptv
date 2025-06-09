"""
Модуль управления конфигурацией для MaksIPTV Player
Версия 0.13.0

Содержит ConfigManager для управления настройками приложения.
Реализует принцип единственной ответственности (SRP).
"""

import os
import json
import logging
from typing import Any
from threading import Lock
from PyQt5.QtCore import Qt
from constants import DEFAULT_WINDOW_SIZE, DEFAULT_WINDOW_POSITION, DEFAULT_VOLUME


class ConfigManager:
    """Менеджер для управления конфигурацией приложения

    Отвечает за загрузку, сохранение и управление настройками приложения.
    Реализует принцип единственной ответственности (SRP).
    Улучшена валидация позиции окна и автоматическая коррекция некорректных значений.
    """

    def __init__(self, config_file: str = "player_config.json"):
        self.config_file = config_file
        self.default_config = {
            "volume": DEFAULT_VOLUME,
            "last_channel": None,
            "last_category": "Все каналы",
            "favorites": [],
            "hidden_channels": [],
            "recent_playlists": [],
            "playlist_names": {},
            "show_hidden": False,
            "show_logos": True,
            "window_size": DEFAULT_WINDOW_SIZE,
            "window_position": DEFAULT_WINDOW_POSITION,
            "always_on_top": False
        }
        self.config = self.default_config.copy()
        self._config_lock = Lock()  # Для потокобезопасности

    def load_config(self) -> None:
        """Загружает конфигурацию из файла с валидацией"""
        with self._config_lock:
            try:
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        loaded_config = json.load(f)
                        # Обновляем конфигурацию, сохраняя значения по умолчанию для отсутствующих ключей
                        self.config.update(loaded_config)

                        # Валидируем и корректируем критические параметры
                        self._validate_and_fix_config()
                else:
                    # Создаем файл конфигурации с настройками по умолчанию
                    self._save_config_internal()

            except Exception as e:
                logging.error(f"Ошибка при загрузке конфигурации: {str(e)}")
                # Используем значения по умолчанию при ошибке
                self.config = self.default_config.copy()

    def save_config(self) -> None:
        """Сохраняет конфигурацию в файл потокобезопасно"""
        with self._config_lock:
            self._save_config_internal()

    def _save_config_internal(self) -> None:
        """Внутренний метод сохранения конфигурации без блокировки"""
        try:
            # Создаем резервную копию перед сохранением
            if os.path.exists(self.config_file):
                backup_file = f"{self.config_file}.backup"
                with open(self.config_file, 'r', encoding='utf-8') as src:
                    with open(backup_file, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            logging.info("Конфигурация успешно сохранена")
        except Exception as e:
            logging.error(f"Ошибка при сохранении конфигурации: {str(e)}")

    def get(self, key: str, default: Any = None) -> Any:
        """Получает значение конфигурации потокобезопасно"""
        with self._config_lock:
            return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Устанавливает значение конфигурации потокобезопасно"""
        with self._config_lock:
            self.config[key] = value

    def _validate_and_fix_config(self) -> None:
        """Валидирует и исправляет некорректные значения в конфигурации"""
        # Проверяем размер окна
        window_size = self.config.get('window_size', self.default_config['window_size'])
        if not isinstance(window_size, list) or len(window_size) != 2:
            self.config['window_size'] = self.default_config['window_size']
        else:
            # Проверяем разумные пределы размера
            width, height = window_size
            if width < 800 or height < 600 or width > 3840 or height > 2160:
                self.config['window_size'] = self.default_config['window_size']
                logging.warning(f"Некорректный размер окна {window_size}, использованы значения по умолчанию")

        # Проверяем позицию окна
        window_position = self.config.get('window_position', self.default_config['window_position'])
        if not isinstance(window_position, list) or len(window_position) != 2:
            self.config['window_position'] = self.default_config['window_position']
        else:
            # Проверяем разумные пределы позиции
            x, y = window_position
            if x < -100 or y < -100 or x > 5000 or y > 5000:
                self.config['window_position'] = self.default_config['window_position']
                logging.warning(f"Некорректная позиция окна {window_position}, использованы значения по умолчанию")

        # Проверяем громкость
        volume = self.config.get('volume', self.default_config['volume'])
        if not isinstance(volume, (int, float)) or volume < 0 or volume > 100:
            self.config['volume'] = self.default_config['volume']
            logging.warning(f"Некорректная громкость {volume}, использовано значение по умолчанию")

    def update_window_geometry(self, window):
        """Обновляет геометрию окна в конфигурации"""
        # Получаем текущую позицию и размер
        x, y = window.x(), window.y()
        width, height = window.width(), window.height()

        # Проверяем, что позиция разумная (не отрицательная и не слишком большая)
        try:
            from PyQt5.QtWidgets import QApplication
            desktop = QApplication.desktop()
            screen_geometry = desktop.availableGeometry()

            # Сохраняем только если позиция в разумных пределах
            if (x >= -100 and y >= -100 and
                x < screen_geometry.width() + 100 and
                y < screen_geometry.height() + 100):
                self.config["window_position"] = [x, y]
            else:
                # Не обновляем позицию, если она некорректная
                logging.warning(f"Некорректная позиция окна не сохранена: [{x}, {y}]")
        except:
            # В случае ошибки просто сохраняем как есть
            self.config["window_position"] = [x, y]

        self.config["window_size"] = [width, height]
        self.config["always_on_top"] = window.windowFlags() & Qt.WindowStaysOnTopHint == Qt.WindowStaysOnTopHint
