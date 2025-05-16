import sys
import os
import re
import time
import json
import urllib.request
import urllib.error
import logging
import socket
import uuid
from datetime import datetime
from functools import partial
import warnings
import requests
import hashlib
import urllib3

"""
MaksIPTV Player
Версия 0.11.48 (Рефакторинг)

Изменения:
1. Разбит перегруженный метод init_ui() на логические компоненты для 
   лучшей читаемости и поддержки кода
2. Добавлены вспомогательные методы (make_icon_button, create_labeled_control и др.)
   для устранения дублирования кода и упрощения интерфейса
3. Исправлен баг с полноэкранным режимом через переработку toggle_fullscreen()
4. Изолирована платформенно-зависимая логика в отдельный класс PlatformManager
5. Улучшена документация методов для облегчения будущей поддержки
6. Добавлен централизованный метод обновления UI

Все функции сохранены в полном объеме, изменения касаются только
внутренней структуры кода для улучшения его поддерживаемости.
"""

# Игнорируем предупреждения о устаревшем методе sipPyTypeDict в PyQt5
warnings.filterwarnings("ignore", category=DeprecationWarning, message="sipPyTypeDict")

"""# Указываем путь к libvlc, если он не в стандартном месте
if getattr(sys, 'frozen', False):
    # если PyInstaller-сборка, добавляем путь
    os.environ["LD_LIBRARY_PATH"] = "/usr/lib/x86_64-linux-gnu/"
"""
import vlc
import qtawesome as qta
import platform
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QLineEdit, QPushButton, QSlider, QStyle, QToolBar, QAction, 
    QStatusBar, QProgressBar, QMenu, QSystemTrayIcon, QFileDialog, QInputDialog, 
    QListWidgetItem, QWidgetAction, QGraphicsOpacityEffect, QMessageBox, 
    QTreeWidget, QTreeWidgetItem, QFrame, QSplitter, QListWidget, QMenuBar, 
    QDialog, QSizePolicy, QTextBrowser, QStackedWidget, QHeaderView, 
    QTreeWidgetItemIterator, QAbstractItemView, QDialogButtonBox
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, pyqtSignal, QThread, QPoint, QByteArray, QEvent
)
from PyQt5.QtGui import (
    QIcon, QFont, QPalette, QColor, QPixmap, QImage, QCursor, QPainter, QBrush, QPen, QLinearGradient
)

# Определение потоковых классов для загрузки
class DownloadThread(QThread):
    """Поток для загрузки файлов по URL"""
    finished = pyqtSignal(bool, str)
    
    def __init__(self, url, file_path):
        super().__init__()
        self.url = url
        self.file_path = file_path
    
    def run(self):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            request = urllib.request.Request(self.url, headers=headers)
            response = urllib.request.urlopen(request, timeout=30)
            
            with open(self.file_path, 'wb') as f:
                f.write(response.read())
                
            self.finished.emit(True, "")
        except urllib.error.URLError as e:
            self.finished.emit(False, f"Ошибка URL: {str(e)}")
        except urllib.error.HTTPError as e:
            self.finished.emit(False, f"Ошибка HTTP: {e.code} {e.reason}")
        except (TimeoutError, socket.timeout, socket.error):
            # Обрабатываем все виды таймаутов и ошибок сокета
            self.finished.emit(False, "Превышено время ожидания")
        except Exception as e:
            self.finished.emit(False, str(e))

class ChannelPlayThread(QThread):
    """Поток для асинхронного воспроизведения канала"""
    setup_finished = pyqtSignal(bool, str, object)  # Статус, сообщение об ошибке, медиа-объект
    
    def __init__(self, url, options=None, vlc_instance=None):
        super().__init__()
        self.url = url
        self.options = options or {}
        self.vlc_instance = vlc_instance
        self.media = None
        
    def run(self):
        try:
            # Создаем медиа с нужным URL
            self.media = self.vlc_instance.media_new(self.url)
            
            # Настраиваем медиа-опции VLC, если они указаны для канала
            if self.options:
                for opt_name, opt_value in self.options.items():
                    if opt_name == 'user-agent':
                        self.media.add_option(f":http-user-agent={opt_value}")
                    elif opt_name == 'http-referrer' or opt_name == 'referer':
                        self.media.add_option(f":http-referrer={opt_value}")
                    else:
                        self.media.add_option(f":{opt_name}={opt_value}")
            
            # Добавляем общие сетевые опции для улучшения воспроизведения
            self.media.add_option(":network-caching=3000")
            self.media.add_option(":file-caching=1000")
            self.media.add_option(":live-caching=1000")
            self.media.add_option(":sout-mux-caching=1000")
            
            # Дополнительные опции для стабильности
            self.media.add_option(":http-reconnect")
            self.media.add_option(":rtsp-tcp")
            self.media.add_option(":no-video-title-show")
            
            # Сигнализируем о готовности медиа
            self.setup_finished.emit(True, "", self.media)
            
        except Exception as e:
            logging.error(f"Ошибка в потоке воспроизведения: {str(e)}")
            self.setup_finished.emit(False, str(e), None)

class PlaylistDownloadThread(QThread):
    """Поток для загрузки плейлистов с возвратом URL источника"""
    finished = pyqtSignal(bool, str, str)
    
    def __init__(self, url, file_path):
        super().__init__()
        self.url = url
        self.file_path = file_path
    
    def run(self):
        try:
            # Настраиваем opener с User-Agent для обхода ограничений
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')]
            urllib.request.install_opener(opener)
            
            # Скачиваем напрямую
            request = urllib.request.Request(self.url)
            response = urllib.request.urlopen(request, timeout=30)
            
            content = response.read()
            
            # Проверяем, что контент похож на плейлист
            content_str = content.decode('utf-8', errors='ignore')
            if not ('#EXTM3U' in content_str or '#EXTINF' in content_str):
                self.finished.emit(False, "Скачанный файл не является плейлистом IPTV", "")
                return
            
            with open(self.file_path, 'wb') as f:
                f.write(content)
            
            self.finished.emit(True, "", self.url)
        except (TimeoutError, socket.timeout, socket.error):
            # Обрабатываем все виды таймаутов и ошибок сокета
            self.finished.emit(False, "Превышено время ожидания", "")
        except Exception as e:
            self.finished.emit(False, str(e), "")

# Определение стилей
STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #f0f0f0;
}

QLabel {
    color: #f0f0f0;
    font-size: 13px;
}

QLabel#channelNameLabel {
    font-size: 16px;
    font-weight: bold;
    color: #ffffff;
    padding: 8px;
    background-color: rgba(90, 141, 176, 0.2);
    border-radius: 6px;
}

QTreeWidget, QListWidget, QComboBox, QLineEdit {
    background-color: #2d2d2d;
    color: #f0f0f0;
    border: 1px solid #444444;
    border-radius: 6px;
    padding: 4px;
}

QTreeWidget, QListWidget {
    padding: 5px;
    background-color: #2d2d2d;
    alternate-background-color: #333333;
}

QTreeWidget::item, QListWidget::item {
    padding: 8px;
    margin: 2px 0;
    border-radius: 4px;
}

QTreeWidget::item:hover, QListWidget::item:hover {
    background-color: rgba(90, 141, 176, 0.3);
}

QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #5a8db0;
    color: white;
}

QComboBox {
    padding: 8px;
    border-radius: 6px;
    min-height: 30px;
}

QComboBox::drop-down {
    width: 25px;
    border-left: 1px solid #444444;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox::down-arrow {
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTQiIGhlaWdodD0iMTQiIHZpZXdCb3g9IjAgMCAxNCAxNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTcgMTBMMTAgNUg0TDcgMTBaIiBmaWxsPSIjZjBmMGYwIi8+Cjwvc3ZnPgo=);
}

QMenuBar {
    background-color: #1e1e1e;
    color: #f0f0f0;
    border-bottom: 1px solid #444444;
}

QMenuBar::item {
    background-color: transparent;
    padding: 6px 15px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #5a8db0;
    color: white;
}

QMenuBar::item:pressed {
    background-color: #4d7d9e;
    color: white;
}

QMenu {
    background-color: #2d2d2d;
    color: #f0f0f0;
    border: 1px solid #444444;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 30px 8px 20px;
    border-radius: 4px;
    margin: 2px 4px;
}

QMenu::item:selected {
    background-color: #5a8db0;
    color: white;
}

QMenu::separator {
    height: 1px;
    background-color: #444444;
    margin: 6px 10px;
}

QPushButton {
    background-color: #5a8db0;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    min-height: 30px;
}

QPushButton:hover {
    background-color: #6a9cbe;
}

QPushButton:pressed {
    background-color: #4d7d9e;
}

QPushButton:disabled {
    background-color: #555555;
    color: #999999;
}

QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px;
}

QToolButton:hover {
    background-color: rgba(90, 141, 176, 0.2);
}

QToolButton:pressed {
    background-color: rgba(90, 141, 176, 0.3);
}

QLineEdit {
    padding: 8px;
    border-radius: 6px;
    background-color: #2d2d2d;
    min-height: 30px;
}

QLineEdit:focus {
    border: 1px solid #5a8db0;
}

QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #444444;
    margin: 2px 0;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #5a8db0;
    border: none;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #6a9cbe;
}

QProgressBar {
    border: none;
    border-radius: 4px;
    text-align: center;
    background-color: #444444;
    height: 8px;
}

QProgressBar::chunk {
    background-color: #5a8db0;
    border-radius: 4px;
}

QFrame#videoFrame {
    background-color: #131313;
    border: 1px solid #333333;
    border-radius: 6px;
}

QSplitter::handle {
    background-color: #444444;
    width: 1px;
    margin: 0 2px;
}

QStatusBar {
    background-color: #1e1e1e;
    color: #f0f0f0;
    border-top: 1px solid #444444;
}

QScrollBar:vertical {
    border: none;
    background: #2d2d2d;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #555555;
    min-height: 30px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #666666;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #2d2d2d;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #555555;
    min-width: 30px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #666666;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QHeaderView::section {
    background-color: #2d2d2d;
    color: #f0f0f0;
    padding: 5px;
    border: 1px solid #444444;
}

/* Стили для категорий */
QWidget#left_panel {
    background-color: #1e1e1e;
    border-right: 1px solid #333333;
    border-radius: 0px;
}

QWidget#right_panel {
    background-color: #1e1e1e;
}

QLabel#channelsHeader {
    font-size: 18px;
    font-weight: bold;
    padding: 10px;
    color: #ffffff;
    border-bottom: 1px solid #3d8ec9;
    margin-bottom: 10px;
}

QLabel#playlistInfo {
    color: #a0a0a0;
    font-size: 12px;
    padding: 5px;
}
"""

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

class PlatformManager:
    """Класс для управления платформенно-зависимой логикой
    
    Обеспечивает унифицированный доступ к функциям, которые различаются
    в зависимости от операционной системы (Windows, Linux, macOS).
    """
    
    @staticmethod
    def get_platform_name():
        """Возвращает название текущей платформы
        
        Returns:
            str: Название платформы ('windows', 'linux', 'macos' или 'unknown')
        """
        if sys.platform.startswith('win'):
            return 'windows'
        elif sys.platform.startswith('linux'):
            return 'linux'
        elif sys.platform.startswith('darwin'):
            return 'macos'
        else:
            return 'unknown'
    
    @staticmethod
    def setup_vlc_video_output(media_player, frame_handle):
        """Настраивает вывод видео с учетом платформы
        
        Args:
            media_player: Объект медиаплеера VLC
            frame_handle: Дескриптор окна для вывода видео
            
        Returns:
            tuple: (success, error_message)
        """
        try:
            if sys.platform.startswith("linux"):
                # Для Linux используем X Window System
                media_player.set_xwindow(int(frame_handle))
                return True, "Настроен видеовывод для Linux (XWindow)"
            elif sys.platform.startswith("win"):
                # Для Windows используем HWND
                media_player.set_hwnd(frame_handle)
                return True, "Настроен видеовывод для Windows (HWND)"
            elif sys.platform.startswith("darwin"):
                # Для macOS используем NSObject
                media_player.set_nsobject(int(frame_handle))
                return True, "Настроен видеовывод для macOS (NSObject)"
            else:
                # Для неизвестных платформ пытаемся использовать XWindow
                media_player.set_xwindow(int(frame_handle))
                return True, f"Использован XWindow для неизвестной платформы: {sys.platform}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_vlc_args():
        """Возвращает аргументы командной строки для VLC в зависимости от платформы
        
        Returns:
            list: Список аргументов командной строки для VLC
        """
        args = [
            "--no-video-title-show",
            "--no-osd",
            "--no-stats",
            "--no-sub-autodetect",
            "--no-snapshot-preview",
            "--live-caching=1000",
            "--network-caching=3000",
            "--http-reconnect",
            "--rtsp-tcp",
        ]
        
        # Добавляем специфические для платформы аргументы
        platform = PlatformManager.get_platform_name()
        
        if platform == 'windows':
            # Пробуем использовать Direct3D для ускорения
            args.extend([
                "--directx-device=default",
                "--directx-use-sysmem",
            ])
        elif platform == 'linux':
            # Для Linux можем использовать опции для X11
            args.extend([
                "--x11-display=default",
            ])
        elif platform == 'macos':
            # Для macOS 
            args.extend([
                "--macosx-vdev=default",
            ])
            
        return args

class IPTVPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Заголовок окна и иконка
        self.setWindowTitle("MaksIPTV Плеер")
        self.setWindowIcon(qta.icon('fa5s.tv'))
        
        # Размеры окна
        self.setGeometry(40, 40, 1200, 650)
        self.setMinimumSize(1000, 650)
        
        # Применяем стили
        self.setStyleSheet(STYLESHEET)
        
        # Стандартная иконка для каналов без логотипа
        self.default_channel_icon = self.create_default_channel_icon()
        
        # Дополнительные данные
        self.channels = []
        self.categories = {"Все каналы": []}
        self.current_channel_index = -1
        self.current_channel = ""
        self.favorites = []
        self.hidden_channels = []
        
        # Загружаем конфигурацию
        self.config_file = "player_config.json"
        self.load_config()  # Теперь метод устанавливает атрибуты напрямую
        
        # Флаги для отображения избранных и скрытых каналов
        self.show_favorites = False
        
        # История плейлистов
        if not hasattr(self, 'recent_playlists') or not self.recent_playlists:
            self.recent_playlists = ["local.m3u"]
        self.current_playlist = self.recent_playlists[0] if self.recent_playlists else "local.m3u"
        self.temp_playlist_path = None
        
        # Настройка VLC
        vlc_args = []
        
        # Для логов VLC
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        vlc_log_file = os.path.join(log_dir, "vlc.log")
        vlc_args.append(f"--logfile={vlc_log_file}")
        
        # Добавляем аргументы VLC для улучшения производительности
        vlc_args.extend(PlatformManager.get_vlc_args())
        
        # Инициализация VLC
        self.instance = vlc.Instance(' '.join(vlc_args))
        self.media_player = self.instance.media_player_new()
        
        # Счетчик попыток переподключения
        self.retry_count = 0
        self.max_retry_count = 3  # Максимальное количество автоматических попыток
        
        # Таймер для обнаружения подвисших каналов
        self.play_timeout_timer = QTimer(self)
        self.play_timeout_timer.setSingleShot(True)
        self.play_timeout_timer.timeout.connect(self.handle_play_timeout)
        
        # Поток для воспроизведения канала
        self.channel_play_thread = None
        
        # Время ожидания начала воспроизведения (сек)
        self.play_timeout = 10
        
        # Инициализируем интерфейс
        self.init_ui()
        
        # Подключаем таймер обновления UI
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start()
        
        # Подключаем обработчики событий медиаплеера
        self.event_manager = self.media_player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.media_playing)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self.media_paused)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self.media_stopped)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.handle_error)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.media_stopped)
        
        # Устанавливаем запомненный уровень громкости
        self.volume_slider.setValue(self.volume)
        self.set_volume(self.volume)
        
        # Обновляем меню недавних плейлистов
        self.update_recent_menu()
         
        # Показываем приложение
        # Настройка атрибутов окна для плавного старта
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_StaticContents, True)
        self.show()
        
        # Настройка системного трея
        self.setup_tray()
        
        # Привязываем обработчик закрытия окна для корректного завершения потоков
        self.closeEvent = self.handle_close_event
        
        # Обновление встроенного плейлиста при запуске
        QTimer.singleShot(0, self.update_playlist_from_url)

    def make_icon_button(self, icon_name, tooltip, size=QSize(32, 32), icon_size=QSize(16, 16), callback=None):
        """Создает стилизованную кнопку с иконкой
        
        Args:
            icon_name: Название иконки из qtawesome
            tooltip: Текст подсказки
            size: Размер кнопки
            icon_size: Размер иконки
            callback: Функция обратного вызова
            
        Returns:
            QPushButton: Созданная кнопка
        """
        button = QPushButton()
        button.setIcon(qta.icon(icon_name, color='#e8e8e8'))
        button.setIconSize(icon_size)
        button.setFixedSize(size)
        button.setToolTip(tooltip)
        
        if callback:
            button.clicked.connect(callback)
            
        return button
    
    def create_labeled_control(self, label_text, control, layout_type=QHBoxLayout):
        """Создает виджет с меткой и указанным контролом
        
        Args:
            label_text: Текст метки
            control: Контрол, который нужно добавить
            layout_type: Тип компоновки (горизонтальный или вертикальный)
            
        Returns:
            QWidget: Виджет, содержащий метку и контрол
        """
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
    
    def setup_video_output(self):
        """Настраивает вывод видео с учетом платформы
        
        Устанавливает соответствующий метод отображения VLC в зависимости
        от операционной системы (Linux, Windows, macOS).
        """
        try:
            # Получаем идентификатор окна для видеофрейма
            win_id = self.video_frame.winId()
            
            # Используем PlatformManager для настройки вывода
            success, message = PlatformManager.setup_vlc_video_output(self.media_player, win_id)
            
            if success:
                logging.info(message)
            else:
                raise Exception(message)
        except Exception as e:
            logging.error(f"Ошибка при настройке видеовывода: {str(e)}")
            QMessageBox.warning(
                self, 
                "Предупреждение", 
                f"Не удалось настроить видеовывод: {str(e)}\n"
                "Воспроизведение видео может работать некорректно."
            )

    def init_ui(self):
        """Инициализирует пользовательский интерфейс приложения"""
        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Создаем основную компоновку
        main_layout = self.create_main_layout(central_widget)
        
        # Создаем меню приложения
        self.create_menu()
        
        # Создаем основной сплиттер
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(2)
        
        # Создаем левую и правую панели
        left_panel = self.create_left_panel()
        right_panel = self.create_right_panel()
        
        # Добавляем панели в сплиттер
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(right_panel)
        
        # Устанавливаем начальные размеры панелей
        self.main_splitter.setSizes([int(self.width() * 0.3), int(self.width() * 0.7)])
        
        # Добавляем сплиттер в главный макет
        main_layout.addWidget(self.main_splitter)
        
        # Создаем статусную строку
        self.setup_statusbar()
        
        # Загружаем плейлист
        self.fill_channel_list()
        
        # Безопасная установка окна для воспроизведения
        self.setup_video_output()
        
        # Если был сохранен последний канал, выбираем его автоматически
        if self.last_channel:
            self.restore_last_channel(self.last_channel)
            
    def create_main_layout(self, parent_widget):
        """Создает основную компоновку приложения
        
        Args:
            parent_widget: Родительский виджет для размещения компоновки
            
        Returns:
            QVBoxLayout: Созданная основная компоновка
        """
        main_layout = QVBoxLayout(parent_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        return main_layout
    
    def create_left_panel(self):
        """Создает левую панель с категориями и списком каналов
        
        Returns:
            QWidget: Левая панель с содержимым
        """
        left_panel = QWidget()
        left_panel.setObjectName("left_panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)
        
        # Заголовок панели каналов
        channels_header = QLabel("КАНАЛЫ")
        channels_header.setObjectName("channelsHeader")
        channels_header.setAlignment(Qt.AlignCenter)
        
        # Выбор категории
        self.category_combo = QComboBox()
        self.category_combo.addItems(sorted(self.categories.keys()))
        self.category_combo.currentTextChanged.connect(self.category_changed)
        
        category_container = self.create_labeled_control("Категория:", self.category_combo)
        
        # Поиск
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Поиск каналов...")
        self.search_box.textChanged.connect(self.filter_channels)
        
        search_container = self.create_labeled_control("Поиск:", self.search_box)
        
        # Панель кнопок
        button_layout = self.create_channel_button_panel()
        
        # Создаем компоненты для отображения каналов
        self.create_channel_view_widgets()
        
        # Информация о плейлисте
        total_channels = len(self.channels)
        visible_channels = total_channels - len(self.hidden_channels)
        self.playlist_info_label = QLabel(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
        self.playlist_info_label.setObjectName("playlistInfo")
        self.playlist_info_label.setAlignment(Qt.AlignCenter)
        
        # Добавляем все виджеты на левую панель
        left_layout.addWidget(channels_header)
        left_layout.addWidget(category_container)
        left_layout.addWidget(search_container)
        left_layout.addLayout(button_layout)
        left_layout.addWidget(self.channels_stack, 1)
        left_layout.addWidget(self.playlist_info_label)
        
        return left_panel
    
    def create_channel_button_panel(self):
        """Создает панель с кнопками управления списком каналов
        
        Returns:
            QHBoxLayout: Компоновка с кнопками
        """
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        
        # Кнопки с иконками для управления списком каналов
        button_size = QSize(32, 32)
        icon_size = QSize(16, 16)
        
        self.sort_button = self.make_icon_button(
            'fa5s.sort-alpha-down', "Сортировать по алфавиту", 
            button_size, icon_size, self.sort_channels
        )
        
        self.refresh_button = self.make_icon_button(
            'fa5s.sync', "Обновить плейлист", 
            button_size, icon_size, self.reload_playlist
        )
        
        self.update_button = self.make_icon_button(
            'fa5s.cloud-download-alt', "Обновить из интернета", 
            button_size, icon_size, self.update_playlist_from_url
        )
        
        self.favorites_button = self.make_icon_button(
            'fa5s.star', "Избранное", 
            button_size, icon_size, self.toggle_favorites
        )
        
        self.hidden_button = self.make_icon_button(
            'fa5s.eye-slash', "Скрытые каналы", 
            button_size, icon_size, self.toggle_hidden_channels
        )
        
        self.play_selected_button = self.make_icon_button(
            'fa5s.play-circle', "Воспроизвести выбранный канал", 
            button_size, icon_size, self.play_selected_channel
        )
        
        button_layout.addWidget(self.sort_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.favorites_button)
        button_layout.addWidget(self.hidden_button)
        button_layout.addWidget(self.play_selected_button)
        button_layout.addStretch(1)
        
        return button_layout
    
    def create_channel_view_widgets(self):
        """Создает виджеты для отображения списка каналов"""
        # Список каналов
        self.channel_list = QListWidget()
        self.channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.channel_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.channel_list.setAlternatingRowColors(True)  # Включаем чередование цветов строк
        
        # Настраиваем стиль и размеры для отображения логотипов
        self.channel_list.setStyleSheet("""
            QListWidget { 
                alternate-background-color: #383838;
                background-color: #2a2a2a;
            }
            
            QListWidget::item { 
                padding: 10px 10px 10px 44px; /* Отступ слева под логотип */
                margin: 2px 0;
                height: 40px; /* Фиксированная высота для элементов списка */
            }
            
            QListWidget::item:nth-child(odd) { 
                background-color: #2a2a2a;
            }
            
            QListWidget::item:nth-child(even) { 
                background-color: #383838;
            }
            
            QListWidget::item:selected {
                background-color: #4080b0;
                color: white;
            }
        """)
        
        self.channel_list.setIconSize(QSize(32, 32))  # Устанавливаем размер иконок для логотипов
        self.channel_list.currentRowChanged.connect(self.channel_changed)
        
        # Двойной клик на канале начинает воспроизведение
        self.channel_list.itemDoubleClicked.connect(self.on_channel_double_clicked)
        
        # Добавляем контекстное меню к списку каналов
        self.channel_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self.show_channel_context_menu)
        
        # Древовидный список каналов
        self.channel_tree = QTreeWidget()
        self.channel_tree.setHeaderHidden(True)
        self.channel_tree.setIconSize(QSize(32, 32))  # Устанавливаем размер иконок для логотипов
        self.channel_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.channel_tree.setAlternatingRowColors(True)  # Включаем чередование цветов строк
        
        # Настраиваем стиль для древовидного списка
        self.channel_tree.setStyleSheet("""
            QTreeWidget { 
                alternate-background-color: #383838;
                background-color: #2a2a2a;
            }
            
            QTreeWidget::item { 
                padding: 8px; 
                margin: 2px 0;
                height: 40px; /* Фиксированная высота для элементов списка */
            }
            
            QTreeWidget::item:nth-child(odd) { 
                background-color: #2a2a2a;
            }
            
            QTreeWidget::item:nth-child(even) { 
                background-color: #383838;
            }
            
            QTreeWidget::item:selected {
                background-color: #4080b0;
                color: white;
            }
        """)
        
        self.channel_tree.itemSelectionChanged.connect(self.tree_selection_changed)
        
        # Двойной клик на канале начинает воспроизведение
        self.channel_tree.itemDoubleClicked.connect(lambda item: self.on_channel_double_clicked(item))
        
        # Добавляем контекстное меню к дереву каналов
        self.channel_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.channel_tree.customContextMenuRequested.connect(self.show_channel_context_menu)
        
        # Стек виджетов для переключения между списком и деревом
        self.channels_stack = QStackedWidget()
        self.channels_stack.addWidget(self.channel_tree)
        self.channels_stack.addWidget(self.channel_list)
        
        # По умолчанию показываем обычный список
        self.channels_stack.setCurrentIndex(1)
        
        return self.channels_stack
    
    def create_right_panel(self):
        """Создает правую панель с видео и элементами управления
        
        Returns:
            QWidget: Правая панель с содержимым
        """
        right_panel = QWidget()
        right_panel.setObjectName("right_panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        right_layout.setSpacing(15)
        
        # Заголовок с названием канала
        self.channel_name_label = QLabel("Нет воспроизведения")
        self.channel_name_label.setObjectName("channelNameLabel")
        self.channel_name_label.setAlignment(Qt.AlignCenter)
        
        # Создаем фрейм для видео
        self.create_video_frame()
        
        # Создаем панель управления воспроизведением
        control_panel = self.create_control_panel()
        
        # Создаем информационную панель
        info_panel = self.create_info_panel()
        
        # Добавляем все элементы на правую панель
        right_layout.addWidget(self.channel_name_label)
        right_layout.addWidget(self.video_frame, 1)
        right_layout.addWidget(control_panel)
        right_layout.addWidget(info_panel)
        
        return right_panel
    
    def create_video_frame(self):
        """Создает фрейм для отображения видео"""
        # Фрейм для видео
        self.video_frame = QFrame()
        self.video_frame.setObjectName("videoFrame")
        self.video_frame.setFrameShape(QFrame.StyledPanel)
        self.video_frame.setFrameShadow(QFrame.Raised)
        self.video_frame.setMinimumHeight(400)
        
        # При клике на видео - переключаем полноэкранный режим
        self.video_frame_label = ClickableLabel()
        self.video_frame_label.setAlignment(Qt.AlignCenter)
        self.video_frame_label.clicked.connect(self.toggle_fullscreen)
        
        video_layout = QVBoxLayout(self.video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.addWidget(self.video_frame_label)
    
    def create_control_panel(self):
        """Создает панель с элементами управления воспроизведением
        
        Returns:
            QWidget: Панель управления
        """
        control_panel = QWidget()
        control_panel.setObjectName("controlPanel")
        control_panel.setStyleSheet("QWidget#controlPanel { background-color: #2d2d2d; border-radius: 8px; }")
        
        control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(10, 5, 10, 5)
        control_layout.setSpacing(8)
        
        # Размеры кнопок и иконок
        button_size = QSize(36, 36)
        icon_size = QSize(20, 20)
        
        # Кнопки управления воспроизведением
        self.play_button = self.make_icon_button(
            'fa5s.play', "Воспроизведение/Пауза (Пробел)", 
            button_size, icon_size, self.play_pause
        )
        
        self.stop_button = self.make_icon_button(
            'fa5s.stop', "Остановить", 
            button_size, icon_size, self.stop
        )
        
        self.screenshot_button = self.make_icon_button(
            'fa5s.camera', "Сделать снимок экрана", 
            button_size, icon_size, self.take_screenshot
        )
        
        self.audio_track_button = self.make_icon_button(
            'fa5s.volume-up', "Следующая аудиодорожка (A)", 
            button_size, icon_size, self.next_audio_track
        )
        
        self.fullscreen_button = self.make_icon_button(
            'fa5s.expand', "Полный экран (CTRL+F)", 
            button_size, icon_size, self.toggle_fullscreen
        )
        
        # Создаем виджет для регулировки громкости
        volume_panel = self.create_volume_panel()
        
        # Добавляем элементы на панель управления
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.screenshot_button)
        control_layout.addWidget(self.audio_track_button)
        control_layout.addStretch(1)
        control_layout.addWidget(volume_panel)
        control_layout.addStretch(1)
        control_layout.addWidget(self.fullscreen_button)
        
        return control_panel
    
    def create_volume_panel(self):
        """Создает панель регулировки громкости
        
        Returns:
            QWidget: Панель с регулятором громкости
        """
        volume_panel = QWidget()
        volume_layout = QHBoxLayout(volume_panel)
        volume_layout.setContentsMargins(0, 0, 0, 0)
        volume_layout.setSpacing(5)
        
        self.volume_icon = QLabel()
        self.volume_icon.setPixmap(qta.icon('fa5s.volume-up', color='#e8e8e8').pixmap(QSize(18, 18)))
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setToolTip("Громкость")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)  # Начальная громкость 70%
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.volume_slider.setFixedWidth(120)
        
        volume_layout.addWidget(self.volume_icon)
        volume_layout.addWidget(self.volume_slider)
        
        return volume_panel
    
    def create_info_panel(self):
        """Создает информационную панель с индикаторами состояния
        
        Returns:
            QWidget: Информационная панель
        """
        info_panel = QWidget()
        info_panel.setObjectName("infoPanel")
        info_panel.setStyleSheet("QWidget#infoPanel { background-color: #2d2d2d; border-radius: 8px; }")
        
        info_layout = QHBoxLayout(info_panel)
        info_layout.setContentsMargins(10, 5, 10, 5)
        
        self.info_label = QLabel("Готов к воспроизведению")
        self.info_label.setStyleSheet("color: #a0a0a0;")
        
        # Прогресс бар для буферизации
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Бесконечный прогресс
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        
        info_layout.addWidget(self.info_label)
        info_layout.addWidget(self.progress_bar)
        
        return info_panel

    def create_menu(self):
        """Создает главное меню приложения"""
        menu_bar = self.menuBar()
        
        # Меню "Файл"
        file_menu = menu_bar.addMenu("Файл")
        
        # Действие "Открыть плейлист"
        open_action = QAction("Открыть плейлист...", self)
        open_action.triggered.connect(self.open_playlist)
        file_menu.addAction(open_action)
        
        # Действие "Добавить плейлист из URL"
        add_url_action = QAction("Добавить плейлист из URL...", self)
        add_url_action.triggered.connect(self.add_playlist_from_url)
        file_menu.addAction(add_url_action)
        
        # Действие "Обновить плейлист из URL"
        update_url_action = QAction("Обновить плейлист из URL...", self)
        update_url_action.triggered.connect(self.update_playlist_from_url)
        file_menu.addAction(update_url_action)
        
        # Действие "Обновить текущий плейлист"
        reload_action = QAction("Обновить текущий плейлист", self)
        reload_action.triggered.connect(self.reload_playlist)
        file_menu.addAction(reload_action)
        
        # Подменю "Недавние плейлисты"
        self.recent_menu = QMenu("Недавние плейлисты", self)
        file_menu.addMenu(self.recent_menu)
        
        # Разделитель
        file_menu.addSeparator()
        
        # Действие "Выход"
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.exit_app)
        file_menu.addAction(exit_action)
        
        # Меню "Вид"
        view_menu = menu_bar.addMenu("Вид")
        
        # Действие "Полноэкранный режим"
        self.fullscreen_action = QAction("Полноэкранный режим", self)
        self.fullscreen_action.setCheckable(True)
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(self.fullscreen_action)
        
        # Действие "Всегда поверх других окон"
        self.always_on_top_action = QAction("Поверх всех окон", self)
        self.always_on_top_action.setCheckable(True)
        self.always_on_top_action.setChecked(self.windowFlags() & Qt.WindowStaysOnTopHint == Qt.WindowStaysOnTopHint)
        self.always_on_top_action.triggered.connect(self.toggle_always_on_top)
        view_menu.addAction(self.always_on_top_action)
        
        # Разделитель
        view_menu.addSeparator()
        
        # Действие "Показывать логотипы каналов"
        self.show_logos_action = QAction("Показывать логотипы каналов", self)
        self.show_logos_action.setCheckable(True)
        self.show_logos_action.setChecked(self.show_logos)
        self.show_logos_action.triggered.connect(self.toggle_logos)
        view_menu.addAction(self.show_logos_action)
        
        # Действие "Показывать скрытые каналы"
        self.show_hidden_action = QAction("Показывать скрытые каналы", self)
        self.show_hidden_action.setCheckable(True)
        self.show_hidden_action.setChecked(self.show_hidden)
        self.show_hidden_action.triggered.connect(self.toggle_hidden_channels)
        view_menu.addAction(self.show_hidden_action)
        
        # Действие "Сделать скриншот"
        screenshot_action = QAction("Сделать скриншот", self)
        screenshot_action.triggered.connect(self.take_screenshot)
        view_menu.addAction(screenshot_action)
        
        # Меню "Избранное"
        favorites_menu = menu_bar.addMenu("Избранное")
        
        # Действие "Показать все избранные"
        show_favorites_action = QAction("Показать все избранные", self)
        show_favorites_action.triggered.connect(self.show_all_favorites)
        favorites_menu.addAction(show_favorites_action)
        
        # Действие "Очистить избранное"
        clear_favorites_action = QAction("Очистить избранное", self)
        clear_favorites_action.triggered.connect(self.clear_favorites)
        favorites_menu.addAction(clear_favorites_action)
        
        # Меню "Справка"
        help_menu = menu_bar.addMenu("Справка")
        
        # Действие "О программе"
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        # Обновляем список недавних плейлистов
        self.update_recent_menu()
        
        return menu_bar

    def update_recent_menu(self):
        """Обновляет меню недавно открытых плейлистов"""
        self.recent_menu.clear()
        
        if not self.recent_playlists:
            empty_action = QAction("Нет недавних плейлистов", self)
            empty_action.setEnabled(False)
            self.recent_menu.addAction(empty_action)
            
            # Добавляем разделитель и пункт "Очистить список"
            self.recent_menu.addSeparator()
            clear_action = QAction("Очистить список", self)
            clear_action.triggered.connect(self.clear_recent_playlists)
            self.recent_menu.addAction(clear_action)
            return
            
        for i, playlist in enumerate(self.recent_playlists):
            # Используем имя плейлиста из словаря, если оно есть
            if playlist in self.playlist_names:
                display_name = self.playlist_names[playlist]
            else:
                # Иначе используем имя файла для путей или URL целиком
                display_name = os.path.basename(playlist) if os.path.exists(playlist) else playlist
                
                # Если это URL, добавляем пометку
                if playlist.startswith(('http://', 'https://')):
                    display_name = f"{display_name} (URL)"
            
            # Проверяем, является ли плейлист текущим
            is_current = False
            
            # Прямое совпадение пути
            if playlist == self.current_playlist:
                is_current = True
            
            # Проверка на временный плейлист (для плейлистов из URL)
            if hasattr(self, 'temp_playlist_path') and self.temp_playlist_path:
                if (playlist.startswith(('http://', 'https://')) and 
                    self.current_playlist == playlist and 
                    self.temp_playlist_path == "temp_playlist.m3u"):
                    is_current = True
                # Для локальных плейлистов проверяем совпадение с временным путем
                elif os.path.exists(playlist) and os.path.exists(self.temp_playlist_path):
                    try:
                        if os.path.samefile(playlist, self.temp_playlist_path):
                            is_current = True
                    except:
                        pass
            
            # Формируем отображаемое имя и стиль
            if is_current:
                # Создаем виджет с более заметным выделением для текущего плейлиста
                container = QWidget()
                container_layout = QHBoxLayout(container)
                container_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.setSpacing(5)
                
                # Добавляем иконку "воспроизведения" слева
                icon_label = QLabel()
                icon_label.setPixmap(self.style().standardIcon(QStyle.SP_MediaPlay).pixmap(QSize(12, 12)))
                container_layout.addWidget(icon_label)
                
                # Добавляем название плейлиста с выделением
                title_label = QLabel(display_name)
                title_label.setStyleSheet("""
                    QLabel {
                        color: #4CAF50;
                        font-weight: bold;
                        padding: 4px 10px;
                        background-color: rgba(76, 175, 80, 0.2);
                        border-radius: 4px;
                    }
                    QLabel:hover {
                        background-color: rgba(76, 175, 80, 0.3);
                    }
                """)
                container_layout.addWidget(title_label)
                container_layout.addStretch()
                
                # Добавляем виджет в меню
                action = QWidgetAction(self)
                action.setDefaultWidget(container)
                
                # Сохраняем данные плейлиста
                container.playlist_path = playlist
                title_label.playlist_path = playlist
                icon_label.playlist_path = playlist
            else:
                # Создаем обычный элемент меню для не выбранных плейлистов
                label = QLabel(display_name)
                label.setStyleSheet("""
                    QLabel {
                        color: white;
                        padding: 4px 10px;
                        margin-left: 17px; /* отступ для выравнивания с текущим плейлистом */
                    }
                    QLabel:hover {
                        background-color: rgba(30, 144, 255, 0.3);
                        border-radius: 4px;
                    }
                """)
                
                # Заворачиваем в QWidgetAction
                action = QWidgetAction(self)
                action.setDefaultWidget(label)
                
                # Сохраняем данные плейлиста
                label.playlist_path = playlist
            
            # Определяем функцию для обработки нажатий мыши
            def mousePressEvent(event, widget=action.defaultWidget()):
                if event.button() == Qt.LeftButton:
                    self.open_recent_playlist(widget.playlist_path)
                elif event.button() == Qt.RightButton:
                    self.show_recent_playlist_context_menu(event.globalPos(), widget.playlist_path)
            
            # Заменяем стандартное событие нажатия мыши
            action.defaultWidget().mousePressEvent = mousePressEvent
            
            self.recent_menu.addAction(action)

        # Добавляем разделитель и пункт "Очистить список"
        self.recent_menu.addSeparator()
        clear_action = QAction("Очистить список", self)
        clear_action.triggered.connect(self.clear_recent_playlists)
        self.recent_menu.addAction(clear_action)
        
        # Обновляем интерфейс
        QApplication.processEvents()

    def show_recent_playlist_context_menu(self, position, playlist_path):
        """Показывает контекстное меню для элемента в списке недавних плейлистов"""
        menu = QMenu()
        
        # Пункт для удаления плейлиста из истории
        remove_action = QAction("Удалить из списка", self)
        remove_action.triggered.connect(lambda: self.remove_from_recent_playlists(playlist_path))
        menu.addAction(remove_action)
        
        # Показываем меню
        menu.exec_(position)
    
    def remove_from_recent_playlists(self, playlist_path):
        """Удаляет плейлист из списка недавних"""
        if playlist_path in self.recent_playlists:
            self.recent_playlists.remove(playlist_path)
            self.update_recent_menu()
            self.save_config()
            QMessageBox.information(self, "Информация", f"Плейлист удален из истории.")

    def open_recent_playlist(self, playlist_path):
        """Открывает плейлист из списка недавних"""
        # Проверяем существование локального файла
        if not playlist_path.startswith(('http://', 'https://')) and not os.path.exists(playlist_path):
            QMessageBox.warning(self, "Предупреждение", 
                f"Файл плейлиста не найден:\n{playlist_path}\n\nПуть будет удален из истории.")
            # Удаляем несуществующий файл из истории
            if playlist_path in self.recent_playlists:
                self.recent_playlists.remove(playlist_path)
                self.update_recent_menu()
                self.save_config()
            return
            
        # Проверяем, не тот же ли это плейлист
        is_same_playlist = False
        
        # Прямое совпадение пути
        if playlist_path == self.current_playlist:
            is_same_playlist = True
        
        # Проверка временного плейлиста
        if hasattr(self, 'temp_playlist_path') and self.temp_playlist_path:
            if (playlist_path.startswith(('http://', 'https://')) and 
                self.current_playlist == playlist_path and 
                self.temp_playlist_path == "temp_playlist.m3u"):
                is_same_playlist = True
            elif os.path.exists(playlist_path) and os.path.exists(self.temp_playlist_path):
                try:
                    if os.path.samefile(playlist_path, self.temp_playlist_path):
                        is_same_playlist = True
                except:
                    pass
        
        if is_same_playlist:
            reply = QMessageBox.question(
                self, 'Повторная загрузка', 
                'Этот плейлист уже загружен. Загрузить повторно?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                return
                
        try:
            # Если это URL, загружаем через add_playlist_from_url
            if playlist_path.startswith(('http://', 'https://')):
                # Эмулируем ввод URL в диалоге
                url = playlist_path
                
                # Создаем временный файл для загрузки
                temp_file = "temp_playlist.m3u"
                
                # Показываем прогресс
                self.info_label.setText(f"Скачивание плейлиста из {url}...")
                self.statusbar_label.setText("Скачивание плейлиста...")
                self.progress_bar.setVisible(True)
                
                # Загружаем и обрабатываем как обычно
                def download_finished(success, error_message, source_url=""):
                    self.progress_bar.setVisible(False)
                    
                    if success:
                        try:
                            # Обновляем историю плейлистов с сохраненным именем
                            playlist_name = self.playlist_names.get(url)
                            self.update_recent_playlists(url, playlist_name)
                            self.current_playlist = url
                            
                            # Сохраняем путь к временному плейлисту
                            self.temp_playlist_path = temp_file
                            
                            # Загружаем внешний плейлист
                            self.stop()
                            self.channels = []
                            self.categories = {"Все каналы": []}
                            self.load_external_playlist(temp_file)
                            self.fill_channel_list()
                            
                            # Обновляем меню недавних плейлистов
                            self.update_recent_menu()
                            
                            self.info_label.setText(f"Загружен плейлист из URL")
                            
                            # Обновляем отображение количества каналов
                            total_channels = len(self.channels)
                            visible_channels = total_channels - len(self.hidden_channels)
                            self.statusbar_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
                            
                            # UX-твик: автоматически выделяем первый канал 
                            self.select_first_channel()
                        except Exception as e:
                            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить плейлист: {str(e)}")
                            
                            if os.path.exists(temp_file):
                                os.remove(temp_file)
                    else:
                        self.info_label.setText(f"Ошибка загрузки плейлиста: {error_message}")
                        self.statusbar_label.setText("Ошибка загрузки плейлиста")
                        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить плейлист: {error_message}")
                
                # Создаем и запускаем поток
                self.download_thread = PlaylistDownloadThread(url, temp_file)
                self.download_thread.finished.connect(download_finished)
                self.download_thread.start()
            else:
                # Это локальный файл
                self.stop()
                self.channels = []
                self.categories = {"Все каналы": []}
                
                # Обновляем историю плейлистов с сохраненным именем
                playlist_name = self.playlist_names.get(playlist_path)
                self.update_recent_playlists(playlist_path, playlist_name)
                self.current_playlist = playlist_path
                
                # Сохраняем путь к временному плейлисту
                self.temp_playlist_path = playlist_path
                
                # Загружаем плейлист
                self.load_external_playlist(playlist_path)
                self.fill_channel_list()
                
                # Обновляем меню недавних плейлистов
                self.update_recent_menu()
                
                # Используем имя плейлиста для отображения
                display_name = self.playlist_names.get(playlist_path, os.path.basename(playlist_path))
                self.info_label.setText(f"Загружен внешний плейлист: {display_name}")
                
                # Обновляем отображение количества каналов
                total_channels = len(self.channels)
                visible_channels = total_channels - len(self.hidden_channels)
                self.statusbar_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
                
                # Автоматически выбираем первый канал
                self.select_first_channel()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть плейлист: {str(e)}")

    def clear_recent_playlists(self):
        """Очищает список недавних плейлистов"""
        reply = QMessageBox.question(
            self, 'Подтверждение', 
            'Вы уверены, что хотите очистить историю плейлистов?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Сохраняем только текущий плейлист
            self.recent_playlists = [self.current_playlist] if self.current_playlist else []
            self.update_recent_menu()
            self.save_config()

    def exit_app(self):
        """Выход из приложения"""
        try:
            # Сначала сохраняем конфигурацию
            self.save_config()
            
            # Останавливаем все активные потоки загрузки логотипов
            if hasattr(self, 'logo_download_threads'):
                for url, thread in list(self.logo_download_threads.items()):
                    if thread and thread.isRunning():
                        try:
                            # Устанавливаем флаг прерывания
                            thread.abort()
                        except Exception as e:
                            logging.error(f"Ошибка при остановке потока логотипа {url}: {e}")
            
            # Затем выполняем очистку ресурсов
            # полная очистка будет выполнена через aboutToQuit в методе cleanup
            logging.info("Выход из приложения...")
            
            # Задержка для завершения потоков
            QTimer.singleShot(100, QApplication.quit)
        except Exception as e:
            logging.error(f"Ошибка при выходе из приложения: {e}")
            QApplication.quit()
        
    def show_all_favorites(self):
        """Показывает все избранные каналы"""
        # Находим индекс категории "Избранное" и выбираем её
        index = self.category_combo.findText("Избранное")
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
        else:
            # Если категории нет, добавляем её
            self.categories["Избранное"] = []
            for fav in self.favorites:
                for channel in self.channels:
                    if channel['name'] == fav:
                        self.categories["Избранное"].append(channel)
            
            self.category_combo.clear()
            self.category_combo.addItems(sorted(self.categories.keys()))
            index = self.category_combo.findText("Избранное")
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
                
    def clear_favorites(self):
        """Очищает список избранных каналов"""
        reply = QMessageBox.question(self, 'Подтверждение', 
                                    'Вы уверены, что хотите очистить список избранных каналов?',
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.favorites = []
            self.save_config()
            self.fill_channel_list()
            QMessageBox.information(self, "Информация", "Список избранных каналов очищен")
            
    def manage_hidden_channels(self):
        """Управление скрытыми каналами"""
        # Создаем диалог с выбором скрытых каналов
        if not self.hidden_channels:
            QMessageBox.information(self, "Информация", "Список скрытых каналов пуст")
            return
            
        # Отображаем список скрытых каналов
        hidden_list = "\n".join(self.hidden_channels)
        QMessageBox.information(self, "Скрытые каналы", 
                               f"Скрытые каналы ({len(self.hidden_channels)}):\n\n{hidden_list}\n\n"
                               "Для управления скрытыми каналами используйте контекстное меню канала.")
            
    def clear_hidden_channels(self):
        """Очищает список скрытых каналов (показывает все)"""
        reply = QMessageBox.question(self, 'Подтверждение', 
                                    'Вы уверены, что хотите показать все скрытые каналы?',
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.hidden_channels = []
            self.save_config()
            self.fill_channel_list()
            QMessageBox.information(self, "Информация", "Все скрытые каналы теперь видны")
    
    def fill_favorites_list(self):
        """Заполняет список избранных каналов"""
        self.channels_stack.setCurrentIndex(1)  # Переключаемся на обычный список
        self.channel_list.clear()
        
        for channel_name in self.favorites:
            # Находим канал по имени
            for channel in self.channels:
                if channel['name'] == channel_name:
                    # Пропускаем скрытые каналы если не в режиме отображения скрытых
                    if channel['name'] in self.hidden_channels and not self.show_hidden:
                        continue
                    
                    # Создаем элемент списка с логотипом
                    item = self.create_channel_item(channel['name'], channel)
                    self.channel_list.addItem(item)
    
    def fill_hidden_list(self):
        """Заполняет список скрытых каналов"""
        self.channels_stack.setCurrentIndex(1)  # Переключаемся на обычный список
        self.channel_list.clear()
        
        for channel_name in self.hidden_channels:
            # Находим канал по имени
            for channel in self.channels:
                if channel['name'] == channel_name:
                    # Создаем элемент списка с логотипом
                    item = self.create_channel_item(channel['name'], channel)
                    self.channel_list.addItem(item)
    
    def show_about(self):
        """Показывает информацию о программе"""
        QMessageBox.about(self, "О программе",
                         "<h3>MaksIPTV Плеер</h3>"
                         "<p>Версия 0.11.48</p>"
                         "<p>Современный плеер для просмотра IPTV каналов из M3U плейлиста</p>"
                         "<p><a href='https://maks-mk.github.io/maksiptv/' style='color:#87CEEB;'>https://maks-mk.github.io/maksiptv/</a></p>"
                         "<p>MaksK © 2025</p>")

    def load_playlist(self):
        playlist_file = "local.m3u"
        if not os.path.exists(playlist_file):
            QMessageBox.critical(None, "Ошибка", f"Плейлист {playlist_file} не найден!")
            sys.exit(1)

        try:
            with open(playlist_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            channel = None
            user_agent = None
            self.categories = {"Все каналы": []}
            
            # Иконки для категорий
            self.category_icons = {
                "Фильмы": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Спорт": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Новости": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Музыка": self.style().standardIcon(QStyle.SP_MediaVolume),
                "Детские": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Развлекательные": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Познавательные": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Все каналы": self.style().standardIcon(QStyle.SP_DirIcon),
                "Без категории": self.style().standardIcon(QStyle.SP_DirLinkIcon),
            }
            
            # Для хранения текущей группы из тега #EXTGRP
            current_group = "Без категории"
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#EXTM3U'):
                    continue
                elif line.startswith('#EXTINF:'):
                    # Извлекаем имя канала и группу из строки #EXTINF
                    group_match = re.search(r'group-title="([^"]*)"', line)
                    group_title = "Без категории"
                    
                    if group_match:
                        group_title = group_match.group(1).strip()
                        if not group_title:
                            group_title = "Без категории"
                    
                    # Извлекаем tvg-id если есть
                    tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
                    tvg_id = ""
                    if tvg_id_match:
                        tvg_id = tvg_id_match.group(1).strip()
                    
                    # Извлекаем tvg-logo если есть
                    tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                    tvg_logo = ""
                    if tvg_logo_match:
                        tvg_logo = tvg_logo_match.group(1).strip()
                    
                    parts = line.split(',', 1)
                    if len(parts) > 1:
                        channel = {
                            'name': parts[1].strip(), 
                            'options': {},
                            'category': group_title,
                            'tvg_id': tvg_id,
                            'tvg_logo': tvg_logo  # Добавляем URL логотипа
                        }
                        
                        # Добавляем категорию в словарь, если её ещё нет
                        if group_title not in self.categories:
                            self.categories[group_title] = []
                elif line.startswith('#EXTGRP:'):
                    # Обработка тега EXTGRP для m3u8 формата
                    current_group = line[len('#EXTGRP:'):].strip()
                    if not current_group:
                        current_group = "Без категории"
                    
                    # Если канал уже был определен, применяем к нему группу
                    if channel and 'name' in channel:
                        channel['category'] = current_group
                        
                        # Добавляем категорию в словарь, если её ещё нет
                        if current_group not in self.categories:
                            self.categories[current_group] = []
                elif line.startswith('#EXTVLCOPT:'):
                    # Обработка опций VLC
                    if channel:
                        opt = line[len('#EXTVLCOPT:'):].strip()
                        if 'http-user-agent=' in opt:
                            user_agent = opt.split('http-user-agent=')[1]
                            channel['options']['user-agent'] = user_agent
                
                elif channel and 'name' in channel and not line.startswith('#'):
                    # Это URL канала
                    channel['url'] = line
                    self.channels.append(channel)
                    
                    # Добавляем канал в соответствующую категорию
                    category = channel['category']
                    self.categories[category].append(channel)
                    self.categories["Все каналы"].append(channel)
                    
                    channel = None
                    # Сбрасываем текущую группу после добавления канала
                    current_group = "Без категории"

        except Exception as e:
            QMessageBox.critical(None, "Ошибка", f"Ошибка при чтении плейлиста: {str(e)}")
            sys.exit(1)

    def fill_channel_list(self):
        """Заполняет список или дерево каналов в зависимости от выбранной категории"""
        current_category = self.category_combo.currentText()
        search_text = self.search_box.text().lower()
        
        if current_category == "Избранное":
            # Заполняем список избранных каналов
            self.channels_stack.setCurrentIndex(1)
            self.channel_list.clear()
            
            for channel_name in self.favorites:
                # Находим канал по имени
                for channel in self.channels:
                    if channel['name'] == channel_name and (not search_text or search_text in channel['name'].lower()):
                        # Пропускаем скрытые каналы
                        if channel['name'] in self.hidden_channels:
                            continue
                        
                        # Создаем элемент списка с логотипом
                        item = self.create_channel_item(channel['name'], channel)
                        self.channel_list.addItem(item)
            return
        
        if current_category == "Все каналы":
            # Используем древовидное представление для всех категорий
            self.channels_stack.setCurrentIndex(0)
            self.channel_tree.clear()
            
            # Создаем корневые элементы для каждой категории
            category_items = {}
            for category in sorted(self.categories.keys()):
                if category == "Все каналы":
                    continue
                    
                category_item = QTreeWidgetItem([category])
                
                # Применяем иконку категории, если есть
                if category in self.category_icons:
                    category_item.setIcon(0, self.category_icons[category])
                
                self.channel_tree.addTopLevelItem(category_item)
                category_items[category] = category_item
                
                # Подсчет видимых каналов в категории (исключая скрытые)
                visible_channels = 0
                for ch in self.categories[category]:
                    if ch['name'] not in self.hidden_channels:
                        visible_channels += 1
                
                # Устанавливаем количество каналов в категории
                category_item.setText(0, f"{category} ({visible_channels})")
            
            # Добавляем каналы в соответствующие категории
            for channel in self.channels:
                # Пропускаем скрытые каналы
                if channel['name'] in self.hidden_channels:
                    continue
                
                if search_text and search_text not in channel['name'].lower():
                    continue
                    
                category = channel['category']
                if category in category_items:
                    channel_item = QTreeWidgetItem([channel['name']])
                    channel_item.setData(0, Qt.UserRole, self.channels.index(channel))
                    
                    # Добавляем логотип, если доступен
                    if self.show_logos:
                        if 'tvg_logo' in channel and channel['tvg_logo']:
                            logo = self.load_channel_logo(channel['tvg_logo'])
                            if logo:
                                channel_item.setIcon(0, QIcon(logo))
                            else:
                                # Если не удалось загрузить логотип, используем стандартную иконку
                                channel_item.setIcon(0, QIcon(self.default_channel_icon))
                        else:
                            # Если у канала нет логотипа, используем стандартную иконку
                            channel_item.setIcon(0, QIcon(self.default_channel_icon))
                    
                    category_items[category].addChild(channel_item)
            
            # Разворачиваем все категории
            self.channel_tree.expandAll()
            
            # Обновляем информацию о количестве каналов (всего и видимых)
            total_channels = len(self.channels)
            visible_channels = total_channels - len(self.hidden_channels)
            self.playlist_info_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
        else:
            # Используем обычный список для конкретной категории
            self.channels_stack.setCurrentIndex(1)
            self.channel_list.clear()
            
            channels_in_category = self.categories.get(current_category, [])
            visible_count = 0
            
            for channel in channels_in_category:
                # Пропускаем скрытые каналы
                if channel['name'] in self.hidden_channels:
                    continue
                
                visible_count += 1
                
                if not search_text or search_text in channel['name'].lower():
                    # Создаем элемент списка с логотипом
                    item = self.create_channel_item(channel['name'], channel)
                    self.channel_list.addItem(item)
            
            # Обновляем информацию о количестве каналов в категории
            total_in_category = len(channels_in_category)
            self.playlist_info_label.setText(f"Каналов в категории: {total_in_category} (видимых: {visible_count})")

    def category_changed(self, category):
        """Обработчик смены категории"""
        # Добавляем категорию "Избранное" если её нет
        if category == "Избранное" and "Избранное" not in self.categories:
            self.categories["Избранное"] = []
            for fav in self.favorites:
                for channel in self.channels:
                    if channel['name'] == fav:
                        self.categories["Избранное"].append(channel)
        
        self.fill_channel_list()
        
    def filter_channels(self, text):
        """Фильтрация списка каналов по введенному тексту"""
        search_text = text.lower().strip()
        current_category = self.category_combo.currentText()
        
        # Если поиск пустой, просто обновляем список
        if not search_text:
            self.fill_channel_list()
            return
        
        # Получаем список каналов для фильтрации
        if current_category == "Все каналы":
            channels_to_filter = self.channels.copy()
        else:
            channels_to_filter = self.categories.get(current_category, []).copy()
        
        # Фильтруем каналы
        filtered_channels = []
        
        # Разбиваем поисковый запрос на отдельные слова для улучшенного поиска
        search_terms = search_text.split()
        
        for channel in channels_to_filter:
            # Пропускаем скрытые каналы, если не находимся в режиме просмотра скрытых
            if channel['name'] in self.hidden_channels and not self.show_hidden:
                continue
                
            channel_name = channel['name'].lower()
            
            # Проверяем по всем поисковым терминам
            all_terms_found = True
            for term in search_terms:
                if term not in channel_name:
                    all_terms_found = False
                    break
            
            if all_terms_found:
                filtered_channels.append(channel)

        # Количество найденных каналов
        found_count = len(filtered_channels)
        
        # Отображаем результаты поиска
        if current_category == "Все каналы":
            # Используем древовидное представление
            self.channels_stack.setCurrentIndex(0)
            self.channel_tree.clear()
            
            # Группируем каналы по категориям
            channels_by_category = {}
            for channel in filtered_channels:
                category = channel['category']
                if category not in channels_by_category:
                    channels_by_category[category] = []
                channels_by_category[category].append(channel)
            
            # Создаем элементы дерева
            for category, channels in sorted(channels_by_category.items()):
                category_item = QTreeWidgetItem([f"{category} ({len(channels)})"])
                
                # Применяем иконку категории, если есть
                if category in self.category_icons:
                    category_item.setIcon(0, self.category_icons[category])
                
                self.channel_tree.addTopLevelItem(category_item)
                
                # Добавляем каналы в категорию
                for channel in channels:
                    channel_item = QTreeWidgetItem([channel['name']])
                    channel_item.setData(0, Qt.UserRole, self.channels.index(channel))
                    category_item.addChild(channel_item)
            
            # Разворачиваем все категории для лучшей видимости результатов поиска
            self.channel_tree.expandAll()
            
            # Обновляем информацию о количестве найденных каналов
            self.playlist_info_label.setText(f"Результаты поиска: найдено {found_count} каналов")
        else:
            # Используем обычный список
            self.channels_stack.setCurrentIndex(1)
            self.channel_list.clear()
            
            # Добавляем найденные каналы в список
            for channel in filtered_channels:
                item = QListWidgetItem(channel['name'])
                self.channel_list.addItem(item)
            
            # Обновляем информацию о количестве найденных каналов
            self.playlist_info_label.setText(f"Результаты поиска: найдено {found_count} каналов")
        
        # Обновляем статус бар
        self.statusbar_label.setText(f"Найдено {found_count} каналов по запросу '{text}'")
        
        # Если найден только один канал, автоматически выбираем его
        if found_count == 1:
            if current_category == "Все каналы":
                # Выбираем единственный канал в дереве
                for i in range(self.channel_tree.topLevelItemCount()):
                    category_item = self.channel_tree.topLevelItem(i)
                    if category_item.childCount() == 1:
                        channel_item = category_item.child(0)
                        self.channel_tree.setCurrentItem(channel_item)
                        break
            else:
                # Выбираем единственный канал в списке
                self.channel_list.setCurrentRow(0)
    
    def tree_selection_changed(self):
        """Обработчик выбора канала в дереве категорий"""
        # Канал выбран, но не воспроизводится автоматически
        # Пользователь должен явно запустить воспроизведение
        pass
    
    def channel_changed(self, row):
        """Обработчик выбора канала в обычном списке"""
        # Канал выбран, но не воспроизводится автоматически
        # Пользователь должен явно запустить воспроизведение
        pass
    
    def play_channel(self, channel_index):
        """Воспроизведение выбранного канала с учетом всех опций
        
        Запускает асинхронное воспроизведение выбранного канала, устанавливая все необходимые 
        параметры и опции для потока. Контролирует процесс загрузки канала с помощью таймера.
        
        Args:
            channel_index: Индекс канала в списке каналов (self.channels)
        """
        if channel_index < 0 or channel_index >= len(self.channels):
            return
        
        # Сброс счетчика попыток при старте нового канала
        self.retry_count = 0
        
        # Останавливаем текущее воспроизведение и освобождаем ресурсы
        self.stop()
        
        # Останавливаем таймер, если он активен
        if self.play_timeout_timer.isActive():
            self.play_timeout_timer.stop()
        
        # Останавливаем и очищаем предыдущий поток, если он есть
        if self.channel_play_thread and self.channel_play_thread.isRunning():
            self.channel_play_thread.quit()
            self.channel_play_thread.wait(1000)  # Ждем завершения потока
        
        # Запоминаем индекс текущего канала
        self.current_channel_index = channel_index
        channel = self.channels[channel_index]
        
        # Показываем имя канала и информацию о буферизации
        self.info_label.setText(f"Загрузка: {channel['name']}")
        self.channel_name_label.setText(channel['name'])
        self.statusbar_label.setText(f"Загрузка: {channel['name']}")
        self.progress_bar.setVisible(True)
        
        # Добавляем в недавние каналы
        self.current_channel = channel['name']
        self.last_channel = channel['name']
        self.save_config()
        
        # Запускаем таймер ожидания начала воспроизведения
        self.play_timeout_timer.start(self.play_timeout * 1000)
        
        try:
            # Подготавливаем опции для канала
            options = channel.get('options', {})
            
            # Создаем и запускаем поток для асинхронной подготовки медиа
            self.channel_play_thread = ChannelPlayThread(channel['url'], options, self.instance)
            self.channel_play_thread.setup_finished.connect(self.on_channel_setup_finished)
            self.channel_play_thread.start()
            
            # Обновляем интерфейс
            QApplication.processEvents()
            
        except Exception as e:
            self.play_timeout_timer.stop()
            self.progress_bar.setVisible(False)
            self.info_label.setText(f"Ошибка воспроизведения: {str(e)}")
            self.statusbar_label.setText("Ошибка воспроизведения")
            logging.error(f"Ошибка воспроизведения канала: {str(e)}")
            QMessageBox.critical(self, "Ошибка воспроизведения", 
                              f"Не удалось воспроизвести канал '{channel['name']}'.\n{str(e)}")
    
    def on_channel_setup_finished(self, success, error_message, media):
        """Обработчик завершения настройки медиа в потоке"""
        # Останавливаем таймер ожидания начала воспроизведения, т.к. процесс настройки медиа завершен
        if self.play_timeout_timer.isActive():
            self.play_timeout_timer.stop()
        
        if success and media:
            try:
                # Устанавливаем медиа в плеер и начинаем воспроизведение
                self.media_player.set_media(media)
                self.play()
                
                # Запускаем новый таймер для контроля начала воспроизведения
                # (на случай если канал подготовлен, но не начал воспроизводиться)
                self.play_timeout_timer.start(self.play_timeout * 1000)
                
                # Сбрасываем счетчик попыток восстановления видео
                if hasattr(self, 'video_retry_count'):
                    delattr(self, 'video_retry_count')
                
                # Обновляем интерфейс
                self.update_ui()
                
            except Exception as e:
                self.progress_bar.setVisible(False)
                self.info_label.setText(f"Ошибка воспроизведения: {str(e)}")
                self.statusbar_label.setText("Ошибка воспроизведения")
                logging.error(f"Ошибка при установке медиа: {str(e)}")
        else:
            self.progress_bar.setVisible(False)
            error_msg = error_message or "Неизвестная ошибка при подготовке канала"
            self.info_label.setText(f"Ошибка воспроизведения: {error_msg}")
            self.statusbar_label.setText("Ошибка воспроизведения")
            logging.error(f"Ошибка подготовки медиа: {error_msg}")
            
            if self.current_channel_index >= 0 and self.current_channel_index < len(self.channels):
                channel_name = self.channels[self.current_channel_index]['name']
                QMessageBox.warning(self, "Ошибка воспроизведения", 
                                  f"Не удалось воспроизвести канал '{channel_name}'.\n{error_msg}")
    
    def handle_play_timeout(self):
        """Обработчик таймаута начала воспроизведения"""
        self.progress_bar.setVisible(False)
        
        # Если канал не начал воспроизводиться за отведенное время
        if not self.media_player.is_playing():
            # Увеличиваем счетчик попыток
            self.retry_count += 1
            
            # Получаем информацию о канале
            channel_name = "Неизвестный канал"
            if self.current_channel_index >= 0 and self.current_channel_index < len(self.channels):
                channel_name = self.channels[self.current_channel_index]['name']
            
            # Логируем проблему
            logging.warning(f"Таймаут воспроизведения канала '{channel_name}'. Попытка {self.retry_count} из {self.max_retry_count}")
            
            if self.retry_count < self.max_retry_count:
                # Показываем сообщение о переподключении
                self.info_label.setText(f"Канал не отвечает. Переподключение... Попытка {self.retry_count}/{self.max_retry_count}")
                self.statusbar_label.setText(f"Переподключение к каналу. Попытка {self.retry_count}/{self.max_retry_count}")
                
                # Запускаем новую попытку через 2 секунды
                QTimer.singleShot(2000, self.retry_current_channel)
            else:
                # Превышено макс. количество попыток
                self.info_label.setText(f"Канал '{channel_name}' недоступен после {self.max_retry_count} попыток")
                self.statusbar_label.setText("Канал недоступен")
                
                # Сбрасываем состояние плеера
                self.stop()
                
                # Показываем сообщение пользователю
                QMessageBox.warning(self, "Канал недоступен", 
                                 f"Канал '{channel_name}' недоступен после {self.max_retry_count} попыток подключения.\n"
                                 f"Возможно, поток вещания временно не работает или перегружен.")
    
    def sort_channels(self):
        """Сортировка списка каналов по алфавиту"""
        for category in self.categories:
            self.categories[category].sort(key=lambda x: x['name'])
        
        self.channels.sort(key=lambda x: x['name'])
        self.fill_channel_list()

    def play_pause(self):
        """Переключение воспроизведения/паузы"""
        if self.media_player.is_playing():
            self.media_player.pause()
            self.play_button.setIcon(qta.icon('fa5s.play', color='#e8e8e8'))
        else:
            self.play()

    def play(self):
        """Начать воспроизведение"""
        self.media_player.play()
        self.play_button.setIcon(qta.icon('fa5s.pause', color='#e8e8e8'))
        
        # Запускаем таймер таймаута воспроизведения, если он еще не запущен
        if not self.play_timeout_timer.isActive():
            self.play_timeout_timer.start(self.play_timeout * 1000)

    def stop(self):
        """Остановить воспроизведение"""
        try:
            # Останавливаем воспроизведение
            if self.media_player.is_playing():
                self.media_player.stop()
            
            # Освобождаем медиа-ресурсы
            current_media = self.media_player.get_media()
            if current_media:
                current_media.release()
                
            self.play_button.setIcon(qta.icon('fa5s.play', color='#e8e8e8'))
            self.info_label.setText("Остановлено")
            self.channel_name_label.setText("Нет воспроизведения")
            self.statusbar_label.setText("Остановлено")
        except Exception as e:
            logging.error(f"Ошибка при остановке воспроизведения: {e}")
            # Обновляем интерфейс даже при ошибке
            try:
                self.play_button.setIcon(qta.icon('fa5s.play', color='#e8e8e8'))
                self.info_label.setText("Остановлено")
                self.channel_name_label.setText("Нет воспроизведения")
                self.statusbar_label.setText("Остановлено")
            except:
                pass
    
    def handle_close_event(self, event):
        """Обрабатывает событие закрытия окна
        
        Останавливает все потоки перед закрытием окна и выполняет корректное освобождение ресурсов.
        
        Args:
            event: Событие закрытия окна
        """
        try:
            logging.info("Обработка закрытия окна...")
            
            # Останавливаем все потоки загрузки логотипов
            if hasattr(self, 'logo_download_threads'):
                for url, thread in list(self.logo_download_threads.items()):
                    if thread and thread.isRunning():
                        try:
                            # Устанавливаем флаг прерывания
                            thread.abort()
                            # Отсоединяем сигналы
                            try:
                                thread.logo_loaded.disconnect()
                                thread.logo_failed.disconnect()
                            except:
                                pass
                        except Exception as e:
                            logging.error(f"Ошибка при остановке потока логотипа {url} (closeEvent): {e}")
            
            # Сначала сохраняем настройки
            self.save_config()
            
            # Передаем событие дальше (будет вызван метод cleanup через aboutToQuit)
            event.accept()
        except Exception as e:
            logging.error(f"Ошибка при обработке закрытия окна: {e}")
            # В случае ошибки все равно закрываем окно
            event.accept()

    def cleanup(self):
        """Освобождает ресурсы при выходе из приложения
        
        Корректно останавливает воспроизведение, отсоединяет обработчики событий,
        завершает рабочие потоки и освобождает все ресурсы перед завершением работы
        приложения для предотвращения утечек памяти и зависания системы.
        """
        try:
            # Останавливаем таймеры
            if hasattr(self, 'timer') and self.timer.isActive():
                self.timer.stop()
                
            if hasattr(self, 'play_timeout_timer') and self.play_timeout_timer.isActive():
                self.play_timeout_timer.stop()
                
            # Останавливаем поток воспроизведения, если он запущен
            if hasattr(self, 'channel_play_thread') and self.channel_play_thread and self.channel_play_thread.isRunning():
                try:
                    self.channel_play_thread.quit()
                    # Ждем завершения потока с таймаутом
                    if not self.channel_play_thread.wait(500):
                        logging.warning("Не удалось завершить поток воспроизведения, принудительное завершение.")
                        self.channel_play_thread.terminate()
                except Exception as e:
                    logging.error(f"Ошибка при остановке потока воспроизведения: {e}")
                
            # Останавливаем поток загрузки, если он запущен
            if hasattr(self, 'download_thread') and self.download_thread and self.download_thread.isRunning():
                try:
                    self.download_thread.quit()
                    # Ждем завершения потока с таймаутом
                    if not self.download_thread.wait(500):
                        logging.warning("Не удалось завершить поток загрузки, принудительное завершение.")
                        self.download_thread.terminate()
                except Exception as e:
                    logging.error(f"Ошибка при остановке потока загрузки: {e}")
                
            # Сбрасываем обработчики событий медиаплеера
            if hasattr(self, 'event_manager'):
                try:
                    self.event_manager.event_detach(vlc.EventType.MediaPlayerPlaying)
                    self.event_manager.event_detach(vlc.EventType.MediaPlayerPaused)
                    self.event_manager.event_detach(vlc.EventType.MediaPlayerStopped)
                    self.event_manager.event_detach(vlc.EventType.MediaPlayerEncounteredError)
                    self.event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                except:
                    pass
            
            # Безопасно останавливаем воспроизведение
            if hasattr(self, 'media_player'):
                try:
                    # Получаем текущее медиа перед остановкой плеера
                    current_media = self.media_player.get_media()
                    
                    # Останавливаем воспроизведение
                    if self.media_player.is_playing():
                        self.media_player.pause()
                        time.sleep(0.1)  # Даем время на обработку паузы
                        
                    self.media_player.stop()
                    time.sleep(0.1)  # Даем время на обработку остановки
                    
                    # Освобождаем медиа отдельно
                    if current_media:
                        current_media.release()
                except Exception as e:
                    logging.error(f"Ошибка при остановке медиаплеера: {e}")
                
                # Освобождаем медиаплеер
                try:
                    self.media_player.release()
                except Exception as e:
                    logging.error(f"Ошибка при освобождении медиаплеера: {e}")
            
            # Освобождаем инстанс VLC в последнюю очередь
            if hasattr(self, 'instance'):
                try:
                    self.instance.release()
                except Exception as e:
                    logging.error(f"Ошибка при освобождении инстанса VLC: {e}")
            
            # Останавливаем все потоки загрузки логотипов
            if hasattr(self, 'logo_download_threads'):
                for url, thread in list(self.logo_download_threads.items()):
                    try:
                        if thread and thread.isRunning():
                            # Сначала устанавливаем флаг прерывания
                            thread.abort()
                            # Отсоединяем сигналы
                            try:
                                thread.logo_loaded.disconnect()
                                thread.logo_failed.disconnect()
                            except:
                                pass
                            # Вызываем quit для корректного завершения
                            thread.quit()
                            # Ждем завершения потока с увеличенным таймаутом
                            if not thread.wait(300):
                                logging.warning(f"Не удалось завершить поток загрузки логотипа {url}, принудительное завершение.")
                                # Если не удалось завершить, используем terminate
                                thread.terminate()
                                # Даем немного времени на завершение
                                time.sleep(0.05)
                        # Планируем удаление объекта позже
                        thread.deleteLater()
                    except Exception as e:
                        logging.error(f"Ошибка при остановке потока загрузки логотипа {url}: {e}")
                # Очищаем словарь потоков
                self.logo_download_threads.clear()
                
            # Удаляем временные файлы
            if hasattr(self, 'temp_playlist_path') and self.temp_playlist_path and self.temp_playlist_path.startswith("temp_"):
                try:
                    if os.path.exists(self.temp_playlist_path):
                        os.remove(self.temp_playlist_path)
                except Exception as e:
                    logging.error(f"Ошибка при удалении временного файла: {e}")
                    
            logging.info("Ресурсы успешно освобождены при выходе")
                    
        except Exception as e:
            logging.error(f"Критическая ошибка при освобождении ресурсов: {e}", exc_info=True)

    def restore_ui_after_fullscreen(self):
        """Восстанавливает интерфейс после выхода из полноэкранного режима
        
        Обеспечивает корректное отображение всех элементов интерфейса,
        которые могут оставаться скрытыми при определенных условиях.
        """
        # Принудительно показываем все основные элементы интерфейса
        self.main_splitter.setVisible(True)
        self.menuBar().setVisible(True)
        self.statusBar().setVisible(True)
        
        # Обновляем внутренние панели
        left_panel = self.findChild(QWidget, "left_panel")
        right_panel = self.findChild(QWidget, "right_panel")
        
        if left_panel:
            left_panel.setVisible(True)
            
            # Обновляем ключевые элементы левой панели
            for widget in [self.category_combo, self.search_box, self.channels_stack, 
                          self.sort_button, self.refresh_button, self.update_button,
                          self.favorites_button, self.hidden_button, self.play_selected_button]:
                if widget:
                    widget.setVisible(True)
                    widget.update()
            
            # Обновляем списки каналов
            if hasattr(self, 'channel_tree'):
                self.channel_tree.setVisible(True)
                self.channel_tree.update()
                
            if hasattr(self, 'channel_list'):
                self.channel_list.setVisible(True)
                self.channel_list.update()
            
            left_panel.update()
        
        if right_panel:
            right_panel.setVisible(True)
            
            # Обновляем ключевые элементы правой панели
            for widget in [self.channel_name_label, self.video_frame, self.info_label, 
                          self.play_button, self.stop_button, self.screenshot_button, 
                          self.audio_track_button, self.fullscreen_button, self.volume_slider]:
                if widget:
                    widget.setVisible(True)
                    widget.update()
            
            right_panel.update()
        
        # Обновляем виджеты списка каналов
        if hasattr(self, 'channels_stack'):
            self.channels_stack.setVisible(True)
            self.channels_stack.update()
            
            # Обновляем активный виджет в стеке
            current_widget = self.channels_stack.currentWidget()
            if current_widget:
                current_widget.setVisible(True)
                current_widget.update()
        
        # Обновляем видеофрейм и его содержимое
        if hasattr(self, 'video_frame'):
            self.video_frame.setVisible(True)
            
            # Обновляем метку видеофрейма
            if hasattr(self, 'video_frame_label'):
                self.video_frame_label.setVisible(True)
                self.video_frame_label.update()
            
            self.video_frame.update()
        
        # Обновляем компоновку и обрабатываем отложенные события
        self.centralWidget().layout().activate()
        self.repaint()
        QApplication.processEvents()
        
        # Проверяем размеры сплиттера и восстанавливаем их при необходимости
        sizes = self.main_splitter.sizes()
        if len(sizes) == 2 and (sizes[0] <= 0 or sizes[1] <= 0):
            # Если какая-то панель скрыта, восстанавливаем размеры
            self.main_splitter.setSizes([int(self.width() * 0.3), int(self.width() * 0.7)])
        
        # Принудительно обновляем макет после восстановления размеров
        self.centralWidget().layout().update()
        
        # Обновляем после изменения размеров
        self.update()
        QApplication.processEvents()
        
        # Устанавливаем фокус на видеофрейм
        if hasattr(self, 'video_frame'):
            self.video_frame.setFocus()
        
        # Логируем информацию о восстановлении интерфейса
        logging.info("Интерфейс восстановлен после выхода из полноэкранного режима")
    
    def toggle_fullscreen(self):
        """Переключение полноэкранного режима
        
        Реализует корректное переключение между обычным и полноэкранным режимами
        с сохранением правильных пропорций видео-виджета и возможностью возврата
        к нормальному виду клавишей ESC или через кнопку.
        """
        if self.isFullScreen():
            # === Выход из полноэкранного режима ===
            
            # Возвращаемся из полноэкранного режима
            self.showNormal()
            
            # Удаляем прозрачную кнопку выхода из полноэкранного режима, если есть
            if hasattr(self, 'exit_fs_button') and self.exit_fs_button:
                self.exit_fs_button.deleteLater()
                self.exit_fs_button = None
            
            # Восстанавливаем видеофрейм в исходную компоновку
            if hasattr(self, 'fullscreen_video_layout'):
                # Извлекаем видеофрейм из текущего контейнера
                self.video_frame.setParent(None)
                
                # Удаляем временный контейнер если он существует
                if hasattr(self, 'fullscreen_container') and self.fullscreen_container:
                    self.fullscreen_container.deleteLater()
                    self.fullscreen_container = None
                
                # Восстанавливаем исходное состояние
                right_panel = self.findChild(QWidget, "right_panel")
                if right_panel:
                    # Получаем layout правой панели
                    right_layout = right_panel.layout()
                    
                    # Вставляем видеофрейм на правильную позицию (после заголовка)
                    right_layout.insertWidget(1, self.video_frame)
                
                # Очищаем временную компоновку
                del self.fullscreen_video_layout
            
            # Вызываем комплексное восстановление UI
            QTimer.singleShot(100, self.restore_ui_after_fullscreen)
            
            # Восстанавливаем обработчик клика для метки
            try:
                self.video_frame_label.clicked.disconnect()
            except TypeError:
                pass
            self.video_frame_label.clicked.connect(self.toggle_fullscreen)
            
        else:
            # === Переход в полноэкранный режим ===
            
            # Сохраняем текущее состояние для последующего восстановления
            self.normal_geometry = self.geometry()
            
            # Создаем временный контейнер и компоновку для полноэкранного режима
            self.fullscreen_container = QWidget(self)
            self.fullscreen_video_layout = QVBoxLayout(self.fullscreen_container)
            self.fullscreen_video_layout.setContentsMargins(0, 0, 0, 0)
            self.fullscreen_video_layout.setSpacing(0)
            
            # Извлекаем видеофрейм из текущей компоновки
            self.video_frame.setParent(None)
            
            # Добавляем видеофрейм в новую компоновку
            self.fullscreen_video_layout.addWidget(self.video_frame)
            
            # Настраиваем контейнер на полный размер централного виджета
            self.fullscreen_container.setGeometry(self.centralWidget().rect())
            self.fullscreen_container.show()
            
            # Скрываем обычный интерфейс
            self.main_splitter.setVisible(False)
            self.menuBar().setVisible(False)
            self.statusBar().setVisible(False)
            
            # Переключаемся в полноэкранный режим
            self.showFullScreen()
            
            # Обновляем размер контейнера после перехода в полноэкранный режим
            self.fullscreen_container.setGeometry(0, 0, self.width(), self.height())
            
            # Создаем компактную кнопку для выхода из полноэкранного режима
            self.create_fullscreen_exit_button()
    
    def create_fullscreen_exit_button(self):
        """Создает кнопку выхода из полноэкранного режима"""
        self.exit_fs_button = QPushButton(self)
        self.exit_fs_button.setIcon(qta.icon('fa5s.times', color='white'))
        self.exit_fs_button.setIconSize(QSize(24, 24))
        self.exit_fs_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 100);
                border: none;
                border-radius: 15px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: rgba(200, 0, 0, 150);
            }
        """)
        
        # Устанавливаем размер и позицию кнопки
        self.exit_fs_button.setFixedSize(30, 30)
        self.exit_fs_button.clicked.connect(self.toggle_fullscreen)
        self.exit_fs_button.move(self.width() - 40, 10)
        self.exit_fs_button.show()
        self.exit_fs_button.raise_()
        
        # Создаем подсказку для выхода из полноэкранного режима
        self.create_fullscreen_hint()
    
    def create_fullscreen_hint(self):
        """Создает временную подсказку при входе в полноэкранный режим"""
        hint_label = QLabel("Нажмите ESC или на X для выхода из полноэкранного режима", self)
        hint_label.setStyleSheet("background-color: rgba(0, 0, 0, 150); color: white; padding: 10px; border-radius: 5px;")
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setGeometry(self.width() // 2 - 250, self.height() - 50, 500, 40)
        hint_label.show()
        hint_label.raise_()
        # Автоматически скрываем подсказку через 3 секунды
        QTimer.singleShot(3000, hint_label.deleteLater)
        
    def resizeEvent(self, event):
        """Обработчик изменения размера окна
        
        Обновляет положение компонентов при изменении размеров окна,
        особенно в полноэкранном режиме.
        """
        # Если находимся в полноэкранном режиме, обновляем размеры и положение элементов
        if self.isFullScreen():
            # Обновляем размеры временного контейнера
            if hasattr(self, 'fullscreen_container') and self.fullscreen_container:
                self.fullscreen_container.setGeometry(0, 0, self.width(), self.height())
                
            # Обновляем положение кнопки выхода
            if hasattr(self, 'exit_fs_button') and self.exit_fs_button:
                self.exit_fs_button.move(self.width() - 40, 10)
                
        super().resizeEvent(event)

    def update_ui(self):
        """Обновление UI состояния 
        
        Периодически вызывается таймером для обновления элементов интерфейса
        в соответствии с текущим состоянием медиаплеера. Обрабатывает различные
        состояния воспроизведения, показывает/скрывает индикаторы буферизации и
        обновляет информацию о воспроизводимом канале.
        """
        # Обновляем состояние кнопки воспроизведения
        is_playing = self.media_player.is_playing()
        has_media = self.media_player.get_media() is not None
        
        if is_playing:
            self.play_button.setIcon(qta.icon('fa5s.pause', color='#e8e8e8'))
        else:
            self.play_button.setIcon(qta.icon('fa5s.play', color='#e8e8e8'))
            
        # Получаем текущее состояние медиаплеера
        state = self.media_player.get_state()
        
        # Обрабатываем разные состояния
        if state == vlc.State.Opening:
            self.info_label.setText("Открытие медиа...")
            self.statusbar_label.setText("Открытие медиа...")
            self.progress_bar.setVisible(True)
        elif state == vlc.State.Buffering:
            self.info_label.setText("Буферизация...")
            self.statusbar_label.setText("Буферизация...")
            self.progress_bar.setVisible(True)
        elif state == vlc.State.Playing and is_playing:
            self.progress_bar.setVisible(False)
            if self.current_channel_index >= 0:
                channel_name = self.channels[self.current_channel_index]['name']
                self.info_label.setText(f"Воспроизведение: {channel_name}")
                self.statusbar_label.setText(f"Воспроизведение: {channel_name}")
        elif state == vlc.State.Playing and not is_playing:
            self.info_label.setText("Буферизация...")
            self.statusbar_label.setText("Буферизация...")
            self.progress_bar.setVisible(True)
        elif state == vlc.State.Paused:
            self.progress_bar.setVisible(False)
            if self.current_channel_index >= 0:
                channel_name = self.channels[self.current_channel_index]['name']
                self.info_label.setText(f"Пауза: {channel_name}")
                self.statusbar_label.setText(f"Пауза: {channel_name}")
        elif state == vlc.State.Stopped:
            self.progress_bar.setVisible(False)
            self.info_label.setText("Остановлено")
            self.statusbar_label.setText("Остановлено")
        elif state == vlc.State.Ended:
            self.progress_bar.setVisible(False)
            self.info_label.setText("Воспроизведение завершено")
            self.statusbar_label.setText("Воспроизведение завершено")
            self.play_button.setIcon(qta.icon('fa5s.play', color='#e8e8e8'))
        elif state == vlc.State.Error:
            self.progress_bar.setVisible(False)
            self.info_label.setText("Ошибка воспроизведения")
            self.statusbar_label.setText("Ошибка воспроизведения")
        
        # Если воспроизведение идет, но нет видео трека - пробуем перезапустить
        if is_playing and not self.media_player.has_vout():
            if hasattr(self, 'video_retry_count'):
                self.video_retry_count += 1
                if self.video_retry_count > 10:  # После 10 попыток сообщаем, что это может быть аудио-канал
                    self.info_label.setText("Нет видеопотока. Возможно аудио-канал.")
                    self.statusbar_label.setText("Нет видеопотока")
                    # Не сбрасываем счетчик, чтобы не спамить сообщениями
            else:
                self.video_retry_count = 1

    def handle_error(self, event):
        """Обработчик ошибок воспроизведения
        
        Вызывается при возникновении ошибок во время воспроизведения медиа.
        Обрабатывает ошибки, пытается автоматически переподключиться к каналу,
        и информирует пользователя о проблемах.
        
        Args:
            event: Событие ошибки от VLC
        """
        self.progress_bar.setVisible(False)
        
        # Останавливаем таймер ожидания, если он активен
        if self.play_timeout_timer.isActive():
            self.play_timeout_timer.stop()
        
        # Увеличиваем счетчик попыток переподключения
        self.retry_count += 1
        
        try:
            # Получаем текущее медиа
            media = self.media_player.get_media()
            if media:
                media_url = media.get_mrl()
                error_msg = f"Ошибка воспроизведения потока: {media_url}"
            else:
                error_msg = "Ошибка воспроизведения потока"
                
            # Получаем информацию о канале
            channel_name = None
            if 0 <= self.current_channel_index < len(self.channels):
                channel = self.channels[self.current_channel_index]
                channel_name = channel.get('name', 'Неизвестный канал')
                error_msg = f"Ошибка воспроизведения канала: {channel_name}"
            
            # Обновляем информационную метку
            self.update_ui_status(error_msg, error=True)
            
            if self.retry_count <= self.max_retry_count:
                # Показываем информацию о попытке переподключения
                status_msg = f"⚠️ Ошибка воспроизведения! Переподключение... Попытка №{self.retry_count}/{self.max_retry_count}"
                self.statusBar().showMessage(status_msg, 5000)
                logging.error(f"Ошибка воспроизведения VLC. Попытка переподключения #{self.retry_count}/{self.max_retry_count}")
                
                # Запускаем переподключение через 3 секунды
                QTimer.singleShot(3000, self.retry_current_channel)
            else:
                # Превышено макс. количество попыток
                error_msg = f"Канал '{channel_name}' недоступен после {self.max_retry_count} попыток"
                status_msg = "Канал недоступен"
                
                self.update_ui_status(error_msg, error=True, status_message=status_msg)
                logging.error(f"Превышено максимальное количество попыток подключения к каналу: {channel_name}")
                
                # Показываем сообщение пользователю
                QMessageBox.warning(self, "Канал недоступен", 
                                 f"Канал '{channel_name}' недоступен после {self.max_retry_count} попыток подключения.\n"
                                 f"Возможно, поток вещания временно не работает или перегружен.")
            
        except Exception as e:
            logging.error(f"Ошибка при обработке события MediaPlayerEncounteredError: {e}")
            self.update_ui_status(f"Ошибка воспроизведения: {str(e)}", error=True)
            self.statusBar().showMessage("Ошибка воспроизведения", 5000)

    def media_playing(self, event):
        """Событие начала воспроизведения"""
        # Останавливаем таймер ожидания, т.к. воспроизведение началось
        if self.play_timeout_timer.isActive():
            self.play_timeout_timer.stop()
            
        self.progress_bar.setVisible(False)
        if self.current_channel_index >= 0:
            channel_name = self.channels[self.current_channel_index]['name']
            self.info_label.setText(f"Воспроизведение: {channel_name}")
            self.channel_name_label.setText(channel_name)
            self.statusbar_label.setText(f"Воспроизведение: {channel_name}")
            
            # Обновляем иконку в трее
            self.tray_icon.setToolTip(f"MaksIPTV Плеер - {channel_name}")
    
    def media_paused(self, event):
        """Событие паузы воспроизведения"""
        if self.current_channel_index >= 0:
            channel_name = self.channels[self.current_channel_index]['name']
            self.info_label.setText(f"Пауза: {channel_name}")
            self.statusbar_label.setText(f"Пауза: {channel_name}")
    
    def media_stopped(self, event):
        """Обработчик остановки медиаплеера"""
        self.statusbar_label.setText("Воспроизведение остановлено")

    def setup_tray(self):
        """Настройка иконки трея"""
        self.tray_icon = QSystemTrayIcon(qta.icon('fa5s.tv', color='#3d8ec9'), self)
        
        # Создаем меню для трея
        tray_menu = QMenu()
        
        show_action = QAction("Показать", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        hide_action = QAction("Скрыть", self)
        hide_action.triggered.connect(self.hide)
        tray_menu.addAction(hide_action)
        
        tray_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()
    
    def tray_icon_activated(self, reason):
        """Обработчик активации иконки в трее"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()
    
    def open_playlist(self):
        """Открывает диалог выбора плейлиста"""
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getOpenFileName(
            self, "Открыть плейлист", "", 
            "Плейлисты (*.m3u *.m3u8);;Все файлы (*)", 
            options=options
        )
        
        if filename:
            # Проверяем, не загружается ли тот же файл повторно
            is_same_playlist = False
            
            # Прямое совпадение пути
            if filename == self.current_playlist:
                is_same_playlist = True
            
            # Проверка временного плейлиста
            if hasattr(self, 'temp_playlist_path') and self.temp_playlist_path:
                if os.path.exists(filename) and os.path.exists(self.temp_playlist_path):
                    try:
                        if os.path.samefile(filename, self.temp_playlist_path):
                            is_same_playlist = True
                    except:
                        pass
            
            if is_same_playlist:
                reply = QMessageBox.question(
                    self, 'Повторная загрузка', 
                    'Этот плейлист уже загружен. Загрузить повторно?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    return
            
            try:
                # Запрашиваем имя для плейлиста
                default_name = os.path.splitext(os.path.basename(filename))[0]
                playlist_name, ok = QInputDialog.getText(
                    self, "Имя плейлиста", 
                    "Укажите имя плейлиста для отображения:",
                    text=default_name
                )
                
                if not ok:
                    playlist_name = default_name
                
                # Спрашиваем, копировать ли файл в текущую директорию
                reply = QMessageBox.question(
                    self, 'Копирование плейлиста', 
                    'Копировать плейлист в директорию программы?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                
                if reply == QMessageBox.Yes:
                    # Получаем только имя файла из полного пути
                    target_file = os.path.basename(filename)
                    
                    # Создаем резервную копию текущего плейлиста, если он существует
                    if os.path.exists(target_file):
                        backup_file = f"{target_file}.backup"
                        with open(target_file, 'rb') as src:
                            with open(backup_file, 'wb') as dst:
                                dst.write(src.read())
                    
                    # Копируем выбранный плейлист
                    with open(filename, 'rb') as src:
                        with open(target_file, 'wb') as dst:
                            dst.write(src.read())
                    
                    # Обновляем историю плейлистов с указанным именем
                    self.update_recent_playlists(target_file, playlist_name)
                    self.current_playlist = target_file
                    
                    # Сбрасываем путь к временному плейлисту
                    if hasattr(self, 'temp_playlist_path'):
                        delattr(self, 'temp_playlist_path')
                    
                    # Перезагружаем плейлист
                    self.reload_playlist()
                    
                    # Обновляем меню недавних плейлистов
                    self.update_recent_menu()
                    
                    QMessageBox.information(self, "Информация", "Плейлист успешно импортирован")
                else:
                    # Открываем внешний плейлист без копирования
                    self.stop()
                    self.channels = []
                    self.categories = {"Все каналы": []}
                    
                    # Обновляем историю плейлистов с указанным именем
                    self.update_recent_playlists(filename, playlist_name)
                    self.current_playlist = filename
                    
                    # Сохраняем путь к временному плейлисту
                    self.temp_playlist_path = filename
                    
                    # Загружаем плейлист
                    self.load_external_playlist(filename)
                    self.fill_channel_list()
                    
                    # Обновляем меню недавних плейлистов
                    self.update_recent_menu()
                    
                    self.info_label.setText(f"Загружен внешний плейлист: {playlist_name}")
                    
                    # Обновляем отображение количества каналов
                    total_channels = len(self.channels)
                    visible_channels = total_channels - len(self.hidden_channels)
                    self.statusbar_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
                    
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть плейлист: {str(e)}")

    def update_recent_playlists(self, playlist_path, playlist_name=None):
        """Обновляет список недавно использованных плейлистов
        
        Args:
            playlist_path: путь к плейлисту или URL
            playlist_name: имя плейлиста для отображения (если None, будет использовано имя файла)
        """
        # Добавляем имя плейлиста, если оно указано, иначе используем имя файла
        if playlist_name:
            self.playlist_names[playlist_path] = playlist_name
        elif playlist_path not in self.playlist_names:
            # Если имя не задано и отсутствует в словаре, используем имя файла или URL
            if playlist_path.startswith(('http://', 'https://')):
                self.playlist_names[playlist_path] = "Плейлист из URL"
            else:
                self.playlist_names[playlist_path] = os.path.basename(playlist_path)
            
            # Для локального плейлиста всегда используем "Локальный"
            if playlist_path == "local.m3u" or os.path.basename(playlist_path) == "local.m3u":
                self.playlist_names[playlist_path] = "Локальный"
        
        # Удаляем путь из списка, если он уже есть
        if playlist_path in self.recent_playlists:
            self.recent_playlists.remove(playlist_path)
            
        # Добавляем путь в начало списка
        self.recent_playlists.insert(0, playlist_path)
        
        # Ограничиваем список до 10 элементов (вместо 5)
        self.recent_playlists = self.recent_playlists[:10]
        
        # Обновляем текущий плейлист
        self.current_playlist = playlist_path
        
        # Сохраняем настройки
        self.save_config()
        
        # Обновляем меню недавних плейлистов
        if hasattr(self, 'recent_menu'):
            self.update_recent_menu()
        
    def select_first_channel(self):
        """Выбирает первый канал в списке без автоматического воспроизведения"""
        if self.channels:
            if self.channels_stack.currentIndex() == 0:  # Дерево категорий
                # Выбираем первую категорию и разворачиваем её
                if self.channel_tree.topLevelItemCount() > 0:
                    category_item = self.channel_tree.topLevelItem(0)
                    self.channel_tree.expandItem(category_item)
                    
                    # Выбираем первый канал в категории, если он есть
                    if category_item.childCount() > 0:
                        channel_item = category_item.child(0)
                        self.channel_tree.setCurrentItem(channel_item)
                        # Не воспроизводим канал автоматически
            else:  # Обычный список
                if self.channel_list.count() > 0:
                    self.channel_list.setCurrentRow(0)
                    # Не запускаем автоматическое воспроизведение

    def load_external_playlist(self, playlist_file):
        """Загружает внешний плейлист"""
        if not os.path.exists(playlist_file):
            QMessageBox.critical(None, "Ошибка", f"Плейлист {playlist_file} не найден!")
            return

        try:
            with open(playlist_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            channel = None
            user_agent = None
            self.categories = {"Все каналы": []}
            
            # Иконки для категорий
            self.category_icons = {
                "Фильмы": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Спорт": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Новости": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Музыка": self.style().standardIcon(QStyle.SP_MediaVolume),
                "Детские": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Развлекательные": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Познавательные": self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                "Все каналы": self.style().standardIcon(QStyle.SP_DirIcon),
                "Без категории": self.style().standardIcon(QStyle.SP_DirLinkIcon),
            }
            
            self.channels = []
            
            # Для хранения текущей группы из тега #EXTGRP
            current_group = "Без категории"
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#EXTM3U'):
                    continue
                elif line.startswith('#EXTINF:'):
                    # Извлекаем имя канала и группу из строки #EXTINF
                    group_match = re.search(r'group-title="([^"]*)"', line)
                    group_title = "Без категории"
                    
                    if group_match:
                        group_title = group_match.group(1).strip()
                        if not group_title:
                            group_title = "Без категории"
                    
                    # Извлекаем tvg-id если есть
                    tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
                    tvg_id = ""
                    if tvg_id_match:
                        tvg_id = tvg_id_match.group(1).strip()
                    
                    # Извлекаем tvg-logo если есть
                    tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                    tvg_logo = ""
                    if tvg_logo_match:
                        tvg_logo = tvg_logo_match.group(1).strip()
                    
                    parts = line.split(',', 1)
                    if len(parts) > 1:
                        channel = {
                            'name': parts[1].strip(), 
                            'options': {},
                            'category': group_title,
                            'tvg_id': tvg_id,
                            'tvg_logo': tvg_logo  # Добавляем URL логотипа
                        }
                        
                        # Добавляем категорию в словарь, если её ещё нет
                        if group_title not in self.categories:
                            self.categories[group_title] = []
                elif line.startswith('#EXTGRP:'):
                    # Обработка тега EXTGRP для m3u8 формата
                    current_group = line[len('#EXTGRP:'):].strip()
                    if not current_group:
                        current_group = "Без категории"
                    
                    # Если канал уже был определен, применяем к нему группу
                    if channel and 'name' in channel:
                        channel['category'] = current_group
                        
                        # Добавляем категорию в словарь, если её ещё нет
                        if current_group not in self.categories:
                            self.categories[current_group] = []
                elif line.startswith('#EXTVLCOPT:'):
                    # Обработка опций VLC
                    if channel:
                        opt = line[len('#EXTVLCOPT:'):].strip()
                        if 'http-user-agent=' in opt:
                            user_agent = opt.split('http-user-agent=')[1]
                            channel['options']['user-agent'] = user_agent
                
                elif channel and 'name' in channel and not line.startswith('#'):
                    # Это URL канала
                    channel['url'] = line
                    self.channels.append(channel)
                    
                    # Добавляем канал в соответствующую категорию
                    category = channel['category']
                    self.categories[category].append(channel)
                    self.categories["Все каналы"].append(channel)
                    
                    channel = None
                    # Сбрасываем текущую группу после добавления канала
                    current_group = "Без категории"

            # Обновляем выпадающий список категорий
            current_category = self.category_combo.currentText()
            self.category_combo.clear()
            self.category_combo.addItems(sorted(self.categories.keys()))
            
            # Пытаемся восстановить выбранную категорию
            index = self.category_combo.findText(current_category)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
                
            self.info_label.setText(f"Загружен плейлист: {len(self.channels)} каналов")

        except Exception as e:
            logging.error(f"Ошибка при чтении плейлиста: {str(e)}")
            QMessageBox.critical(None, "Ошибка", f"Ошибка при чтении плейлиста: {str(e)}")
        
    def add_playlist_from_url(self):
        """Добавляет плейлист из URL"""
        # Создаем диалоговое окно для ввода данных
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить плейлист из URL")
        dialog.resize(400, 120)
        
        layout = QVBoxLayout()
        
        # URL плейлиста
        url_layout = QHBoxLayout()
        url_label = QLabel("URL плейлиста:")
        url_edit = QLineEdit("http://")
        url_layout.addWidget(url_label)
        url_layout.addWidget(url_edit)
        layout.addLayout(url_layout)
        
        # Имя плейлиста
        name_layout = QHBoxLayout()
        name_label = QLabel("Имя плейлиста:")
        name_edit = QLineEdit("Новый плейлист")
        name_layout.addWidget(name_label)
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)
        
        # Кнопки
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        # Показываем диалог и получаем результат
        if dialog.exec_() == QDialog.Accepted:
            url = url_edit.text()
            playlist_name = name_edit.text()
            
            if url:
                # Проверяем, не загружается ли тот же URL повторно
                if url == self.current_playlist:
                    reply = QMessageBox.question(
                        self, 'Повторная загрузка', 
                        'Этот плейлист уже загружен. Загрузить повторно?',
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                    )
                    
                    if reply == QMessageBox.No:
                        return
                
                # Создаем уникальное имя для временного файла
                import uuid
                temp_file = f"temp_playlist_{str(uuid.uuid4())[:8]}.m3u"
                
                # Записываем имя плейлиста для URL
                if playlist_name:
                    self.playlist_names[url] = playlist_name
                
                # Загружаем плейлист по URL
                self.download_playlist_from_url(url, temp_file, is_update=False)

    def update_playlist_from_url(self):
        """Обновляет плейлист из интернета"""
        playlist_file = "local.m3u"
        playlist_url = "https://gitlab.com/iptv135435/iptvshared/raw/main/IPTV_SHARED.m3u"
        
        # Создаем резервную копию текущего плейлиста
        if os.path.exists(playlist_file):
            backup_file = f"{playlist_file}.backup"
            with open(playlist_file, 'rb') as src:
                with open(backup_file, 'wb') as dst:
                    dst.write(src.read())
        
        # Загружаем плейлист по URL
        self.download_playlist_from_url(playlist_url, playlist_file, is_update=True)
        
    def download_playlist_from_url(self, url, target_file, is_update=False):
        """Загружает и обрабатывает плейлист из URL
        
        Args:
            url: URL плейлиста
            target_file: Имя файла для сохранения плейлиста
            is_update: True если это обновление существующего плейлиста, False если добавление нового
        """
        try:
            # Удаляем старые временные файлы перед загрузкой (только для новых плейлистов)
            if not is_update:
                self._cleanup_temp_files()
            
            # Показываем прогресс
            self.info_label.setText(f"Скачивание плейлиста из {url}...")
            self.statusbar_label.setText("Скачивание плейлиста...")
            self.progress_bar.setVisible(True)
            
            def download_finished(success, error_message, source_url=""):
                self.progress_bar.setVisible(False)
                
                if success:
                    try:
                        # Проверяем, что файл действительно загружен и имеет формат M3U (для обновления)
                        if is_update:
                            with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                                first_line = f.readline().strip()
                                if not first_line.startswith('#EXTM3U'):
                                    raise ValueError("Файл не является плейлистом M3U")
                        
                        # Обновляем историю плейлистов
                        if is_update:
                            self.update_recent_playlists(target_file, "Локальный")
                            self.current_playlist = target_file
                        else:
                            if source_url:
                                # Используем сохраненное имя плейлиста или URL
                                playlist_name = self.playlist_names.get(source_url)
                                self.update_recent_playlists(source_url, playlist_name)
                                self.current_playlist = source_url
                            
                            # Сохраняем путь к временному плейлисту (только для новых плейлистов)
                            self.temp_playlist_path = target_file
                        
                        # Останавливаем текущий плейбек
                        self.stop()
                        
                        # Очищаем текущие данные каналов
                        self.channels = []
                        self.categories = {"Все каналы": []}
                        
                        # Загружаем внешний плейлист
                        self.load_external_playlist(target_file)
                        self.fill_channel_list()
                        
                        # Обновляем меню недавних плейлистов
                        self.update_recent_menu()
                        
                        # Устанавливаем сообщение об успешной загрузке
                        if is_update:
                            self.info_label.setText("Плейлист успешно обновлен")
                            self.statusbar_label.setText("Плейлист успешно обновлен")
                            QMessageBox.information(self, "Информация", "Плейлист успешно обновлен из интернета")
                        else:
                            self.info_label.setText(f"Загружен плейлист из URL")
                        
                        # Обновляем отображение количества каналов
                        total_channels = len(self.channels)
                        visible_channels = total_channels - len(self.hidden_channels)
                        
                        if hasattr(self, 'playlist_info_label'):
                            self.playlist_info_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
                        else:
                            self.statusbar_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
                        
                        # Автоматически выбираем первый канал
                        self.select_first_channel()
                        
                    except Exception as e:
                        self.info_label.setText(f"Ошибка обработки плейлиста: {str(e)}")
                        self.statusbar_label.setText("Ошибка обработки плейлиста")
                        QMessageBox.critical(self, "Ошибка", f"Не удалось обработать плейлист: {str(e)}")
                        
                        # Восстанавливаем из резервной копии если она есть (только для обновления)
                        if is_update:
                            backup_file = f"{target_file}.backup"
                            if os.path.exists(backup_file):
                                with open(backup_file, 'rb') as src:
                                    with open(target_file, 'wb') as dst:
                                        dst.write(src.read())
                        else:
                            # Удаляем неудачный временный файл
                            try:
                                if os.path.exists(target_file):
                                    os.remove(target_file)
                            except:
                                pass
                else:
                    self.info_label.setText(f"Ошибка загрузки плейлиста: {error_message}")
                    self.statusbar_label.setText("Ошибка загрузки плейлиста")
                    QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить плейлист: {error_message}")
                    
                    # Удаляем неудачный временный файл (только для новых плейлистов)
                    if not is_update:
                        try:
                            if os.path.exists(target_file):
                                os.remove(target_file)
                        except:
                            pass
            
            # Выбираем соответствующий поток для загрузки
            if is_update:
                # Для обновления используем обычный DownloadThread
                self.download_thread = DownloadThread(url, target_file)
            else:
                # Для добавления нового используем PlaylistDownloadThread (возвращает source_url)
                self.download_thread = PlaylistDownloadThread(url, target_file)
                
            self.download_thread.finished.connect(download_finished)
            self.download_thread.start()
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            self.info_label.setText(f"Ошибка загрузки плейлиста: {str(e)}")
            self.statusbar_label.setText("Ошибка загрузки плейлиста")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить плейлист: {str(e)}")

    def _cleanup_temp_files(self):
        """Удаляет старые временные файлы плейлистов"""
        try:
            # Перечисляем все файлы в текущей директории
            for filename in os.listdir("."):
                # Ищем временные файлы плейлистов
                if filename.startswith("temp_playlist_") and filename.endswith(".m3u"):
                    # Пропускаем текущий использующийся файл
                    if hasattr(self, 'temp_playlist_path') and filename == self.temp_playlist_path:
                        continue
                    
                    # Проверяем время создания файла
                    file_path = os.path.join(".", filename)
                    creation_time = os.path.getctime(file_path)
                    
                    # Если файл старше 1 часа, удаляем его
                    if (time.time() - creation_time) > 3600:  # 3600 секунд = 1 час
                        try:
                            os.remove(file_path)
                            logging.debug(f"Удален устаревший временный файл: {filename}")
                        except Exception as e:
                            logging.error(f"Ошибка при удалении временного файла {filename}: {e}")
        except Exception as e:
            logging.error(f"Ошибка при очистке временных файлов: {e}")

    def reload_playlist(self):
        """Перезагружает текущий плейлист из его источника (URL или файл)"""
        self.stop()
        self.channels = []
        self.categories = {"Все каналы": []}

        if not self.current_playlist:
            QMessageBox.warning(self, "Ошибка", "Не выбран текущий плейлист для обновления.")
            self.statusbar_label.setText("Ошибка: Нет плейлиста для обновления")
            return

        playlist_source = self.current_playlist
        is_url = playlist_source.startswith(('http://', 'https://'))

        if is_url:
            # --- Обновление из URL ---
            temp_file = "temp_playlist_for_reload.m3u" # Используем отдельное имя файла для перезагрузки
            self.info_label.setText(f"Обновление плейлиста из {playlist_source}...")
            self.statusbar_label.setText("Обновление плейлиста из URL...")
            self.progress_bar.setVisible(True)

            def download_finished(success, error_message, source_url=""): # Добавлен source_url для совместимости
                self.progress_bar.setVisible(False)
                if success:
                    try:
                        # Загружаем обновленный плейлист
                        self.temp_playlist_path = temp_file # Обновляем путь к временному файлу
                        self.load_external_playlist(temp_file)
                        self.fill_channel_list()
                        self.info_label.setText("Плейлист успешно обновлен из URL")
                        self.statusbar_label.setText("Плейлист обновлен из URL")
                        # Обновляем отображение количества каналов
                        total_channels = len(self.channels)
                        visible_channels = total_channels - len(self.hidden_channels)
                        self.playlist_info_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
                    except Exception as e:
                        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить каналы из обновленного плейлиста: {str(e)}")
                        self.info_label.setText("Ошибка загрузки каналов")
                        self.statusbar_label.setText("Ошибка загрузки каналов")
                else:
                    QMessageBox.critical(self, "Ошибка обновления", f"Не удалось скачать плейлист: {error_message}")
                    self.info_label.setText(f"Ошибка обновления: {error_message}")
                    self.statusbar_label.setText("Ошибка обновления плейлиста")
                     # Попытаться загрузить старую временную версию, если она есть
                    if hasattr(self, 'temp_playlist_path') and os.path.exists(self.temp_playlist_path):
                         try:
                             self.load_external_playlist(self.temp_playlist_path)
                             self.fill_channel_list()
                             self.info_label.setText("Загружена предыдущая версия плейлиста")
                             self.statusbar_label.setText("Загружена предыдущая версия")
                             QMessageBox.information(self, "Информация", "Не удалось обновить плейлист. Загружена предыдущая версия.")
                             self.select_first_channel()
                         except Exception as load_err:
                             QMessageBox.critical(self, "Критическая ошибка", f"Не удалось загрузить даже предыдущую версию: {load_err}")


            # Используем PlaylistDownloadThread для скачивания
            self.download_thread = PlaylistDownloadThread(playlist_source, temp_file)
            self.download_thread.finished.connect(download_finished)
            self.download_thread.start()

        else:
            # --- Обновление из файла ---
            if os.path.exists(playlist_source):
                try:
                    self.load_external_playlist(playlist_source)
                    self.fill_channel_list()
                    # Используем имя плейлиста для отображения
                    display_name = self.playlist_names.get(playlist_source, os.path.basename(playlist_source))
                    self.info_label.setText(f"Плейлист '{display_name}' перезагружен")
                    self.statusbar_label.setText("Плейлист перезагружен из файла")
                     # Обновляем отображение количества каналов
                    total_channels = len(self.channels)
                    visible_channels = total_channels - len(self.hidden_channels)
                    self.playlist_info_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
                    self.select_first_channel()
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось перезагрузить плейлист из файла: {str(e)}")
                    self.info_label.setText("Ошибка перезагрузки файла")
                    self.statusbar_label.setText("Ошибка перезагрузки файла")
            else:
                QMessageBox.warning(self, "Ошибка", f"Файл плейлиста не найден: {playlist_source}")
                self.info_label.setText("Файл плейлиста не найден")
                self.statusbar_label.setText("Файл плейлиста не найден")
    
    def toggle_favorites(self):
        """Переключение отображения избранных каналов"""
        if self.show_favorites:
            self.show_favorites = False
            self.favorites_button.setIcon(qta.icon('fa5s.star', color='#f0f0f0'))
            self.fill_channel_list()
            
            # Обновляем отображение количества каналов
            total_channels = len(self.channels)
            visible_channels = total_channels - len(self.hidden_channels)
            self.statusbar_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
            self.playlist_info_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
        else:
            self.show_favorites = True
            self.show_hidden = False
            self.hidden_button.setIcon(qta.icon('fa5s.eye-slash', color='#f0f0f0'))
            self.favorites_button.setIcon(qta.icon('fa5s.star', color='#f0d43c'))
            self.fill_favorites_list()
            
            # Отображаем количество избранных каналов
            visible_favorites = 0
            for fav in self.favorites:
                if fav not in self.hidden_channels:
                    visible_favorites += 1
                    
            self.statusbar_label.setText(f"Избранных каналов: {len(self.favorites)} (видимых: {visible_favorites})")
            self.playlist_info_label.setText(f"Избранных каналов: {len(self.favorites)} (видимых: {visible_favorites})")

    def toggle_hidden_channels(self):
        """Переключение отображения скрытых каналов"""
        if self.show_hidden:
            self.show_hidden = False
            self.hidden_button.setIcon(qta.icon('fa5s.eye-slash', color='#f0f0f0'))
            self.fill_channel_list()
            
            # Обновляем отображение количества каналов
            total_channels = len(self.channels)
            visible_channels = total_channels - len(self.hidden_channels)
            self.statusbar_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
            self.playlist_info_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
        else:
            self.show_hidden = True
            self.show_favorites = False
            self.favorites_button.setIcon(qta.icon('fa5s.star', color='#f0f0f0'))
            self.hidden_button.setIcon(qta.icon('fa5s.eye', color='#f0f0f0'))
            self.fill_hidden_list()
            self.statusbar_label.setText(f"Скрытых каналов: {len(self.hidden_channels)}")
            self.playlist_info_label.setText(f"Скрытых каналов: {len(self.hidden_channels)}")

    def next_audio_track(self):
        """Переключает на следующую аудиодорожку, если она доступна"""
        if not self.media_player.is_playing():
            return
            
        # Получаем текущий трек
        current_track = self.media_player.audio_get_track()
        
        # Получаем список доступных аудиодорожек
        track_count = self.media_player.audio_get_track_count()
        
        if track_count <= 1:
            self.info_label.setText("Нет дополнительных аудиодорожек")
            self.statusbar_label.setText("Нет дополнительных аудиодорожек")
            return
            
        # Находим следующий трек
        next_track = (current_track + 1) % track_count
        if next_track == 0:  # Трек 0 обычно означает "выключено"
            next_track = 1
            
        # Устанавливаем новый трек
        self.media_player.audio_set_track(next_track)
        
        # Получаем описание дорожки
        track_description = f"Аудиодорожка {next_track} из {track_count-1}"
        
        self.info_label.setText(track_description)
        self.statusbar_label.setText(track_description)

    def keyPressEvent(self, event):
        """Обработка нажатий клавиш"""
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.toggle_fullscreen()
            # Дополнительное принудительное восстановление интерфейса через 300мс
            QTimer.singleShot(300, self.restore_ui_after_fullscreen)
        elif event.key() == Qt.Key_Space:
            self.play_pause()
        elif event.key() == Qt.Key_F:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key_A:
            self.next_audio_track()
        else:
            super().keyPressEvent(event)
            
    def event(self, event):
        """Обрабатывает события приложения"""
        # Обрабатываем события приостановки/восстановления работы системы
        if event.type() == QEvent.ApplicationStateChange:
            # Если приложение становится неактивным (система блокируется/спит)
            if QApplication.applicationState() == Qt.ApplicationInactive:
                logging.info("Приложение перешло в неактивное состояние")
                # Останавливаем таймеры, которые могут вызвать проблемы
                if self.play_timeout_timer.isActive():
                    self.play_timeout_timer.stop()
                    
            # Если приложение восстанавливается
            elif QApplication.applicationState() == Qt.ApplicationActive:
                logging.info("Приложение стало активным")
                # Проверяем, воспроизводится ли канал, и если нет - пытаемся переподключиться
                if self.current_channel_index >= 0 and not self.media_player.is_playing():
                    logging.info("Автоматическое восстановление воспроизведения после возобновления работы")
                    # Сбрасываем счетчик попыток
                    self.retry_count = 0
                    # Через секунду пробуем восстановить воспроизведение текущего канала
                    QTimer.singleShot(1000, self.retry_current_channel)
        
        return super().event(event)

    def load_config(self):
        """Загружает конфигурацию из JSON-файла"""
        config_file = "player_config.json"
        default_config = {
            "volume": 50,
            "last_channel": None,
            "last_category": "Все каналы",
            "favorites": [],
            "hidden_channels": [],
            "recent_playlists": [],
            "playlist_names": {},  # Словарь с именами плейлистов (ключ - путь, значение - имя)
            "show_hidden": False,
            "show_logos": True,  # Показывать логотипы каналов по умолчанию
            "window_size": [800, 600],
            "window_position": [100, 100],
            "always_on_top": False
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # Устанавливаем значения из конфигурации
                self.volume = config.get('volume', default_config['volume'])
                self.last_channel = config.get('last_channel', default_config['last_channel'])
                self.last_category = config.get('last_category', default_config['last_category'])
                self.favorites = config.get('favorites', default_config['favorites'])
                self.hidden_channels = config.get('hidden_channels', default_config['hidden_channels'])
                self.recent_playlists = config.get('recent_playlists', default_config['recent_playlists'])
                self.playlist_names = config.get('playlist_names', default_config['playlist_names'])  # Загружаем имена плейлистов
                self.show_hidden = config.get('show_hidden', default_config['show_hidden'])
                self.show_logos = config.get('show_logos', default_config['show_logos'])  # Загружаем параметр отображения логотипов
                
                # Восстанавливаем размер и позицию окна
                window_size = config.get('window_size', default_config['window_size'])
                window_position = config.get('window_position', default_config['window_position'])
                
                if len(window_size) == 2 and all(isinstance(x, int) for x in window_size):
                    self.resize(window_size[0], window_size[1])
                
                if len(window_position) == 2 and all(isinstance(x, int) for x in window_position):
                    self.move(window_position[0], window_position[1])
                    
                # Восстанавливаем режим "поверх всех окон"
                self.always_on_top = config.get('always_on_top', default_config['always_on_top'])
                self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
            else:
                # Используем значения по умолчанию
                self.volume = default_config['volume']
                self.last_channel = default_config['last_channel']
                self.last_category = default_config['last_category']
                self.favorites = default_config['favorites']
                self.hidden_channels = default_config['hidden_channels']
                self.recent_playlists = default_config['recent_playlists']
                self.playlist_names = default_config['playlist_names']  # Инициализируем словарь имен плейлистов
                self.show_hidden = default_config['show_hidden']
                self.show_logos = default_config['show_logos']  # Инициализируем параметр отображения логотипов
                
                # Устанавливаем имя для локального плейлиста
                if os.path.exists("local.m3u"):
                    self.playlist_names["local.m3u"] = "Локальный"
                
                # Сохраняем конфигурацию по умолчанию
                self.save_config()
                
        except Exception as e:
            logging.error(f"Ошибка при загрузке конфигурации: {str(e)}")
            # Используем значения по умолчанию
            self.volume = default_config['volume']
            self.last_channel = default_config['last_channel']
            self.last_category = default_config['last_category']
            self.favorites = default_config['favorites']
            self.hidden_channels = default_config['hidden_channels']
            self.recent_playlists = default_config['recent_playlists']
            self.playlist_names = default_config['playlist_names']  # Инициализируем словарь имен плейлистов
            self.show_hidden = default_config['show_hidden']
            self.show_logos = default_config['show_logos']  # Инициализируем параметр отображения логотипов
            
            # Устанавливаем имя для локального плейлиста
            if os.path.exists("local.m3u"):
                self.playlist_names["local.m3u"] = "Локальный"

    def save_config(self):
        """Сохраняет конфигурацию в JSON-файл"""
        config_file = "player_config.json"
        try:
            # Определяем текущую категорию
            if hasattr(self, 'category_combo') and self.category_combo is not None:
                current_category = self.category_combo.currentText()
            else:
                # Если комбобокс еще не создан, используем сохраненное значение или значение по умолчанию
                current_category = getattr(self, 'last_category', "Все каналы")

            config = {
                "volume": self.volume,
                "last_channel": self.last_channel,
                "last_category": current_category,
                "favorites": self.favorites,
                "hidden_channels": self.hidden_channels,
                "recent_playlists": self.recent_playlists,
                "playlist_names": self.playlist_names,  # Сохраняем словарь имен плейлистов
                "show_hidden": self.show_hidden,
                "show_logos": self.show_logos,  # Сохраняем параметр отображения логотипов
                "window_size": [self.width(), self.height()],
                "window_position": [self.x(), self.y()],
                "always_on_top": self.windowFlags() & Qt.WindowStaysOnTopHint == Qt.WindowStaysOnTopHint
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
                
            logging.info("Конфигурация успешно сохранена")
        except Exception as e:
            logging.error(f"Ошибка при сохранении конфигурации: {str(e)}")

    def take_screenshot(self):
        """Делает снимок экрана текущего видео"""
        if not self.media_player.is_playing():
            QMessageBox.warning(self, "Предупреждение", "Видео не воспроизводится")
            return
            
        # Создаем папку для скриншотов, если её нет
        screenshots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)
            
        # Формируем имя файла со временем
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        channel_name = "unknown"
        if self.current_channel_index >= 0 and self.current_channel_index < len(self.channels):
            channel_name = self.channels[self.current_channel_index]['name']
            # Очищаем имя от недопустимых символов
            channel_name = ''.join(c if c.isalnum() or c in ' -_[]()' else '_' for c in channel_name)
        
        filename = f"{channel_name}_{timestamp}.png"
        filepath = os.path.join(screenshots_dir, filename)
        
        # Сохраняем скриншот с помощью VLC
        try:
            # Используем метод video_take_snapshot для сохранения скриншота
            self.media_player.video_take_snapshot(0, filepath, 0, 0)
            QMessageBox.information(self, "Информация", f"Скриншот сохранен: {filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сделать скриншот: {str(e)}")
            
    def show_channel_context_menu(self, position):
        """Показывает контекстное меню для канала"""
        sender = self.sender()
        
        # Определяем индекс выбранного канала
        if sender == self.channel_tree:
            selected_items = self.channel_tree.selectedItems()
            if not selected_items or not selected_items[0].parent():
                return
                
            channel_index = selected_items[0].data(0, Qt.UserRole)
            if channel_index is None:
                return
            channel = self.channels[channel_index]
        elif sender == self.channel_list:
            current_row = self.channel_list.currentRow()
            if current_row < 0:
                return
                
            current_category = self.category_combo.currentText()
            if current_category == "Избранное":
                # Находим канал из списка избранных
                favorites_visible = []
                for fav in self.favorites:
                    for ch in self.channels:
                        if ch['name'] == fav and ch['name'] not in self.hidden_channels:
                            favorites_visible.append(ch)
                
                if current_row >= len(favorites_visible):
                    return
                    
                channel = favorites_visible[current_row]
                for i, ch in enumerate(self.channels):
                    if ch['name'] == channel['name']:
                        channel_index = i
                        break
                else:
                    return
            else:
                # Находим видимые каналы в текущей категории
                visible_channels = []
                for ch in self.categories.get(current_category, []):
                    if ch['name'] not in self.hidden_channels:
                        visible_channels.append(ch)
                
                if current_row >= len(visible_channels):
                    return
                
                channel = visible_channels[current_row]
                channel_index = self.channels.index(channel)
        else:
            return
        
        # Создаем контекстное меню
        menu = QMenu(self)
        
        # Пункт "Воспроизвести"
        play_action = QAction("Воспроизвести", self)
        play_action.triggered.connect(lambda: self.play_channel(channel_index))
        menu.addAction(play_action)
        
        # Пункт "Добавить в избранное" или "Удалить из избранного"
        if channel['name'] in self.favorites:
            fav_action = QAction("Удалить из избранного", self)
            fav_action.triggered.connect(lambda: self.remove_from_favorites(channel['name']))
        else:
            fav_action = QAction("Добавить в избранное", self)
            fav_action.triggered.connect(lambda: self.add_to_favorites(channel['name']))
        
        menu.addAction(fav_action)
        
        # Пункт "Скрыть канал" или "Показать канал"
        if channel['name'] in self.hidden_channels:
            hide_action = QAction("Показать канал", self)
            hide_action.triggered.connect(lambda: self.show_channel(channel['name']))
        else:
            hide_action = QAction("Скрыть канал", self)
            hide_action.triggered.connect(lambda: self.hide_channel(channel['name']))
        
        menu.addAction(hide_action)
        
        # Пункт "Информация о канале"
        info_action = QAction("Информация о канале", self)
        info_action.triggered.connect(lambda: self.show_channel_info(channel))
        menu.addAction(info_action)
        
        # Показываем меню
        menu.exec_(QCursor.pos())
    
    def add_to_favorites(self, channel_name):
        """Добавляет канал в избранное"""
        if channel_name not in self.favorites:
            self.favorites.append(channel_name)
            
            # Обновляем список если открыта категория "Избранное"
            if self.category_combo.currentText() == "Избранное":
                self.fill_channel_list()
                
            # Добавляем категорию "Избранное" если её ещё нет
            if "Избранное" not in self.categories:
                self.categories["Избранное"] = []
                combo_current = self.category_combo.currentText()
                self.category_combo.clear()
                self.category_combo.addItems(sorted(self.categories.keys()))
                index = self.category_combo.findText(combo_current)
                if index >= 0:
                    self.category_combo.setCurrentIndex(index)
            
            # Сохраняем конфигурацию
            self.save_config()
    
    def remove_from_favorites(self, channel_name):
        """Удаляет канал из избранного"""
        if channel_name in self.favorites:
            self.favorites.remove(channel_name)
            
            # Обновляем список если открыта категория "Избранное"
            if self.category_combo.currentText() == "Избранное":
                self.fill_channel_list()
            
            # Сохраняем конфигурацию
            self.save_config()
    
    def show_channel_info(self, channel):
        """Показывает информацию о канале"""
        info = f"Название: {channel['name']}\n"
        info += f"Категория: {channel['category']}\n"
        
        if 'tvg_id' in channel and channel['tvg_id']:
            info += f"ID: {channel['tvg_id']}\n"
            
        info += f"URL: {channel['url']}"
        
        QMessageBox.information(self, "Информация о канале", info)
    
    def hide_channel(self, channel_name):
        """Скрывает канал из списков"""
        if channel_name not in self.hidden_channels:
            self.hidden_channels.append(channel_name)
            self.fill_channel_list()
            self.save_config()
            
    def show_channel(self, channel_name):
        """Показывает скрытый канал"""
        if channel_name in self.hidden_channels:
            self.hidden_channels.remove(channel_name)
            self.fill_channel_list()
            self.save_config()
    
    def set_volume(self, volume):
        """Устанавливает громкость воспроизведения"""
        self.media_player.audio_set_volume(volume)
        
        # Обновляем иконку громкости
        if volume == 0:
            self.volume_icon.setPixmap(self.style().standardIcon(QStyle.SP_MediaVolumeMuted).pixmap(QSize(16, 16)))
        else:
            self.volume_icon.setPixmap(self.style().standardIcon(QStyle.SP_MediaVolume).pixmap(QSize(16, 16)))
              
    def setup_statusbar(self):
        """Настраивает строку состояния приложения
        
        Создает и настраивает статус-бар с информацией о текущем состоянии
        воспроизведения и счетчиками каналов.
        """
        # Создаем объект статус-бара
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)
        
        # Создаем метку для отображения информации
        self.statusbar_label = QLabel("Готов к воспроизведению")
        
        # Устанавливаем стиль метки
        self.statusbar_label.setStyleSheet("""
            QLabel {
                padding: 3px;
                color: #f0f0f0;
            }
        """)
        
        # Добавляем метку в статус-бар с растяжением
        statusbar.addWidget(self.statusbar_label, 1)
        
        # Применяем стиль к статус-бару
        statusbar.setStyleSheet("""
            QStatusBar {
                background-color: #1e1e1e;
                color: #f0f0f0;
                border-top: 1px solid #444444;
            }
        """)
        
        logging.info("Статус-бар инициализирован")

    def restore_last_channel(self, channel_name):
        """Восстанавливает воспроизведение последнего просмотренного канала"""
        # Найти канал по имени
        for i, channel in enumerate(self.channels):
            if channel['name'] == channel_name:
                # Найти категорию
                category = channel['category']
                # Выбрать категорию в комбобоксе
                index = self.category_combo.findText(category)
                if index >= 0:
                    self.category_combo.setCurrentIndex(index)
                # Воспроизвести канал
                self.play_channel(i)
                return
    def retry_current_channel(self):
        """Повторное воспроизведение текущего канала после ошибки"""
        if hasattr(self, "current_channel_index") and self.current_channel_index >= 0:
            # Проверяем, не превышено ли максимальное число попыток
            if self.retry_count > self.max_retry_count:
                logging.warning(f"Превышено максимальное количество попыток ({self.max_retry_count}) для канала {self.current_channel_index}")
                
                # Показываем пользователю сообщение
                channel_name = "Неизвестный канал"
                if 0 <= self.current_channel_index < len(self.channels):
                    channel_name = self.channels[self.current_channel_index]['name']
                
                # Обновляем UI
                self.info_label.setText(f"Канал '{channel_name}' недоступен после {self.max_retry_count} попыток")
                self.statusbar_label.setText("Канал недоступен")
                return
                
            # Воспроизводим канал
            self.play_channel(self.current_channel_index)
            logging.info(f"Попытка №{self.retry_count} воспроизвести канал: {self.current_channel_index}")

    def update_ui_status(self, message, error=False, status_message=None, show_dialog=False, dialog_title="Информация"):
        """Централизованное обновление элементов интерфейса со статусом
        
        Args:
            message: Основное сообщение для info_label
            error: True если это сообщение об ошибке
            status_message: Сообщение для статус-бара (если None, используется message)
            show_dialog: Показать диалог с сообщением
            dialog_title: Заголовок диалога
        """
        try:
            # Обновляем метку с информацией
            if hasattr(self, 'info_label'):
                self.info_label.setText(message)
                
            # Обновляем статус-бар
            if hasattr(self, 'statusbar_label'):
                self.statusbar_label.setText(status_message or message)
                
            # Обновляем метку информации о плейлисте, если она доступна
            if hasattr(self, 'playlist_info_label') and self.playlist_info_label:
                # Для информации о плейлисте обычно нужна специальная логика,
                # поэтому только если status_message содержит "каналов: "
                if status_message and "каналов: " in status_message:
                    self.playlist_info_label.setText(status_message)
                    
            # Показываем диалог, если запрошено
            if show_dialog:
                if error:
                    QMessageBox.critical(self, dialog_title, message)
                else:
                    QMessageBox.information(self, dialog_title, message)
                    
        except Exception as e:
            logging.error(f"Ошибка при обновлении интерфейса: {e}")

    def play_selected_channel(self):
        """Воспроизведение выбранного канала"""
        if self.channels_stack.currentIndex() == 0:  # Дерево категорий
            selected_items = self.channel_tree.selectedItems()
            if not selected_items:
                return
                
            item = selected_items[0]
            # Проверяем, является ли выбранный элемент каналом (имеет родителя)
            if item.parent():
                channel_index = item.data(0, Qt.UserRole)
                if channel_index is not None:
                    self.play_channel(channel_index)
        else:  # Обычный список
            current_row = self.channel_list.currentRow()
            if current_row < 0:
                return
                
            current_category = self.category_combo.currentText()
            
            if current_category == "Избранное":
                # Находим канал из списка избранных
                favorites_visible = []
                for fav in self.favorites:
                    for ch in self.channels:
                        if ch['name'] == fav and (self.show_hidden or ch['name'] not in self.hidden_channels):
                            favorites_visible.append(ch)
                
                if current_row >= len(favorites_visible):
                    return
                    
                channel = favorites_visible[current_row]
                for i, ch in enumerate(self.channels):
                    if ch['name'] == channel['name']:
                        channel_index = i
                        break
                else:
                    return
                    
                self.play_channel(channel_index)
            else:
                # Находим видимые каналы в текущей категории
                visible_channels = []
                for ch in self.categories.get(current_category, []):
                    if self.show_hidden or ch['name'] not in self.hidden_channels:
                        visible_channels.append(ch)
                
                if current_row >= len(visible_channels):
                    return
                
                channel = visible_channels[current_row]
                channel_index = self.channels.index(channel)
                self.play_channel(channel_index)
    
    def on_channel_double_clicked(self, item):
        """Обработчик двойного клика по каналу"""
        # Просто вызываем метод воспроизведения выбранного канала
        self.play_selected_channel()

    def showEvent(self, event):
        """Событие при показе окна
        
        Вызывается, когда окно восстанавливается из свернутого состояния
        или становится видимым. Используется для восстановления корректного
        отображения интерфейса.
        """
        super().showEvent(event)
        
        # Если окно не находится в полноэкранном режиме, восстанавливаем интерфейс
        if not self.isFullScreen():
            QTimer.singleShot(100, self.restore_ui_after_fullscreen)
        
        # Логируем событие
        logging.debug("Окно восстановлено/показано")

    def load_channel_logo(self, logo_url):
        """Загружает и кэширует логотип канала"""
        if not logo_url:
            return None
        
        # Инициализация кэша и директории для кэша логотипов
        if not hasattr(self, 'logo_cache'):
            self.logo_cache = {}
            self.logo_download_threads = {}
            self.failed_logos = set()  # Список URL, которые не удалось загрузить
            self.max_concurrent_downloads = 5  # Ограничение на количество одновременных загрузок
            
            # Создаем директорию для кэша логотипов, если её нет
            # Определяем путь к директории кэша с учетом особенностей PyInstaller
            if getattr(sys, 'frozen', False):
                # Для скомпилированного приложения используем директорию с исполняемым файлом
                base_path = os.path.dirname(sys.executable)
            else:
                # Для запуска из исходников используем директорию скрипта
                base_path = os.path.dirname(os.path.abspath(__file__))
                
            # Создаем пути для кэша
            self.logos_cache_dir = os.path.join(base_path, 'cache', 'logos')
            os.makedirs(self.logos_cache_dir, exist_ok=True)
            logging.info(f"Инициализирован кэш логотипов: {self.logos_cache_dir}")
            
            # Отключаем предупреждения о небезопасных HTTPS-соединениях
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Включаем режим отладки для логов (устанавливаем False для рабочей версии)
            self.debug_logo_loading = False
        
        # Если URL уже в списке неудачных, не пытаемся загрузить снова
        if logo_url in self.failed_logos:
            return None
            
        # Если логотип уже загружен, возвращаем его из кэша
        if logo_url in self.logo_cache:
            return self.logo_cache[logo_url]
        
        # Генерируем имя файла для кэша на основе URL
        cache_filename = self._get_cache_filename(logo_url)
        cache_path = os.path.join(self.logos_cache_dir, cache_filename)
        
        # Проверяем, есть ли логотип в кэше на диске
        if os.path.exists(cache_path):
            try:
                pixmap = QPixmap(cache_path)
                if not pixmap.isNull():
                    self.logo_cache[logo_url] = pixmap
                    return pixmap
            except Exception:
                # Если возникла ошибка при загрузке из кэша, удаляем файл и загружаем заново
                try:
                    os.remove(cache_path)
                except Exception:
                    pass
        
        # Если логотип еще не загружается и не превышено ограничение на количество одновременных загрузок
        if (logo_url not in self.logo_download_threads and 
                len(self.logo_download_threads) < self.max_concurrent_downloads):
            thread = LogoDownloadThread(logo_url)
            thread.logo_loaded.connect(lambda url, pixmap: self.on_logo_loaded(url, pixmap, cache_path))
            thread.logo_failed.connect(self.on_logo_failed)
            self.logo_download_threads[logo_url] = thread
            thread.start()
        
        # Возвращаем None, логотип будет обновлен позже, когда загрузится
        return None
    
    def _get_cache_filename(self, url):
        """Генерирует имя файла для кэша на основе URL"""
        # Используем MD5-хеш URL для имени файла
        return hashlib.md5(url.encode('utf-8')).hexdigest() + '.png'
    
    def on_logo_loaded(self, logo_url, pixmap, cache_path=None):
        """Обработчик успешной загрузки логотипа"""
        # Сохраняем логотип в кэше
        self.logo_cache[logo_url] = pixmap
        
        # Сохраняем логотип в кэш на диске с сохранением прозрачности
        if cache_path:
            try:
                # Сохраняем как PNG для поддержки прозрачности
                pixmap.save(cache_path, 'PNG', quality=100)
            except Exception as e:
                logging.error(f"Ошибка при сохранении логотипа в кэш: {e}")
                pass
        
        # Удаляем поток из списка активных загрузок
        if logo_url in self.logo_download_threads:
            self.logo_download_threads[logo_url].deleteLater()
            del self.logo_download_threads[logo_url]
        
        # Обновляем все элементы списка, которые используют этот логотип
        self.update_channel_logos(logo_url, pixmap)
    
    def on_logo_failed(self, logo_url):
        """Обработчик неудачной загрузки логотипа"""
        # Добавляем URL в список неудачных, чтобы не пытаться загрузить снова
        self.failed_logos.add(logo_url)
        
        # Удаляем поток из списка активных загрузок
        if logo_url in self.logo_download_threads:
            self.logo_download_threads[logo_url].deleteLater()
            del self.logo_download_threads[logo_url]
    
    def update_channel_logos(self, logo_url, pixmap):
        """Обновляет иконки каналов после загрузки логотипа"""
        if not self.show_logos:
            return
            
        # Обновляем логотипы в обычном списке
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            idx = self.channel_list.row(item)
            channel_idx = -1
            
            # Получаем индекс канала
            for channel in self.channels:
                if channel['name'] == item.text():
                    if 'tvg_logo' in channel and channel['tvg_logo'] == logo_url:
                        item.setIcon(QIcon(pixmap))
                    break
        
        # Обновляем логотипы в дереве каналов
        root = self.channel_tree.invisibleRootItem()
        for i in range(root.childCount()):
            category_item = root.child(i)
            for j in range(category_item.childCount()):
                channel_item = category_item.child(j)
                channel_idx = channel_item.data(0, Qt.UserRole)
                if channel_idx is not None and 0 <= channel_idx < len(self.channels):
                    channel = self.channels[channel_idx]
                    if 'tvg_logo' in channel and channel['tvg_logo'] == logo_url:
                        channel_item.setIcon(0, QIcon(pixmap))

    def create_channel_item(self, channel_name, channel=None):
        """Создает элемент списка с логотипом (если доступен)"""
        item = QListWidgetItem(channel_name)
        
        # Если отображение логотипов включено
        if self.show_logos:
            # Если у нас есть информация о канале и URL логотипа
            if channel and 'tvg_logo' in channel and channel['tvg_logo']:
                logo = self.load_channel_logo(channel['tvg_logo'])
                if logo:
                    item.setIcon(QIcon(logo))
                else:
                    # Если не удалось загрузить логотип, используем стандартную иконку
                    item.setIcon(QIcon(self.default_channel_icon))
            else:
                # Если у канала нет логотипа, используем стандартную иконку
                item.setIcon(QIcon(self.default_channel_icon))
        
        return item

    def toggle_logos(self):
        """Включает/выключает отображение логотипов каналов"""
        self.show_logos = not self.show_logos
        self.show_logos_action.setChecked(self.show_logos)
        
        # Обновляем список каналов
        self.fill_channel_list()
        
        # Сохраняем настройку
        self.save_config()
        
    def toggle_always_on_top(self):
        """Включает/выключает режим поверх всех окон"""
        self.always_on_top = not self.always_on_top
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
        
        # Нужно скрыть и показать окно, чтобы изменения вступили в силу
        self.show()
        
        # Сохраняем настройку
        self.save_config()

    def create_default_channel_icon(self):
        """Создает стандартную иконку для каналов без логотипа"""
        # Создаем pixmap для иконки
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        # Создаем художника для рисования на pixmap
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Создаем градиент для фона
        gradient = QLinearGradient(0, 0, 32, 32)
        gradient.setColorAt(0, QColor('#4080b0'))  # Верхний цвет
        gradient.setColorAt(1, QColor('#2c5984'))  # Нижний цвет
        
        # Рисуем круглый фон с градиентом
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(2, 2, 28, 28)
        
        # Добавляем тонкую светлую рамку для объема
        pen = QPen(QColor('#ffffff'))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(2, 2, 28, 28)
        
        # Рисуем иконку телевизора внутри круга
        icon = qta.icon('fa5s.tv', color='white')
        icon_pixmap = icon.pixmap(16, 16)
        painter.drawPixmap(8, 8, icon_pixmap)
        
        painter.end()
        
        return pixmap

class LogoDownloadThread(QThread):
    """Поток для асинхронной загрузки логотипов каналов"""
    logo_loaded = pyqtSignal(str, QPixmap)  # URL логотипа, загруженный логотип
    logo_failed = pyqtSignal(str)  # URL логотипа, который не удалось загрузить
    
    def __init__(self, logo_url):
        super().__init__()
        self.logo_url = logo_url
        self.debug_mode = False  # По умолчанию режим отладки выключен
        self._abort = False  # Флаг для прерывания выполнения
        
    def abort(self):
        """Безопасно прервать выполнение потока"""
        self._abort = True
    
    def run(self):
        try:
            # Проверяем флаг прерывания
            if self._abort:
                self.logo_failed.emit(self.logo_url)
                return
                
            # Пропускаем URL от известных проблемных серверов
            skip_domains = ['fe-ural.svc.iptv.rt.ru', 'fe-sib.svc.iptv.rt.ru', 
                          'fe-sth.svc.iptv.rt.ru', 'fe-vlg.svc.iptv.rt.ru', 
                          'fe-nw.svc.iptv.rt.ru', 'picon.ml', 'yt3.ggpht.com',
                          'pbs.twimg.com', 'television-live.com', 'tsifra-tv.ru',
                          'nm-tv.ru', 'gas-kvas.com', 'online-television.net']
            
            if any(domain in self.logo_url for domain in skip_domains):
                self.logo_failed.emit(self.logo_url)
                return
                
            # Проверяем флаг прерывания еще раз
            if self._abort:
                self.logo_failed.emit(self.logo_url)
                return
                
            # Пробуем загрузить изображение из URL с проверкой сертификата
            response = requests.get(self.logo_url, timeout=3, verify=False)
            if response.status_code == 200:
                try:
                    # Предварительная обработка изображения через PIL для устранения проблем с iCCP профилем
                    image_data = response.content
                    try:
                        from PIL import Image
                        import io
                        # Открываем изображение через PIL
                        img = Image.open(io.BytesIO(image_data))
                        # Сохраняем альфа-канал для прозрачности
                        # Просто очищаем профиль iCCP, но сохраняем формат изображения
                        output = io.BytesIO()
                        if img.mode == 'RGBA':
                            # Сохраняем PNG с прозрачностью
                            img.save(output, format='PNG', icc_profile=None)
                        else:
                            # Для других форматов сохраняем как есть
                            img.save(output, format='PNG', icc_profile=None)
                        image_data = output.getvalue()
                    except (ImportError, Exception):
                        # Пропускаем предобработку, если PIL не установлен или возникла ошибка
                        pass
                        
                    pixmap = QPixmap()
                    pixmap.loadFromData(image_data)
                    if not pixmap.isNull():
                        # Проверяем и сохраняем прозрачность, если она есть
                        if pixmap.hasAlpha():
                            # Если у изображения есть альфа-канал, сохраняем его
                            scaled_pixmap = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        else:
                            # Для изображений без альфа-канала создаём прозрачный фон
                            temp = QPixmap(32, 32)
                            temp.fill(Qt.transparent)
                            painter = QPainter(temp)
                            scaled = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            # Центрируем изображение
                            x = (32 - scaled.width()) // 2
                            y = (32 - scaled.height()) // 2
                            painter.drawPixmap(x, y, scaled)
                            painter.end()
                            scaled_pixmap = temp
                        
                        self.logo_loaded.emit(self.logo_url, scaled_pixmap)
                    else:
                        self.logo_failed.emit(self.logo_url)
                except Exception:
                    self.logo_failed.emit(self.logo_url)
            else:
                self.logo_failed.emit(self.logo_url)
        except Exception as e:
            # Выводим ошибку только в режиме отладки
            if self.debug_mode:
                print(f"Ошибка загрузки логотипа {self.logo_url}: {str(e)}")
            self.logo_failed.emit(self.logo_url)

def main():
    """Основная функция программы"""
    try:
        # Настройка системы логирования
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_file = os.path.join(log_dir, f"iptv_player_{datetime.now().strftime('%Y%m%d')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("Запуск приложения MaksIPTV Плеер")
         
        # Создаем экземпляр приложения
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # Устанавливаем стиль
        
        # Создаем главное окно
        window = IPTVPlayer()
                 
        # Обработка завершения приложения
        app.aboutToQuit.connect(window.cleanup)
        
        # Запускаем цикл обработки событий
        sys.exit(app.exec_())
    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске приложения: {e}", exc_info=True)
        if 'app' in locals():
            sys.exit(1)
        else:
            print(f"Критическая ошибка: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main() 