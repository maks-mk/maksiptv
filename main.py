import sys
import os
import re
import time
import json
import urllib.request
import logging
from datetime import datetime
import vlc
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, 
                              QSlider, QStyle, QToolBar, QAction, QStatusBar, 
                              QProgressBar, QMenu, QSystemTrayIcon, QFileDialog,
                              QInputDialog, QListWidgetItem, QWidgetAction, QGraphicsOpacityEffect)
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, QThread, QPoint, QByteArray
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor, QPixmap, QImage, QCursor
from PyQt5.QtWidgets import (QTreeWidget, QTreeWidgetItem, QFrame, QSplitter, 
                             QListWidget, QMenuBar, QMessageBox, QDialog, QSizePolicy,
                             QTextBrowser, QStackedWidget, QHeaderView, QTreeWidgetItemIterator)

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
            # Настраиваем opener с User-Agent для обхода ограничений
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')]
            urllib.request.install_opener(opener)
            
            # Скачиваем файл с таймаутом в 30 секунд
            request = urllib.request.Request(self.url)
            response = urllib.request.urlopen(request, timeout=30)
            
            # Записываем содержимое в файл
            with open(self.file_path, 'wb') as f:
                f.write(response.read())
            
            self.finished.emit(True, "")
        except urllib.error.URLError as e:
            self.finished.emit(False, f"Ошибка URL: {str(e)}")
        except urllib.error.HTTPError as e:
            self.finished.emit(False, f"Ошибка HTTP: {e.code} {e.reason}")
        except TimeoutError:
            self.finished.emit(False, "Превышено время ожидания")
        except Exception as e:
            self.finished.emit(False, str(e))


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
    background-color: rgba(61, 142, 201, 0.2);
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
    background-color: rgba(61, 142, 201, 0.3);
}

QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #3d8ec9;
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
    background-color: #3d8ec9;
    color: white;
}

QMenuBar::item:pressed {
    background-color: #2d7db9;
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
    background-color: #3d8ec9;
    color: white;
}

QMenu::separator {
    height: 1px;
    background-color: #444444;
    margin: 6px 10px;
}

QPushButton {
    background-color: #3d8ec9;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    min-height: 30px;
}

QPushButton:hover {
    background-color: #4a9dd8;
}

QPushButton:pressed {
    background-color: #2d7db9;
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
    background-color: rgba(61, 142, 201, 0.2);
}

QToolButton:pressed {
    background-color: rgba(61, 142, 201, 0.3);
}

QLineEdit {
    padding: 8px;
    border-radius: 6px;
    background-color: #2d2d2d;
    min-height: 30px;
}

QLineEdit:focus {
    border: 1px solid #3d8ec9;
}

QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #444444;
    margin: 2px 0;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #3d8ec9;
    border: none;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #4a9dd8;
}

QProgressBar {
    border: none;
    border-radius: 4px;
    text-align: center;
    background-color: #444444;
    height: 8px;
}

QProgressBar::chunk {
    background-color: #3d8ec9;
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

class IPTVPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MaksIPTV Плеер")
        self.setGeometry(40, 40, 1200, 650)
        self.setMinimumSize(900, 600)
        
        # Применяем стили
        self.setStyleSheet(STYLESHEET)
        
        # Загрузка сохраненных настроек
        self.config_file = "player_config.json"
        self.config = self.load_config()
        
        # Загрузка списка каналов
        self.channels = []
        self.current_channel_index = -1
        self.favorites = self.config.get("favorites", [])
        self.hidden_channels = self.config.get("hidden_channels", [])
        
        # Флаги для отображения избранных и скрытых каналов
        self.show_favorites = False
        self.show_hidden = False
        
        # Инициализируем категории
        self.categories = {"Все каналы": []}
        
        # История плейлистов
        self.recent_playlists = self.config.get("recent_playlists", ["IPTV_SHARED.m3u"])
        self.current_playlist = self.config.get("current_playlist", self.recent_playlists[0] if self.recent_playlists else "IPTV_SHARED.m3u")
        self.temp_playlist_path = None
        
        # Инициализация VLC
        if sys.platform.startswith('linux'):
            self.instance = vlc.Instance("--no-xlib")
        else:
            self.instance = vlc.Instance()
            
        self.media_player = self.instance.media_player_new()
        
        # Таймер для обновления состояния плеера
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)
        
        # Настройка обработчиков событий медиаплеера
        self.event_manager = self.media_player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.media_playing)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self.media_paused)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self.media_stopped)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.handle_error)
        
        self.load_playlist()
        
        # Инициализация UI
        self.init_ui()
        
        # Обновляем меню недавних плейлистов
        self.update_recent_menu()
            
        # Устанавливаем запомненный уровень громкости
        saved_volume = self.config.get("volume", 70)
        self.volume_slider.setValue(saved_volume)
        self.set_volume(saved_volume)
        
        # Восстанавливаем последний просмотренный канал
        last_channel = self.config.get("last_channel", None)
        if last_channel is not None:
            QTimer.singleShot(1000, lambda: self.restore_last_channel(last_channel))
        
        # Настройка системного трея
        self.setup_tray()
        
        # Показываем приложение
        self.show()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный макет
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Создаем основной сплиттер
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(2)
        
        # Создаем меню приложения
        self.create_menu()
        
        # === Левая панель с списком каналов ===
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
        category_layout = QHBoxLayout()
        category_layout.setSpacing(8)
        
        category_label = QLabel("Категория:")
        category_label.setStyleSheet("color: #a0a0a0;")
        category_layout.addWidget(category_label)
        
        self.category_combo = QComboBox()
        self.category_combo.addItems(sorted(self.categories.keys()))
        self.category_combo.currentTextChanged.connect(self.category_changed)
        
        category_layout.addWidget(self.category_combo)
        
        # Поиск
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)
        
        search_label = QLabel("Поиск:")
        search_label.setStyleSheet("color: #a0a0a0;")
        search_layout.addWidget(search_label)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Поиск каналов...")
        self.search_box.textChanged.connect(self.filter_channels)
        search_layout.addWidget(self.search_box)
        
        # Панель кнопок с иконками
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        
        # Создаем небольшие кнопки с иконками
        button_size = QSize(32, 32)
        icon_size = QSize(16, 16)
        
        self.sort_button = QPushButton()
        self.sort_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        self.sort_button.setIconSize(icon_size)
        self.sort_button.setFixedSize(button_size)
        self.sort_button.setToolTip("Сортировать по алфавиту")
        self.sort_button.clicked.connect(self.sort_channels)
        
        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.refresh_button.setIconSize(icon_size)
        self.refresh_button.setFixedSize(button_size)
        self.refresh_button.setToolTip("Обновить плейлист")
        self.refresh_button.clicked.connect(self.reload_playlist)
        
        self.update_button = QPushButton()
        self.update_button.setIcon(self.style().standardIcon(QStyle.SP_DriveNetIcon))
        self.update_button.setIconSize(icon_size)
        self.update_button.setFixedSize(button_size)
        self.update_button.setToolTip("Обновить из интернета")
        self.update_button.clicked.connect(self.update_playlist_from_url)
        
        self.favorites_button = QPushButton()
        self.favorites_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.favorites_button.setIconSize(icon_size)
        self.favorites_button.setFixedSize(button_size)
        self.favorites_button.setToolTip("Избранное")
        self.favorites_button.clicked.connect(self.toggle_favorites)
        
        self.hidden_button = QPushButton()
        self.hidden_button.setIcon(self.style().standardIcon(QStyle.SP_DialogNoButton))
        self.hidden_button.setIconSize(icon_size)
        self.hidden_button.setFixedSize(button_size)
        self.hidden_button.setToolTip("Скрытые каналы")
        self.hidden_button.clicked.connect(self.toggle_hidden_channels)
        
        button_layout.addWidget(self.sort_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.favorites_button)
        button_layout.addWidget(self.hidden_button)
        button_layout.addStretch(1)
        
        # Создаем древовидный список и обычный список
        self.channel_tree = QTreeWidget()
        self.channel_tree.setHeaderHidden(True)
        self.channel_tree.itemSelectionChanged.connect(self.tree_selection_changed)
        self.channel_tree.setIconSize(QSize(24, 24))
        self.channel_tree.setAnimated(True)
        self.channel_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.channel_tree.customContextMenuRequested.connect(self.show_channel_context_menu)
        self.channel_tree.setAlternatingRowColors(True)
        self.channel_tree.setStyleSheet("QTreeWidget::item { padding: 8px; margin: 2px 0; }")
        
        self.channel_list = QListWidget()
        self.channel_list.currentRowChanged.connect(self.channel_changed)
        self.channel_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self.show_channel_context_menu)
        self.channel_list.setAlternatingRowColors(True)
        self.channel_list.setStyleSheet("QListWidget::item { padding: 10px; margin: 2px 0; }")
        
        # Стек виджетов для переключения между деревом и списком
        self.channels_stack = QStackedWidget()
        self.channels_stack.addWidget(self.channel_tree)
        self.channels_stack.addWidget(self.channel_list)
        
        # Информация о плейлисте
        total_channels = len(self.channels)
        visible_channels = total_channels - len(self.hidden_channels)
        self.playlist_info_label = QLabel(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
        self.playlist_info_label.setObjectName("playlistInfo")
        self.playlist_info_label.setAlignment(Qt.AlignCenter)
        
        # Добавляем все виджеты на левую панель
        left_layout.addWidget(channels_header)
        left_layout.addLayout(category_layout)
        left_layout.addLayout(search_layout)
        left_layout.addLayout(button_layout)
        left_layout.addWidget(self.channels_stack, 1)
        left_layout.addWidget(self.playlist_info_label)
        
        # === Правая панель с видео и контролами ===
        right_panel = QWidget()
        right_panel.setObjectName("right_panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        right_layout.setSpacing(15)
        
        # Заголовок с названием канала
        self.channel_name_label = QLabel("Нет воспроизведения")
        self.channel_name_label.setObjectName("channelNameLabel")
        self.channel_name_label.setAlignment(Qt.AlignCenter)
        
        # Фрейм для видео
        self.video_frame = QFrame()
        self.video_frame.setObjectName("videoFrame")
        self.video_frame.setFrameShape(QFrame.StyledPanel)
        self.video_frame.setFrameShadow(QFrame.Raised)
        self.video_frame.setMinimumHeight(400)
        
        # При двойном клике на видео - переключаем полноэкранный режим
        self.video_frame_label = ClickableLabel()
        self.video_frame_label.setAlignment(Qt.AlignCenter)
        self.video_frame_label.clicked.connect(self.toggle_fullscreen)
        
        video_layout = QVBoxLayout(self.video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.addWidget(self.video_frame_label)
        
        # Панель контролов воспроизведения
        control_panel = QWidget()
        control_panel.setObjectName("controlPanel")
        control_panel.setStyleSheet("QWidget#controlPanel { background-color: #2d2d2d; border-radius: 8px; }")
        
        control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(10, 5, 10, 5)
        control_layout.setSpacing(8)
        
        # Создаем кнопки управления воспроизведением
        button_size = QSize(36, 36)
        icon_size = QSize(20, 20)
        
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.setIconSize(icon_size)
        self.play_button.setFixedSize(button_size)
        self.play_button.setToolTip("Воспроизведение/Пауза (Пробел)")
        self.play_button.clicked.connect(self.play_pause)
        
        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.setIconSize(icon_size)
        self.stop_button.setFixedSize(button_size)
        self.stop_button.setToolTip("Остановить")
        self.stop_button.clicked.connect(self.stop)
        
        self.screenshot_button = QPushButton()
        self.screenshot_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.screenshot_button.setIconSize(icon_size)
        self.screenshot_button.setFixedSize(button_size)
        self.screenshot_button.setToolTip("Сделать снимок экрана")
        self.screenshot_button.clicked.connect(self.take_screenshot)
        
        self.audio_track_button = QPushButton()
        self.audio_track_button.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))
        self.audio_track_button.setIconSize(icon_size)
        self.audio_track_button.setFixedSize(button_size)
        self.audio_track_button.setToolTip("Следующая аудиодорожка (A)")
        self.audio_track_button.clicked.connect(self.next_audio_track)
        
        self.fullscreen_button = QPushButton()
        self.fullscreen_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        self.fullscreen_button.setIconSize(icon_size)
        self.fullscreen_button.setFixedSize(button_size)
        self.fullscreen_button.setToolTip("Полный экран (F)")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        
        # Слайдер громкости
        volume_panel = QWidget()
        volume_layout = QHBoxLayout(volume_panel)
        volume_layout.setContentsMargins(0, 0, 0, 0)
        volume_layout.setSpacing(5)
        
        self.volume_icon = QLabel()
        self.volume_icon.setPixmap(self.style().standardIcon(QStyle.SP_MediaVolume).pixmap(QSize(18, 18)))
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setToolTip("Громкость")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)  # Начальная громкость 70%
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.volume_slider.setFixedWidth(120)
        
        volume_layout.addWidget(self.volume_icon)
        volume_layout.addWidget(self.volume_slider)
        
        # Добавляем элементы на панель управления
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.screenshot_button)
        control_layout.addWidget(self.audio_track_button)
        control_layout.addStretch(1)
        control_layout.addWidget(volume_panel)
        control_layout.addStretch(1)
        control_layout.addWidget(self.fullscreen_button)
        
        # Информационная панель
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
        
        # Добавляем все на правую панель
        right_layout.addWidget(self.channel_name_label)
        right_layout.addWidget(self.video_frame, 1)
        right_layout.addWidget(control_panel)
        right_layout.addWidget(info_panel)
        
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
        
        # Настраиваем системный трей
        self.setup_tray()
        
        # Настраиваем VLC
        self.instance = vlc.Instance('--no-xlib --quiet')  # Инициализация VLC без X11
        
        # Создаем проигрыватель
        self.media_player = self.instance.media_player_new()
        
        if sys.platform == "linux":  # для Linux
            self.media_player.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":  # для Windows
            self.media_player.set_hwnd(self.video_frame.winId())
        elif sys.platform == "darwin":  # для MacOS
            self.media_player.set_nsobject(int(self.video_frame.winId()))
            
        # Настраиваем обработчики событий VLC
        events = self.media_player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self.handle_error)
        events.event_attach(vlc.EventType.MediaPlayerPlaying, self.media_playing)
        events.event_attach(vlc.EventType.MediaPlayerPaused, self.media_paused)
        events.event_attach(vlc.EventType.MediaPlayerStopped, self.media_stopped)
        events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.handle_error)
        
        # Настраиваем таймер для обновления интерфейса
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(1000)  # Обновление каждую секунду
        
        # Если был сохранен последний канал, выбираем его автоматически
        if self.config.get("last_channel"):
            self.restore_last_channel(self.config.get("last_channel"))

    def create_menu(self):
        """Создает главное меню приложения"""
        menubar = self.menuBar()
        
        # Меню Файл
        file_menu = menubar.addMenu("Файл")
        
        # Открыть плейлист
        open_action = QAction("Открыть плейлист...", self)
        open_action.triggered.connect(self.open_playlist)
        file_menu.addAction(open_action)
        
        # Добавить плейлист из URL
        add_url_action = QAction("Добавить плейлист из URL...", self)
        add_url_action.triggered.connect(self.add_playlist_from_url)
        file_menu.addAction(add_url_action)
        
        # Обновить плейлист
        update_action = QAction("Обновить плейлист", self)
        update_action.triggered.connect(self.reload_playlist)
        file_menu.addAction(update_action)
        
        # Обновить из интернета
        update_url_action = QAction("Обновить из интернета", self)
        update_url_action.triggered.connect(self.update_playlist_from_url)
        file_menu.addAction(update_url_action)
        
        # Недавние плейлисты
        self.recent_menu = file_menu.addMenu("Недавние плейлисты")
        
        file_menu.addSeparator()
        
        # Выход
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.exit_app)
        file_menu.addAction(exit_action)
        
        # Меню Каналы
        channels_menu = menubar.addMenu("Каналы")
        
        # Избранные каналы
        favorites_menu = channels_menu.addMenu("Избранные каналы")
        
        # Показать все избранные
        show_favorites_action = QAction("Показать все избранные", self)
        show_favorites_action.triggered.connect(self.show_all_favorites)
        favorites_menu.addAction(show_favorites_action)
        
        # Очистить список избранного
        clear_favorites_action = QAction("Очистить список избранного", self)
        clear_favorites_action.triggered.connect(self.clear_favorites)
        favorites_menu.addAction(clear_favorites_action)
        
        # Управление скрытыми каналами
        hidden_menu = channels_menu.addMenu("Скрытые каналы")
        
        # Показать скрытые каналы
        show_hidden_action = QAction("Управление скрытыми каналами", self)
        show_hidden_action.triggered.connect(self.manage_hidden_channels)
        hidden_menu.addAction(show_hidden_action)
        
        # Очистить список скрытых
        clear_hidden_action = QAction("Показать все скрытые каналы", self)
        clear_hidden_action.triggered.connect(self.clear_hidden_channels)
        hidden_menu.addAction(clear_hidden_action)
        
        # Меню Справка
        help_menu = menubar.addMenu("Справка")
        
        # О программе
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def update_recent_menu(self):
        """Обновляет меню недавно открытых плейлистов"""
        self.recent_menu.clear()
        
        if not self.recent_playlists:
            empty_action = QAction("Нет недавних плейлистов", self)
            empty_action.setEnabled(False)
            self.recent_menu.addAction(empty_action)
            return
            
        for i, playlist in enumerate(self.recent_playlists):
            # Отображаем только имя файла для длинных путей
            display_name = os.path.basename(playlist) if os.path.exists(playlist) else playlist
            
            # Показываем URL или путь к файлу
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
            
            # Формируем отображаемое имя
            if is_current:
                display_name = f"[>] {display_name}"
                color = "#00FF00"
            else:
                color = "white"

            # Создаём QLabel с нужным стилем и эффектом наведения
            label = QLabel(display_name)
            label.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    padding: 4px 10px;
                }}
                QLabel:hover {{
                    background-color: #1E90FF;
                }}
                """)

            # Заворачиваем в QWidgetAction
            action = QWidgetAction(self)
            action.setDefaultWidget(label)

            # Сохраняем данные плейлиста в атрибуте QLabel
            label.playlist_path = playlist
            
            # Обработка левого и правого клика
            def mousePressEvent(event, label=label):
                if event.button() == Qt.LeftButton:
                    self.open_recent_playlist(label.playlist_path)
                elif event.button() == Qt.RightButton:
                    self.show_recent_playlist_context_menu(event.globalPos(), label.playlist_path)
            
            # Заменяем стандартное событие нажатия мыши
            label.mousePressEvent = mousePressEvent

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
                            # Обновляем историю плейлистов
                            self.update_recent_playlists(url)
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
                
                # Обновляем историю плейлистов
                self.update_recent_playlists(playlist_path)
                self.current_playlist = playlist_path
                
                # Сохраняем путь к временному плейлисту
                self.temp_playlist_path = playlist_path
                
                # Загружаем плейлист
                self.load_external_playlist(playlist_path)
                self.fill_channel_list()
                
                # Обновляем меню недавних плейлистов
                self.update_recent_menu()
                
                self.info_label.setText(f"Загружен внешний плейлист: {os.path.basename(playlist_path)}")
                
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
        self.save_config()
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
                    
                    # Создаем элемент списка
                    item = QListWidgetItem(channel['name'])
                    self.channel_list.addItem(item)
    
    def fill_hidden_list(self):
        """Заполняет список скрытых каналов"""
        self.channels_stack.setCurrentIndex(1)  # Переключаемся на обычный список
        self.channel_list.clear()
        
        for channel_name in self.hidden_channels:
            # Находим канал по имени
            for channel in self.channels:
                if channel['name'] == channel_name:
                    # Создаем элемент списка
                    item = QListWidgetItem(channel['name'])
                    self.channel_list.addItem(item)
    
    def show_about(self):
        """Показывает информацию о программе"""
        QMessageBox.about(self, "О программе",
                         "<h3>MaksIPTV Плеер</h3>"
                         "<p>Версия 0.11.42</p>"
                         "<p>Современный плеер для просмотра IPTV каналов из M3U плейлиста</p>"
                         "<p>© 2025</p>")

    def load_playlist(self):
        playlist_file = "IPTV_SHARED.m3u"
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
                    
                    parts = line.split(',', 1)
                    if len(parts) > 1:
                        channel = {
                            'name': parts[1].strip(), 
                            'options': {},
                            'category': group_title,
                            'tvg_id': tvg_id
                        }
                        
                        # Добавляем категорию в словарь, если её ещё нет
                        if group_title not in self.categories:
                            self.categories[group_title] = []
                
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
                        
                        # Создаем элемент списка
                        item = QListWidgetItem(channel['name'])
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
                    # Создаем элемент списка
                    item = QListWidgetItem(channel['name'])
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
        self.fill_channel_list()
    
    def tree_selection_changed(self):
        """Обработчик выбора канала в дереве категорий"""
        selected_items = self.channel_tree.selectedItems()
        if not selected_items:
            return
            
        item = selected_items[0]
        # Проверяем, является ли выбранный элемент каналом (имеет родителя)
        if item.parent():
            channel_index = item.data(0, Qt.UserRole)
            if channel_index is not None:
                self.play_channel(channel_index)
    
    def channel_changed(self, row):
        """Обработчик выбора канала в обычном списке"""
        current_category = self.category_combo.currentText()
        channels_in_category = self.categories.get(current_category, [])
        
        if 0 <= row < len(channels_in_category):
            channel = channels_in_category[row]
            channel_index = self.channels.index(channel)
            self.play_channel(channel_index)
    
    def play_channel(self, channel_index):
        """Воспроизведение выбранного канала с учетом всех опций"""
        if channel_index < 0 or channel_index >= len(self.channels):
            return
        
        # Останавливаем текущее воспроизведение, если оно есть
        self.stop()
        
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
        self.config["last_channel"] = channel['name']
        self.save_config()
        
        try:
            # Создаем медиа с нужным URL
            url = channel['url']
            
            # Настраиваем параметры медиа через конструктор MediaPlayer
            media = self.instance.media_new(url)
            
            # Настраиваем медиа-опции VLC, если они указаны для канала
            if 'options' in channel and channel['options']:
                for opt_name, opt_value in channel['options'].items():
                    if opt_name == 'user-agent':
                        media.add_option(f":http-user-agent={opt_value}")
                    elif opt_name == 'http-referrer':
                        media.add_option(f":http-referrer={opt_value}")
                    elif opt_name == 'referer':
                        media.add_option(f":http-referrer={opt_value}")
                    else:
                        media.add_option(f":{opt_name}={opt_value}")
                        
            # Добавляем общие сетевые опции для улучшения воспроизведения
            media.add_option(":network-caching=3000")
            media.add_option(":file-caching=1000")
            media.add_option(":live-caching=1000")
            media.add_option(":sout-mux-caching=1000")
            
            # Устанавливаем медиа в плеер и воспроизводим
            self.media_player.set_media(media)
            self.play()
            
            # Обновляем интерфейс
            self.update_ui()
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            self.info_label.setText(f"Ошибка воспроизведения: {str(e)}")
            self.statusbar_label.setText("Ошибка воспроизведения")
            logging.error(f"Ошибка воспроизведения канала: {str(e)}")
            QMessageBox.critical(self, "Ошибка воспроизведения", 
                                f"Не удалось воспроизвести канал '{channel['name']}'.\n{str(e)}")
    
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
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        else:
            self.play()

    def play(self):
        """Начать воспроизведение"""
        self.media_player.play()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

    def stop(self):
        """Остановить воспроизведение"""
        self.media_player.stop()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.info_label.setText("Остановлено")
        self.channel_name_label.setText("Нет воспроизведения")
        self.statusbar_label.setText("Остановлено")

    def toggle_fullscreen(self):
        """Переключение полноэкранного режима"""
        if self.isFullScreen():
            # Возвращаемся из полноэкранного режима
            self.showNormal()
            
            # Удаляем прозрачный перехватчик кликов, если есть
            if hasattr(self, 'exit_fs_button') and self.exit_fs_button:
                self.exit_fs_button.deleteLater()
                self.exit_fs_button = None
            
            # Возвращаем видеофрейм в основной макет
            self.video_frame.setParent(None)
            right_layout = self.findChild(QWidget, "right_panel").layout()
            right_layout.insertWidget(1, self.video_frame)
            
            # Показываем интерфейс
            self.main_splitter.setVisible(True)
            self.menuBar().setVisible(True)
            self.statusBar().setVisible(True)
            
            # Восстанавливаем обработчик клика для метки
            try:
                self.video_frame_label.clicked.disconnect()
            except TypeError:
                pass
            self.video_frame_label.clicked.connect(self.toggle_fullscreen)
        else:
            # Переходим в полноэкранный режим
            
            # Сначала запоминаем панель с видео
            self.right_panel = self.findChild(QWidget, "right_panel")
            
            # Извлекаем видеофрейм из текущего макета и делаем его основным виджетом
            self.video_frame.setParent(None)
            self.video_frame.setGeometry(0, 0, self.width(), self.height())
            self.video_frame.setParent(self)
            self.video_frame.show()
            
            # Скрываем интерфейс
            self.main_splitter.setVisible(False)
            self.menuBar().setVisible(False)
            self.statusBar().setVisible(False)
            
            # Переходим в полноэкранный режим
            self.showFullScreen()
            
            # Настраиваем видеофрейм под размер экрана
            self.video_frame.setGeometry(0, 0, self.width(), self.height())
            
            # Создаем компактную кнопку с иконкой для выхода из полноэкранного режима
            self.exit_fs_button = QPushButton(self)
            self.exit_fs_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
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
            
            # Устанавливаем размер кнопки
            self.exit_fs_button.setFixedSize(30, 30)
            self.exit_fs_button.clicked.connect(self.toggle_fullscreen)
            self.exit_fs_button.move(self.width() - 40, 10)
            self.exit_fs_button.show()
            self.exit_fs_button.raise_()
            
            # Создаем временную метку для выхода из полноэкранного режима
            hint_label = QLabel("Нажмите ESC или на X для выхода из полноэкранного режима", self)
            hint_label.setStyleSheet("background-color: rgba(0, 0, 0, 150); color: white; padding: 10px; border-radius: 5px;")
            hint_label.setAlignment(Qt.AlignCenter)
            hint_label.setGeometry(self.width() // 2 - 250, self.height() - 50, 500, 40)
            hint_label.show()
            hint_label.raise_()
            QTimer.singleShot(3000, hint_label.deleteLater)

    def resizeEvent(self, event):
        """Обработчик изменения размера окна"""
        # Если в полноэкранном режиме, растягиваем видеофрейм на всё окно
        if self.isFullScreen() and self.video_frame.parent() == self:
            self.video_frame.setGeometry(0, 0, self.width(), self.height())
            # Обновляем положение кнопки выхода при изменении размера
            if hasattr(self, 'exit_fs_button') and self.exit_fs_button:
                self.exit_fs_button.move(self.width() - 270, 20)
        super().resizeEvent(event)

    def update_ui(self):
        """Обновление UI состояния"""
        # Обновляем состояние кнопки воспроизведения
        if self.media_player.is_playing():
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            
        # Если медиаплеер в состоянии воспроизведения, но в буферизации
        state = self.media_player.get_state()
        if state == vlc.State.Playing and not self.media_player.is_playing():
            self.info_label.setText("Буферизация...")
            self.statusbar_label.setText("Буферизация...")
        
        # Если воспроизведение идет, но нет видео трека - пробуем перезапустить
        if self.media_player.is_playing() and not self.media_player.has_vout():
            # Показываем информацию о проблеме с видео
            if hasattr(self, 'video_retry_count'):
                self.video_retry_count += 1
                #if self.video_retry_count > 10:  # Если более 10 попыток, останавливаем
                #    self.info_label.setText("Нет видеопотока. Возможно аудио-канал.")
                #    self.statusbar_label.setText("Нет видеопотока")
                #    delattr(self, 'video_retry_count')
            else:
                self.video_retry_count = 1
        elif self.media_player.is_playing() and self.media_player.has_vout():
            if hasattr(self, 'video_retry_count'):
                delattr(self, 'video_retry_count')

    def handle_error(self, event):
        """Обработчик ошибок воспроизведения"""
        self.progress_bar.setVisible(False)
        
        try:
            if 0 <= self.current_channel_index < len(self.channels):
                name = self.channels[self.current_channel_index].get('name', 'Неизвестный канал')
                error_message = f"Ошибка воспроизведения: {name}"
            else:
                name = "Неизвестный канал"
                error_message = "Ошибка воспроизведения потока"
                
            self.info_label.setText(error_message)
            self.statusbar_label.setText(error_message)
            
            # Показываем уведомление об ошибке через QTimer для избежания блокировки UI
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "Ошибка воспроизведения", 
                f"Не удалось воспроизвести канал '{name}'.\nПроверьте соединение с интернетом или попробуйте другой канал."))
        except Exception as e:
            print(f"Ошибка при обработке события MediaPlayerEncounteredError: {e}")

    def media_playing(self, event):
        """Событие начала воспроизведения"""
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
        self.tray_icon = QSystemTrayIcon(self.style().standardIcon(QStyle.SP_MediaPlay), self)
        
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
                # Спрашиваем, копировать ли файл в текущую директорию
                reply = QMessageBox.question(
                    self, 'Копирование плейлиста', 
                    'Копировать плейлист в директорию программы?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                
                target_file = "IPTV_SHARED.m3u"
                
                if reply == QMessageBox.Yes:
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
                    
                    # Обновляем историю плейлистов
                    self.update_recent_playlists(target_file)
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
                    
                    # Обновляем историю плейлистов
                    self.update_recent_playlists(filename)
                    self.current_playlist = filename
                    
                    # Сохраняем путь к временному плейлисту
                    self.temp_playlist_path = filename
                    
                    # Загружаем плейлист
                    self.load_external_playlist(filename)
                    self.fill_channel_list()
                    
                    # Обновляем меню недавних плейлистов
                    self.update_recent_menu()
                    
                    self.info_label.setText(f"Загружен внешний плейлист: {os.path.basename(filename)}")
                    
                    # Обновляем отображение количества каналов
                    total_channels = len(self.channels)
                    visible_channels = total_channels - len(self.hidden_channels)
                    self.statusbar_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
                    
                    # Автоматически выбираем первый канал 
                    self.select_first_channel()
                    
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть плейлист: {str(e)}")

    def update_recent_playlists(self, playlist_path):
        """Обновляет список недавно использованных плейлистов"""
        # Удаляем путь из списка, если он уже есть
        if playlist_path in self.recent_playlists:
            self.recent_playlists.remove(playlist_path)
            
        # Добавляем путь в начало списка
        self.recent_playlists.insert(0, playlist_path)
        
        # Ограничиваем список до 5 элементов
        self.recent_playlists = self.recent_playlists[:5]
        
        # Обновляем текущий плейлист
        self.current_playlist = playlist_path
        
        # Сохраняем настройки
        self.save_config()
        
        # Обновляем меню недавних плейлистов
        if hasattr(self, 'recent_menu'):
            self.update_recent_menu()
        
    def select_first_channel(self):
        """Выбирает первый канал в списке для быстрого старта просмотра"""
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
                        # Получаем индекс канала и воспроизводим его
                        channel_index = channel_item.data(0, Qt.UserRole)
                        if channel_index is not None:
                            self.play_channel(channel_index)
            else:  # Обычный список
                if self.channel_list.count() > 0:
                    self.channel_list.setCurrentRow(0)
                    # Воспроизведение происходит автоматически через событие выбора

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
                    
                    parts = line.split(',', 1)
                    if len(parts) > 1:
                        channel = {
                            'name': parts[1].strip(), 
                            'options': {},
                            'category': group_title,
                            'tvg_id': tvg_id
                        }
                        
                        # Добавляем категорию в словарь, если её ещё нет
                        if group_title not in self.categories:
                            self.categories[group_title] = []
                
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
        url, ok = QInputDialog.getText(
            self, "Добавить плейлист из URL", 
            "Введите URL плейлиста:", 
            text="http://"
        )
        
        if ok and url:
            # Проверяем, не загружается ли тот же URL повторно
            if url == self.current_playlist:
                reply = QMessageBox.question(
                    self, 'Повторная загрузка', 
                    'Этот плейлист уже загружен. Загрузить повторно?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    return
            
            try:
                # Создаем временный файл для загрузки
                temp_file = "temp_playlist.m3u"
                
                # Показываем прогресс
                self.info_label.setText(f"Скачивание плейлиста из {url}...")
                self.statusbar_label.setText("Скачивание плейлиста...")
                self.progress_bar.setVisible(True)
                
                def download_finished(success, error_message, source_url):
                    self.progress_bar.setVisible(False)
                    
                    if success:
                        try:
                            # Обновляем историю плейлистов
                            if source_url:
                                self.update_recent_playlists(source_url)
                                self.current_playlist = source_url
                            
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
                            
                            # Автоматически выбираем первый канал 
                            self.select_first_channel()
                        except Exception as e:
                            QMessageBox.critical(
                                self, "Ошибка", f"Не удалось загрузить плейлист: {str(e)}"
                            )
                    else:
                        QMessageBox.critical(
                            self, "Ошибка", f"Не удалось загрузить плейлист: {error_message}"
                        )
                
                # Создаем поток и запускаем его
                self.download_thread = PlaylistDownloadThread(url, temp_file)
                self.download_thread.finished.connect(download_finished)
                self.download_thread.start()
                
            except Exception as e:
                self.progress_bar.setVisible(False)
                QMessageBox.critical(
                    self, "Ошибка", f"Не удалось загрузить плейлист: {str(e)}"
                )

    def reload_playlist(self):
        """Перезагружает плейлист"""
        self.stop()
        self.channels = []
        self.categories = {"Все каналы": []}
        
        if hasattr(self, 'temp_playlist_path') and self.temp_playlist_path:
            self.load_external_playlist(self.temp_playlist_path)
        else:
            self.load_playlist()
            
        self.fill_channel_list()
        self.info_label.setText("Плейлист перезагружен")
        
        # Обновляем отображение количества каналов в статус-баре
        total_channels = len(self.channels)
        visible_channels = total_channels - len(self.hidden_channels)
        self.statusbar_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
        
        # Автоматически выбираем первый канал
        self.select_first_channel()

    def toggle_favorites(self):
        """Переключение отображения избранных каналов"""
        if self.show_favorites:
            self.show_favorites = False
            self.favorites_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
            self.fill_channel_list()
            
            # Обновляем отображение количества каналов
            total_channels = len(self.channels)
            visible_channels = total_channels - len(self.hidden_channels)
            self.statusbar_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
            self.playlist_info_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
        else:
            self.show_favorites = True
            self.show_hidden = False
            self.hidden_button.setIcon(self.style().standardIcon(QStyle.SP_DialogNoButton))
            self.favorites_button.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
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
            self.hidden_button.setIcon(self.style().standardIcon(QStyle.SP_DialogNoButton))
            self.fill_channel_list()
            
            # Обновляем отображение количества каналов
            total_channels = len(self.channels)
            visible_channels = total_channels - len(self.hidden_channels)
            self.statusbar_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
            self.playlist_info_label.setText(f"Всего каналов: {total_channels} (видимых: {visible_channels})")
        else:
            self.show_hidden = True
            self.show_favorites = False
            self.favorites_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
            self.hidden_button.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
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
        elif event.key() == Qt.Key_Space:
            self.play_pause()
        elif event.key() == Qt.Key_F:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key_A:
            self.next_audio_track()
        else:
            super().keyPressEvent(event)

    def load_config(self):
        """Загружает конфигурацию из файла"""
        default_config = {
            "volume": 70,
            "last_channel": None,
            "favorites": [],
            "hidden_channels": [],
            "recent_playlists": ["IPTV_SHARED.m3u"],
            "current_playlist": "IPTV_SHARED.m3u"
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Проверяем, что все ключи по умолчанию присутствуют
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                
                # Проверяем, что playlist существует
                if config.get("current_playlist") and not os.path.exists(config.get("current_playlist")):
                    # Проверяем, есть ли в recent_playlists существующие плейлисты
                    existing_playlists = [p for p in config.get("recent_playlists", []) if os.path.exists(p)]
                    if existing_playlists:
                        config["current_playlist"] = existing_playlists[0]
                    else:
                        # Если ни один плейлист не существует, сбрасываем на стандартный
                        if os.path.exists("IPTV_SHARED.m3u"):
                            config["current_playlist"] = "IPTV_SHARED.m3u"
                            config["recent_playlists"] = ["IPTV_SHARED.m3u"]
                        else:
                            # Если даже стандартного нет, создаем пустой плейлист
                            with open("IPTV_SHARED.m3u", "w", encoding="utf-8") as f:
                                f.write("#EXTM3U\n")
                            config["current_playlist"] = "IPTV_SHARED.m3u"
                            config["recent_playlists"] = ["IPTV_SHARED.m3u"]
                
                return config
            else:
                # Если файл не существует, создаем базовый файл плейлиста
                if not os.path.exists("IPTV_SHARED.m3u"):
                    with open("IPTV_SHARED.m3u", "w", encoding="utf-8") as f:
                        f.write("#EXTM3U\n")
                # Удаляю создание директории для логотипов
                return default_config
        except Exception as e:
            print(f"Ошибка при загрузке конфигурации: {e}")
            # Возвращаем конфигурацию по умолчанию
            return default_config
    
    def save_config(self):
        """Сохраняет конфигурацию в файл"""
        # Обновляем текущие параметры
        self.config["volume"] = self.volume_slider.value()
        if self.current_channel_index >= 0 and self.current_channel_index < len(self.channels):
            self.config["last_channel"] = self.channels[self.current_channel_index]['name']
        self.config["favorites"] = self.favorites
        self.config["hidden_channels"] = self.hidden_channels
        self.config["recent_playlists"] = self.recent_playlists
        self.config["current_playlist"] = self.current_playlist
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка при сохранении конфигурации: {e}")
            
    def update_playlist_from_url(self):
        """Обновляет плейлист из интернета"""
        playlist_file = "IPTV_SHARED.m3u"
        playlist_url = "https://gitlab.com/iptv135435/iptvshared/raw/main/IPTV_SHARED.m3u"
        
        try:
            # Создаем резервную копию текущего плейлиста
            if os.path.exists(playlist_file):
                backup_file = f"{playlist_file}.backup"
                with open(playlist_file, 'rb') as src:
                    with open(backup_file, 'wb') as dst:
                        dst.write(src.read())
            
            # Скачиваем плейлист
            self.info_label.setText(f"Скачивание плейлиста из {playlist_url}...")
            self.statusbar_label.setText("Скачивание плейлиста...")
            self.progress_bar.setVisible(True)
            
            def download_finished(success, error_message):
                self.progress_bar.setVisible(False)
                
                if success:
                    try:
                        # Проверяем, что файл действительно загружен и имеет формат M3U
                        with open(playlist_file, 'r', encoding='utf-8', errors='ignore') as f:
                            first_line = f.readline().strip()
                            if not first_line.startswith('#EXTM3U'):
                                raise ValueError("Файл не является плейлистом M3U")
                        
                        # Обновляем историю плейлистов
                        self.update_recent_playlists(playlist_file)
                        self.current_playlist = playlist_file
                        
                        self.info_label.setText("Плейлист успешно обновлен")
                        self.statusbar_label.setText("Плейлист успешно обновлен")
                        
                        # Перезагружаем плейлист
                        self.reload_playlist()
                        
                        # Обновляем меню недавних плейлистов
                        self.update_recent_menu()
                        
                        QMessageBox.information(self, "Информация", "Плейлист успешно обновлен из интернета")
                    except Exception as e:
                        # Если произошла ошибка при проверке файла, восстанавливаем резервную копию
                        self.info_label.setText(f"Ошибка обновления плейлиста: {str(e)}")
                        self.statusbar_label.setText("Ошибка обновления плейлиста")
                        QMessageBox.critical(self, "Ошибка", f"Не удалось обновить плейлист: {str(e)}")
                        
                        # Восстанавливаем из резервной копии если она есть
                        backup_file = f"{playlist_file}.backup"
                        if os.path.exists(backup_file):
                            with open(backup_file, 'rb') as src:
                                with open(playlist_file, 'wb') as dst:
                                    dst.write(src.read())
                else:
                    self.info_label.setText(f"Ошибка обновления плейлиста: {error_message}")
                    self.statusbar_label.setText("Ошибка обновления плейлиста")
                    QMessageBox.critical(self, "Ошибка", f"Не удалось обновить плейлист: {error_message}")
            
            # Создаем и запускаем поток
            self.download_thread = DownloadThread(playlist_url, playlist_file)
            self.download_thread.finished.connect(download_finished)
            self.download_thread.start()
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            self.info_label.setText(f"Ошибка обновления плейлиста: {str(e)}")
            self.statusbar_label.setText("Ошибка обновления плейлиста")
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить плейлист: {str(e)}")
    
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
        """Настраивает статус бар"""
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)
        
        # Добавляем информацию о канале
        self.statusbar_label = QLabel("Готов к воспроизведению")
        statusbar.addWidget(self.statusbar_label, 1)
    
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

def main():
    app = QApplication(sys.argv)
    
    # Устанавливаем иконку приложения
    app.setWindowIcon(QIcon(app.style().standardIcon(QStyle.SP_MediaPlay).pixmap(QSize(128, 128))))
    
    # Темная тема для всего приложения
    app.setStyle("Fusion")
    
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.Active, QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
    dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, Qt.darkGray)
    dark_palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
    dark_palette.setColor(QPalette.Disabled, QPalette.Light, QColor(53, 53, 53))
    
    app.setPalette(dark_palette)
    
    player = IPTVPlayer()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 