"""
Модуль UI компонентов для MaksIPTV Player
Версия 0.13.0

Содержит классы для создания пользовательских UI элементов:
- ClickableLabel - кликабельная метка
- UIComponentFactory - фабрика UI компонентов
- PlaylistUIManager - менеджер UI для работы с плейлистами
"""

import os
import time
from PyQt5.QtWidgets import (
    QLabel, QPushButton, QWidget, QHBoxLayout, QVBoxLayout, QDialog, 
    QLineEdit, QTabWidget, QFileDialog, QMessageBox, QMenu
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QCursor
import qtawesome as qta


class ClickableLabel(QLabel):
    """Класс для создания кликабельных меток"""

    # Сигнал для клика
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super(ClickableLabel, self).__init__(parent)
        # Устанавливаем курсор руки
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Вызываем кастомное событие при клике
            self.clicked.emit()
        # Вызываем родительский обработчик
        super(ClickableLabel, self).mousePressEvent(event)


class UIComponentFactory:
    """Фабрика для создания UI компонентов

    Устраняет дублирование кода при создании стандартных элементов интерфейса.
    Реализует принцип DRY (Don't Repeat Yourself).
    """

    @staticmethod
    def create_icon_button(icon_name, tooltip, size=QSize(28, 28), icon_size=QSize(14, 14), callback=None):
        """Создает стилизованную кнопку с иконкой"""
        button = QPushButton()
        button.setIcon(qta.icon(icon_name, color='#e8e8e8'))
        button.setIconSize(icon_size)
        button.setFixedSize(size)
        button.setToolTip(tooltip)

        # Добавляем стили для правильного выравнивания иконки по центру
        button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
                text-align: center;
                qproperty-iconSize: %dpx %dpx;
            }
            QPushButton:hover {
                background-color: rgba(90, 141, 176, 0.2);
                border-color: #5a8db0;
            }
            QPushButton:pressed {
                background-color: rgba(90, 141, 176, 0.3);
                border-color: #5a8db0;
            }
        """ % (icon_size.width(), icon_size.height()))

        if callback:
            button.clicked.connect(callback)

        return button

    @staticmethod
    def create_labeled_control(label_text, control, layout_type=QHBoxLayout):
        """Создает виджет с меткой и указанным контролом"""
        container = QWidget()
        layout = layout_type()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(label_text)
        label.setStyleSheet("color: #a0a0a0;")

        layout.addWidget(label)
        layout.addWidget(control)

        container.setLayout(layout)
        return container

    @staticmethod
    def create_styled_panel(object_name, background_color="#2d2d2d"):
        """Создает стилизованную панель"""
        panel = QWidget()
        panel.setObjectName(object_name)
        panel.setStyleSheet(f"QWidget#{object_name} {{ background-color: {background_color}; border-radius: 8px; }}")
        return panel


class PlaylistUIManager:
    """Упрощенный менеджер UI для работы с плейлистами

    Объединяет все операции с плейлистами в простой интерфейс:
    - Одна кнопка для всех операций с плейлистами
    - Контекстное меню с основными действиями
    - Автоматическое определение типа источника (файл/URL)
    """

    def __init__(self, parent):
        self.parent = parent

    def create_playlist_button(self):
        """Создает единую кнопку для работы с плейлистами"""
        # Основная кнопка - стилизуем в соответствии с общим UI
        self.playlist_button = QPushButton("📋 Плейлисты ▼")
        self.playlist_button.setToolTip("Управление плейлистами")

        # Устанавливаем размер кнопки как у других иконочных кнопок
        button_size = QSize(80, 28)  # Немного шире для текста
        self.playlist_button.setFixedSize(button_size)

        self.playlist_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #f0f0f0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: normal;
                font-size: 10px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(90, 141, 176, 0.2);
                border-color: #5a8db0;
            }
            QPushButton:pressed {
                background-color: rgba(90, 141, 176, 0.3);
                border-color: #5a8db0;
            }
        """)

        # Создаем меню
        menu = QMenu(self.parent)

        # Добавить плейлист
        add_action = menu.addAction("➕ Добавить плейлист...")
        add_action.triggered.connect(self.show_add_playlist_dialog)

        # Обновить текущий
        refresh_action = menu.addAction("🔄 Обновить текущий")
        refresh_action.triggered.connect(self.parent.reload_playlist)

        menu.addSeparator()

        # Недавние плейлисты (подменю)
        recent_menu = menu.addMenu("📚 Недавние")
        self.update_recent_submenu(recent_menu)

        menu.addSeparator()

        # Обновить встроенный плейлист
        update_builtin_action = menu.addAction("⬇️ Обновить встроенный")
        update_builtin_action.triggered.connect(self.parent.update_playlist_from_url)

        # Очистить историю
        clear_action = menu.addAction("🗑️ Очистить историю")
        clear_action.triggered.connect(self.parent.clear_recent_playlists)

        # Привязываем меню к кнопке
        self.playlist_button.setMenu(menu)

        return self.playlist_button

    def update_recent_submenu(self, menu):
        """Обновляет подменю недавних плейлистов"""
        menu.clear()

        if not self.parent.recent_playlists:
            no_action = menu.addAction("Нет недавних плейлистов")
            no_action.setEnabled(False)
            return

        for playlist_path in self.parent.recent_playlists[:5]:  # Показываем только 5 последних
            display_name = self.parent.playlist_names.get(playlist_path, os.path.basename(playlist_path))

            # Ограничиваем длину имени
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."

            # Добавляем индикатор текущего плейлиста
            if playlist_path == self.parent.current_playlist:
                display_name = f"▶️ {display_name}"

            action = menu.addAction(display_name)
            action.triggered.connect(lambda checked, path=playlist_path: self.parent.open_recent_playlist(path))

    def show_add_playlist_dialog(self):
        """Показывает упрощенный диалог добавления плейлиста"""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Добавить плейлист")
        dialog.setFixedSize(450, 200)

        layout = QVBoxLayout(dialog)

        # Создаем вкладки
        tabs = QTabWidget()

        # Вкладка "Из файла"
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)

        file_info = QLabel("Выберите файл плейлиста (.m3u, .m3u8)")
        file_info.setStyleSheet("color: #888; font-size: 11px;")
        file_layout.addWidget(file_info)

        file_path_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Путь к файлу плейлиста...")
        browse_button = QPushButton("📁 Обзор")
        browse_button.clicked.connect(self.browse_file)

        file_path_layout.addWidget(self.file_path_edit)
        file_path_layout.addWidget(browse_button)
        file_layout.addLayout(file_path_layout)

        # Добавляем поле для названия плейлиста из файла
        self.file_name_edit = QLineEdit()
        self.file_name_edit.setPlaceholderText("Название плейлиста (необязательно)")
        file_layout.addWidget(self.file_name_edit)

        tabs.addTab(file_tab, "📁 Файл")

        # Вкладка "Из URL"
        url_tab = QWidget()
        url_layout = QVBoxLayout(url_tab)

        url_info = QLabel("Введите URL плейлиста")
        url_info.setStyleSheet("color: #888; font-size: 11px;")
        url_layout.addWidget(url_info)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://example.com/playlist.m3u")
        url_layout.addWidget(self.url_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Название плейлиста (необязательно)")
        url_layout.addWidget(self.name_edit)

        tabs.addTab(url_tab, "🌐 URL")

        layout.addWidget(tabs)

        # Кнопки
        button_layout = QHBoxLayout()

        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(dialog.reject)

        add_button = QPushButton("Добавить")
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5ba0f2;
            }
        """)
        add_button.clicked.connect(lambda: self.add_playlist(dialog, tabs.currentIndex()))

        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(add_button)

        layout.addLayout(button_layout)

        dialog.exec_()

    def browse_file(self):
        """Открывает диалог выбора файла"""
        filename, _ = QFileDialog.getOpenFileName(
            self.parent, "Выберите плейлист", "",
            "Плейлисты (*.m3u *.m3u8);;Все файлы (*)"
        )
        if filename:
            self.file_path_edit.setText(filename)

            # Автоматически заполняем поле названия именем файла (без расширения)
            if not self.file_name_edit.text().strip():  # Только если поле пустое
                file_basename = os.path.splitext(os.path.basename(filename))[0]
                self.file_name_edit.setText(file_basename)

    def add_playlist(self, dialog, tab_index):
        """Добавляет плейлист в зависимости от выбранной вкладки"""
        if tab_index == 0:  # Файл
            file_path = self.file_path_edit.text().strip()
            if not file_path:
                QMessageBox.warning(dialog, "Ошибка", "Выберите файл плейлиста")
                return
            if not os.path.exists(file_path):
                QMessageBox.warning(dialog, "Ошибка", "Файл не найден")
                return

            # Получаем название плейлиста
            file_name = self.file_name_edit.text().strip()
            if file_name:
                # Сохраняем пользовательское название
                self.parent.playlist_names[file_path] = file_name
            else:
                # Используем имя файла без расширения как название по умолчанию
                default_name = os.path.splitext(os.path.basename(file_path))[0]
                self.parent.playlist_names[file_path] = default_name

            # Сохраняем обновленные названия плейлистов в конфигурацию
            self.parent.config_manager.set('playlist_names', self.parent.playlist_names)
            self.parent.config_manager.save_config()

            dialog.accept()
            self.parent.open_recent_playlist(file_path)

        else:  # URL
            url = self.url_edit.text().strip()
            if not url:
                QMessageBox.warning(dialog, "Ошибка", "Введите URL плейлиста")
                return
            if not url.startswith(('http://', 'https://')):
                QMessageBox.warning(dialog, "Ошибка", "URL должен начинаться с http:// или https://")
                return

            name = self.name_edit.text().strip() or "Плейлист из URL"

            dialog.accept()

            # Сохраняем имя плейлиста
            self.parent.playlist_names[url] = name

            # Сохраняем обновленные названия плейлистов в конфигурацию
            self.parent.config_manager.set('playlist_names', self.parent.playlist_names)
            self.parent.config_manager.save_config()

            # Загружаем плейлист
            temp_file = f"temp_playlist_{int(time.time())}.m3u"
            self.parent.download_playlist_from_url(url, temp_file, is_update=False)

    def update_menu_if_needed(self):
        """Обновляет меню кнопки, если оно существует"""
        if hasattr(self, 'playlist_button') and self.playlist_button.menu():
            # Находим подменю "Недавние"
            menu = self.playlist_button.menu()
            for action in menu.actions():
                if action.menu() and "Недавние" in action.text():
                    self.update_recent_submenu(action.menu())
                    break
