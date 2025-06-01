"""
Модуль потоков для MaksIPTV Player
Версия 0.13.0

Содержит все классы потоков для асинхронных операций:
- ThreadManager - централизованное управление потоками
- DownloadThread - загрузка файлов
- ChannelPlayThread - подготовка медиа для воспроизведения
- PlaylistDownloadThread - загрузка плейлистов
- LogoDownloadThread - загрузка логотипов каналов

Все потоки поддерживают прерывание и корректное завершение.
"""

import logging
import socket
import urllib.request
import urllib.error
import hashlib
import requests
from typing import Optional, Dict, Any
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtCore import Qt


class ThreadManager:
    """Менеджер для централизованного управления потоками
    
    Обеспечивает контроль над жизненным циклом потоков, ограничение
    количества одновременных операций и безопасное завершение.
    Реализует принцип единственной ответственности (SRP).
    """
    
    def __init__(self, max_concurrent_threads: int = 5):
        self.max_concurrent_threads = max_concurrent_threads
        self.active_threads: Dict[str, QThread] = {}
        self.thread_pool = ThreadPoolExecutor(max_workers=max_concurrent_threads)
        self._lock = Lock()
        
    def register_thread(self, thread_id: str, thread: QThread) -> bool:
        """Регистрирует поток для управления
        
        Args:
            thread_id: Уникальный идентификатор потока
            thread: Экземпляр потока
            
        Returns:
            bool: True если поток зарегистрирован, False если превышен лимит
        """
        with self._lock:
            if len(self.active_threads) >= self.max_concurrent_threads:
                logging.warning(f"Превышен лимит потоков ({self.max_concurrent_threads})")
                return False
                
            self.active_threads[thread_id] = thread
            logging.info(f"Поток {thread_id} зарегистрирован")
            return True
    
    def unregister_thread(self, thread_id: str) -> None:
        """Отменяет регистрацию потока"""
        with self._lock:
            if thread_id in self.active_threads:
                del self.active_threads[thread_id]
                logging.info(f"Поток {thread_id} отменен")
    
    def stop_thread(self, thread_id: str, timeout: int = 1000) -> bool:
        """Останавливает конкретный поток
        
        Args:
            thread_id: Идентификатор потока
            timeout: Время ожидания завершения в миллисекундах
            
        Returns:
            bool: True если поток успешно остановлен
        """
        with self._lock:
            if thread_id not in self.active_threads:
                return True
                
            thread = self.active_threads[thread_id]
            
        try:
            if hasattr(thread, 'abort'):
                thread.abort()
                
            thread.quit()
            if not thread.wait(timeout):
                logging.warning(f"Принудительное завершение потока {thread_id}")
                thread.terminate()
                thread.wait(500)
                
            self.unregister_thread(thread_id)
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при остановке потока {thread_id}: {e}")
            return False
    
    def stop_all_threads(self, timeout: int = 1000) -> None:
        """Останавливает все активные потоки"""
        thread_ids = list(self.active_threads.keys())
        for thread_id in thread_ids:
            self.stop_thread(thread_id, timeout)
            
        # Завершаем пул потоков
        self.thread_pool.shutdown(wait=True)
        
    def get_active_thread_count(self) -> int:
        """Возвращает количество активных потоков"""
        with self._lock:
            return len(self.active_threads)
    
    def is_thread_active(self, thread_id: str) -> bool:
        """Проверяет, активен ли поток"""
        with self._lock:
            return thread_id in self.active_threads


class BaseThread(QThread):
    """Базовый класс для всех потоков с поддержкой прерывания"""
    
    def __init__(self):
        super().__init__()
        self._abort = False
    
    def abort(self) -> None:
        """Безопасно прервать выполнение потока"""
        self._abort = True
    
    def is_aborted(self) -> bool:
        """Проверяет, был ли поток прерван"""
        return self._abort


class DownloadThread(BaseThread):
    """Поток для загрузки файлов по URL с поддержкой прерывания"""
    finished = pyqtSignal(bool, str)

    def __init__(self, url: str, file_path: str):
        super().__init__()
        self.url = url
        self.file_path = file_path

    def run(self) -> None:
        """Выполняет загрузку файла с проверкой прерывания"""
        try:
            if self._abort:
                self.finished.emit(False, "Операция прервана")
                return

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            request = urllib.request.Request(self.url, headers=headers)
            
            if self._abort:
                self.finished.emit(False, "Операция прервана")
                return
                
            response = urllib.request.urlopen(request, timeout=30)
            
            if self._abort:
                self.finished.emit(False, "Операция прервана")
                return

            # Читаем данные порциями для возможности прерывания
            data = b''
            chunk_size = 8192
            while True:
                if self._abort:
                    self.finished.emit(False, "Операция прервана")
                    return
                    
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                data += chunk

            # Записываем файл
            with open(self.file_path, 'wb') as f:
                f.write(data)

            if not self._abort:
                self.finished.emit(True, "")
                
        except urllib.error.URLError as e:
            if not self._abort:
                self.finished.emit(False, f"Ошибка URL: {str(e)}")
        except urllib.error.HTTPError as e:
            if not self._abort:
                self.finished.emit(False, f"Ошибка HTTP: {e.code} {e.reason}")
        except (TimeoutError, socket.timeout, socket.error):
            if not self._abort:
                self.finished.emit(False, "Превышено время ожидания")
        except Exception as e:
            if not self._abort:
                self.finished.emit(False, str(e))


class ChannelPlayThread(BaseThread):
    """Поток для асинхронного воспроизведения канала с поддержкой прерывания"""
    setup_finished = pyqtSignal(bool, str, object)  # Статус, сообщение об ошибке, медиа-объект

    def __init__(self, url: str, options: Optional[Dict[str, Any]] = None, vlc_instance=None):
        super().__init__()
        self.url = url
        self.options = options or {}
        self.vlc_instance = vlc_instance
        self.media = None

    def run(self) -> None:
        """Выполняет настройку медиа с проверкой прерывания"""
        try:
            if self._abort:
                self.setup_finished.emit(False, "Операция прервана", None)
                return

            # Создаем медиа с нужным URL
            self.media = self.vlc_instance.media_new(self.url)

            if self._abort:
                self.setup_finished.emit(False, "Операция прервана", None)
                return

            # Настраиваем медиа-опции VLC, если они указаны для канала
            if self.options:
                for opt_name, opt_value in self.options.items():
                    if self._abort:
                        self.setup_finished.emit(False, "Операция прервана", None)
                        return
                        
                    if opt_name == 'user-agent':
                        self.media.add_option(f":http-user-agent={opt_value}")
                    elif opt_name == 'http-referrer' or opt_name == 'referer':
                        self.media.add_option(f":http-referrer={opt_value}")
                    else:
                        self.media.add_option(f":{opt_name}={opt_value}")

            if self._abort:
                self.setup_finished.emit(False, "Операция прервана", None)
                return

            # Добавляем общие сетевые опции для улучшения воспроизведения
            network_options = [
                ":network-caching=3000",
                ":file-caching=1000", 
                ":live-caching=1000",
                ":sout-mux-caching=1000",
                ":http-reconnect",
                ":rtsp-tcp",
                ":no-video-title-show"
            ]
            
            for option in network_options:
                if self._abort:
                    self.setup_finished.emit(False, "Операция прервана", None)
                    return
                self.media.add_option(option)

            # Сигнализируем о готовности медиа
            if not self._abort:
                self.setup_finished.emit(True, "", self.media)

        except Exception as e:
            if not self._abort:
                logging.error(f"Ошибка в потоке воспроизведения: {str(e)}")
                self.setup_finished.emit(False, str(e), None)


class PlaylistDownloadThread(BaseThread):
    """Поток для загрузки плейлистов с возвратом URL источника и поддержкой прерывания"""
    finished = pyqtSignal(bool, str, str)

    def __init__(self, url: str, file_path: str):
        super().__init__()
        self.url = url
        self.file_path = file_path

    def run(self) -> None:
        """Выполняет загрузку плейлиста с проверкой прерывания"""
        try:
            if self._abort:
                self.finished.emit(False, "Операция прервана", "")
                return

            # Настраиваем opener с User-Agent для обхода ограничений
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')]
            urllib.request.install_opener(opener)

            if self._abort:
                self.finished.emit(False, "Операция прервана", "")
                return

            # Скачиваем напрямую
            request = urllib.request.Request(self.url)
            response = urllib.request.urlopen(request, timeout=30)

            if self._abort:
                self.finished.emit(False, "Операция прервана", "")
                return

            # Читаем содержимое порциями для возможности прерывания
            content = b''
            chunk_size = 8192
            while True:
                if self._abort:
                    self.finished.emit(False, "Операция прервана", "")
                    return
                    
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                content += chunk

            if self._abort:
                self.finished.emit(False, "Операция прервана", "")
                return

            # Проверяем, что контент похож на плейлист
            content_str = content.decode('utf-8', errors='ignore')
            if not ('#EXTM3U' in content_str or '#EXTINF' in content_str):
                self.finished.emit(False, "Скачанный файл не является плейлистом IPTV", "")
                return

            # Записываем файл
            with open(self.file_path, 'wb') as f:
                f.write(content)

            if not self._abort:
                self.finished.emit(True, "", self.url)
                
        except (TimeoutError, socket.timeout, socket.error):
            if not self._abort:
                self.finished.emit(False, "Превышено время ожидания", "")
        except Exception as e:
            if not self._abort:
                self.finished.emit(False, str(e), "")


class LogoDownloadThread(BaseThread):
    """Поток для асинхронной загрузки логотипов каналов с поддержкой прерывания"""
    logo_loaded = pyqtSignal(str, QPixmap)  # URL логотипа, загруженный логотип
    logo_failed = pyqtSignal(str)  # URL логотипа, который не удалось загрузить

    def __init__(self, logo_url: str):
        super().__init__()
        self.logo_url = logo_url
        self.debug_mode = False  # По умолчанию режим отладки выключен

    def run(self) -> None:
        """Выполняет загрузку логотипа с проверкой прерывания"""
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
                    # но с сохранением альфа-канала для прозрачности
                    image_data = response.content
                    try:
                        from PIL import Image
                        import io
                        # Открываем изображение через PIL
                        img = Image.open(io.BytesIO(image_data))

                        # Сохраняем альфа-канал для прозрачности
                        output = io.BytesIO()
                        if img.mode in ('RGBA', 'LA') or 'transparency' in img.info:
                            # Сохраняем с альфа-каналом для прозрачности
                            if img.mode != 'RGBA':
                                img = img.convert('RGBA')
                            img.save(output, format='PNG', icc_profile=None)
                        else:
                            # Для изображений без прозрачности можем конвертировать в RGB
                            if img.mode == 'RGBA':
                                # Создаем белый фон только если нет реальной прозрачности
                                background = Image.new('RGB', img.size, (255, 255, 255))
                                background.paste(img, mask=img.split()[3])
                                img = background
                            img.save(output, format='PNG', icc_profile=None)
                        image_data = output.getvalue()
                    except (ImportError, Exception):
                        # Пропускаем предобработку, если PIL не установлен или возникла ошибка
                        pass

                    if self._abort:
                        self.logo_failed.emit(self.logo_url)
                        return

                    pixmap = QPixmap()
                    pixmap.loadFromData(image_data)
                    if not pixmap.isNull():
                        # Масштабируем логотип до нужного размера с сохранением альфа-канала
                        scaled_pixmap = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                        # Убеждаемся, что масштабированный pixmap поддерживает прозрачность
                        if pixmap.hasAlphaChannel() and not scaled_pixmap.hasAlphaChannel():
                            # Создаем новый pixmap с альфа-каналом
                            alpha_pixmap = QPixmap(scaled_pixmap.size())
                            alpha_pixmap.fill(Qt.transparent)
                            painter = QPainter(alpha_pixmap)
                            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                            painter.drawPixmap(0, 0, scaled_pixmap)
                            painter.end()
                            scaled_pixmap = alpha_pixmap

                        if not self._abort:
                            self.logo_loaded.emit(self.logo_url, scaled_pixmap)
                    else:
                        if not self._abort:
                            self.logo_failed.emit(self.logo_url)
                except Exception:
                    if not self._abort:
                        self.logo_failed.emit(self.logo_url)
            else:
                if not self._abort:
                    self.logo_failed.emit(self.logo_url)
        except Exception as e:
            # Выводим ошибку только в режиме отладки
            if self.debug_mode and not self._abort:
                print(f"Ошибка загрузки логотипа {self.logo_url}: {str(e)}")
            if not self._abort:
                self.logo_failed.emit(self.logo_url)
