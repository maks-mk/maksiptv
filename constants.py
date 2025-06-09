"""
Константы и стили для MaksIPTV Player
Версия 0.13.0

Содержит все константы, стили CSS и настройки по умолчанию.
"""

# Определение стилей приложения
STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #f0f0f0;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QLabel {
    color: #f0f0f0;
    font-size: 12px;
    font-weight: 400;
}

QLabel#channelNameLabel {
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
    padding: 6px 12px;
    background-color: rgba(90, 141, 176, 0.25);
    border-radius: 8px;
    border: 1px solid rgba(90, 141, 176, 0.4);
}

QLabel#channelsHeader {
    font-size: 13px;
    font-weight: 600;
    color: #4080b0;
    padding: 4px 0px;
    background-color: transparent;
}

QLabel#playlistInfo {
    font-size: 11px;
    color: #b0b0b0;
    padding: 2px 4px;
}

QTreeWidget, QListWidget, QComboBox, QLineEdit {
    background-color: #2a2a2a;
    color: #f0f0f0;
    border: 1px solid #404040;
    border-radius: 6px;
    padding: 3px 6px;
    font-size: 12px;
    selection-background-color: #4080b0;
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

# Константы приложения
APP_NAME = "MaksIPTV Плеер"
APP_VERSION = "0.13.0"

# Настройки по умолчанию
DEFAULT_WINDOW_SIZE = [1100, 650]
DEFAULT_WINDOW_POSITION = [50, 40]
DEFAULT_VOLUME = 50
DEFAULT_TIMEOUT = 10
MAX_RETRY_COUNT = 3
MAX_CONCURRENT_DOWNLOADS = 5
MAX_CONCURRENT_THREADS = 8

# URL для обновления плейлиста
DEFAULT_PLAYLIST_URL = "https://gitlab.com/iptv135435/iptvshared/raw/main/IPTV_SHARED.m3u"

# Размеры UI элементов
BUTTON_SIZE = (28, 28)
ICON_SIZE = (14, 14)
LARGE_BUTTON_SIZE = (32, 32)
LARGE_ICON_SIZE = (16, 16)
LOGO_SIZE = (32, 32)

# Домены для пропуска при загрузке логотипов
SKIP_LOGO_DOMAINS = [
    'fe-ural.svc.iptv.rt.ru', 'fe-sib.svc.iptv.rt.ru',
    'fe-sth.svc.iptv.rt.ru', 'fe-vlg.svc.iptv.rt.ru',
    'fe-nw.svc.iptv.rt.ru', 'picon.ml', 'yt3.ggpht.com',
    'pbs.twimg.com', 'television-live.com', 'tsifra-tv.ru',
    'nm-tv.ru', 'gas-kvas.com', 'online-television.net'
]
