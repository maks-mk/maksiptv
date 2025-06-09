"""
Модуль управления медиаплеером для MaksIPTV Player
Версия 0.13.0

Содержит MediaPlayerManager для расширенного управления воспроизведением,
включая перемотку, позицию и временные метки.
"""

import logging
import vlc
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QSlider
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QMetaObject, pyqtSlot
from PyQt5.QtGui import QPixmap
import qtawesome as qta


class MediaPlayerManager(QObject):
    """Менеджер для расширенного управления медиаплеером

    Предоставляет функциональность перемотки, отображения позиции
    и управления временными метками для потоков, которые это поддерживают.
    """

    # Сигналы для безопасного обновления UI из других потоков
    media_info_changed = pyqtSignal()

    def __init__(self, vlc_player, parent=None):
        super().__init__(parent)
        self.vlc_player = vlc_player
        self.parent = parent
        self.is_seekable = False
        self.duration = 0
        self.position = 0

        # Таймер для обновления позиции
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position)
        self.position_timer.setInterval(1000)  # Обновляем каждую секунду

        # Флаг для предотвращения рекурсивных обновлений
        self.updating_position = False

        # Флаг для отслеживания перетаскивания слайдера
        self._slider_being_dragged = False

        # Текущая скорость воспроизведения
        self.playback_rate = 1.0

        # Информация о треках
        self.audio_tracks = []
        self.subtitle_tracks = []
        self.current_audio_track = -1
        self.current_subtitle_track = -1

        # Настройки снимков экрана
        self.auto_screenshot_enabled = False
        self.screenshot_quality = 'high'  # 'low', 'medium', 'high'

        # Подключаем события VLC для отслеживания изменений медиа
        self.setup_vlc_events()

        # Подключаем сигнал для безопасного обновления UI
        self.media_info_changed.connect(self.update_seek_ui)

    def setup_vlc_events(self):
        """Настраивает обработчики событий VLC с безопасной обработкой потоков"""
        if not self.vlc_player:
            return

        try:
            event_manager = self.vlc_player.event_manager()

            # Подключаем события для отслеживания изменений медиа
            # Используем безопасные обработчики, которые вызывают методы через Qt сигналы
            event_manager.event_attach(vlc.EventType.MediaPlayerLengthChanged, self.on_length_changed_safe)
            event_manager.event_attach(vlc.EventType.MediaPlayerSeekableChanged, self.on_seekable_changed_safe)
            event_manager.event_attach(vlc.EventType.MediaPlayerTimeChanged, self.on_time_changed_safe)

            logging.info("События VLC настроены с безопасной обработкой потоков")
        except Exception as e:
            logging.error(f"Ошибка при настройке событий VLC: {e}")

    def on_length_changed_safe(self, event):
        """Безопасный обработчик изменения длительности медиа"""
        # Вызываем метод в главном потоке Qt
        QMetaObject.invokeMethod(self, "handle_length_changed", Qt.QueuedConnection)

    def on_seekable_changed_safe(self, event):
        """Безопасный обработчик изменения возможности перемотки"""
        # Вызываем метод в главном потоке Qt
        QMetaObject.invokeMethod(self, "handle_seekable_changed", Qt.QueuedConnection)

    def on_time_changed_safe(self, event):
        """Безопасный обработчик изменения времени"""
        # Вызываем метод в главном потоке Qt (но не слишком часто)
        if not hasattr(self, '_last_time_event'):
            self._last_time_event = 0

        import time
        current_time = time.time()
        if current_time - self._last_time_event > 0.5:  # Максимум раз в 0.5 секунды
            self._last_time_event = current_time
            QMetaObject.invokeMethod(self, "handle_time_changed", Qt.QueuedConnection)

    @pyqtSlot()
    def handle_length_changed(self):
        """Обработчик изменения длительности в главном потоке Qt"""
        if not self.vlc_player:
            return

        duration_ms = self.vlc_player.get_length()
        old_duration = self.duration
        self.duration = duration_ms / 1000 if duration_ms > 0 else 0

        if abs(self.duration - old_duration) > 1:
            logging.info(f"Длительность изменена через событие VLC: {self.duration} сек")
            self.update_seek_ui()

    @pyqtSlot()
    def handle_seekable_changed(self):
        """Обработчик изменения возможности перемотки в главном потоке Qt"""
        if not self.vlc_player:
            return

        old_seekable = self.is_seekable
        self.is_seekable = self.vlc_player.is_seekable()

        # Принудительно включаем перемотку для файлов с длительностью
        if self.duration > 0:
            self.is_seekable = True

        if self.is_seekable != old_seekable:
            logging.info(f"Возможность перемотки изменена через событие VLC: {self.is_seekable}")
            self.update_seek_ui()

    @pyqtSlot()
    def handle_time_changed(self):
        """Обработчик изменения времени в главном потоке Qt"""
        # Этот метод вызывается не чаще раза в 0.5 секунды
        # Основное обновление позиции происходит через update_position
        pass

    def create_seek_panel(self):
        """Создает панель перемотки с временными метками
        
        Returns:
            QWidget: Панель с элементами управления перемоткой
        """
        seek_panel = QWidget()
        seek_layout = QHBoxLayout(seek_panel)
        seek_layout.setContentsMargins(0, 0, 0, 0)
        seek_layout.setSpacing(8)
        
        # Метка текущего времени
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setStyleSheet("color: #a0a0a0; font-size: 11px; min-width: 35px;")
        
        # Слайдер позиции
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setToolTip("Позиция воспроизведения (работает только для записей)")
        self.position_slider.setRange(0, 1000)  # Используем 1000 для точности
        self.position_slider.setValue(0)
        self.position_slider.setEnabled(True)  # ВСЕГДА включен
        
        # Подключаем события слайдера
        self.position_slider.sliderPressed.connect(self.on_seek_start)
        self.position_slider.sliderReleased.connect(self.on_seek_end)
        self.position_slider.sliderMoved.connect(self.on_position_changed)  # Только при движении пользователем
        self.position_slider.valueChanged.connect(self.on_value_changed)    # Для всех изменений
        
        # Метка общей длительности
        self.duration_label = QLabel("00:00")
        self.duration_label.setStyleSheet("color: #a0a0a0; font-size: 11px; min-width: 35px;")
        
        # Индикатор типа потока
        self.stream_type_label = QLabel("LIVE")
        self.stream_type_label.setStyleSheet("""
            QLabel {
                color: #ff6b6b;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                background-color: rgba(255, 107, 107, 0.2);
                border-radius: 3px;
                min-width: 30px;
            }
        """)

        # Метка скорости воспроизведения
        self.speed_label = QLabel("1.0x")
        self.speed_label.setStyleSheet("""
            QLabel {
                color: #2196F3;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                background-color: rgba(33, 150, 243, 0.2);
                border-radius: 3px;
                min-width: 30px;
            }
        """)
        self.speed_label.setAlignment(Qt.AlignCenter)
        self.speed_label.setToolTip("Скорость воспроизведения (клик для сброса на 1.0x)")
        self.speed_label.mousePressEvent = self.on_speed_label_click

        # Метка информации о треках
        self.tracks_label = QLabel("A:1/1")
        self.tracks_label.setStyleSheet("""
            QLabel {
                color: #9C27B0;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                background-color: rgba(156, 39, 176, 0.2);
                border-radius: 3px;
                min-width: 35px;
            }
        """)
        self.tracks_label.setAlignment(Qt.AlignCenter)
        self.tracks_label.setToolTip("Аудио и субтитры (A - аудио, S - субтитры)")

        # Добавляем элементы в layout
        seek_layout.addWidget(self.current_time_label)
        seek_layout.addWidget(self.position_slider, 1)  # Растягиваем слайдер
        seek_layout.addWidget(self.duration_label)
        seek_layout.addWidget(self.stream_type_label)
        seek_layout.addWidget(self.speed_label)
        seek_layout.addWidget(self.tracks_label)

        # Таймер позиции теперь не нужен - обновление происходит через основной UI таймер
        # if self.position_timer.isActive():
        #     self.position_timer.stop()
        # self.position_timer.start()
        logging.info("Обновление позиции будет происходить через основной UI таймер")

        return seek_panel

    def on_speed_label_click(self, event):
        """Обработчик клика по метке скорости - сбрасывает на 1.0x"""
        logging.info("Клик по метке скорости - сброс на 1.0x")
        self.reset_playback_rate()
        self.update_speed_label()

    def on_seek_start(self):
        """Обработчик начала перемотки"""
        logging.info("Пользователь начал перетаскивание слайдера")
        self.updating_position = True
        self._slider_being_dragged = True
        
    def on_seek_end(self):
        """Обработчик окончания перетаскивания"""
        logging.info("Пользователь закончил перетаскивание слайдера")

        # Выполняем перемотку
        slider_value = self.position_slider.value()
        self.perform_seek(slider_value)

        # Сбрасываем флаги
        self.updating_position = False
        self._slider_being_dragged = False

    def force_position_update(self):
        """Принудительно обновляет позицию после перемотки"""
        if not self.vlc_player:
            return

        # Получаем актуальную информацию
        current_time_ms = self.vlc_player.get_time()
        current_duration_ms = self.vlc_player.get_length()
        position_vlc = self.vlc_player.get_position()

        logging.info(f"Принудительное обновление: time={current_time_ms}ms, duration={current_duration_ms}ms, position={position_vlc}")

        # Обновляем длительность если получили новую информацию
        if current_duration_ms > 0:
            current_duration = current_duration_ms / 1000
            if abs(current_duration - self.duration) > 1:
                self.duration = current_duration
                logging.info(f"Длительность обновлена в force_position_update: {self.duration} сек")
                # Обновляем метку длительности
                self.duration_label.setText(self.format_time(int(self.duration)))

        if current_time_ms >= 0:
            # Обновляем метку времени
            current_seconds = current_time_ms / 1000
            self.current_time_label.setText(self.format_time(int(current_seconds)))

            # Обновляем слайдер
            self.updating_position = True

            if position_vlc >= 0:
                # Используем позицию от VLC
                slider_value = int(position_vlc * 1000)
                self.position_slider.setValue(slider_value)
                logging.info(f"Слайдер обновлен по позиции VLC: {slider_value}/1000")
            elif current_duration_ms > 0:
                # Вычисляем позицию из времени
                position_calc = current_time_ms / current_duration_ms
                slider_value = int(position_calc * 1000)
                self.position_slider.setValue(slider_value)
                logging.info(f"Слайдер обновлен по времени: {slider_value}/1000")

            self.updating_position = False

    def on_position_changed(self, value):
        """Обработчик изменения позиции слайдера"""
        if self.updating_position:
            # Игнорируем изменения, которые мы сами вызвали
            return

        # Получаем актуальную длительность
        duration_ms = 0
        if self.vlc_player:
            duration_ms = self.vlc_player.get_length()

        duration_sec = duration_ms / 1000 if duration_ms > 0 else self.duration

        if duration_sec > 0:
            # Обновляем метку текущего времени при перетаскивании
            current_seconds = int((value / 1000.0) * duration_sec)
            self.current_time_label.setText(self.format_time(current_seconds))

            # Логируем для отладки
            position = value / 1000.0
            logging.debug(f"Слайдер перемещен пользователем: value={value}, position={position:.3f}, time={current_seconds}s")

    def on_value_changed(self, value):
        """Обработчик любых изменений значения слайдера (включая клики)"""
        if self.updating_position:
            # Игнорируем программные изменения
            return

        # Проверяем, был ли это клик по слайдеру (не перетаскивание)
        if not hasattr(self, '_slider_being_dragged'):
            self._slider_being_dragged = False

        if not self._slider_being_dragged:
            # Это клик по слайдеру - выполняем перемотку
            logging.info(f"Клик по слайдеру: value={value}")
            self.perform_seek(value)
        else:
            logging.debug(f"Перетаскивание слайдера: value={value}")

    def perform_seek(self, slider_value):
        """Выполняет перемотку на указанную позицию слайдера"""
        if not self.vlc_player:
            logging.error("VLC плеер не инициализирован")
            return

        target_position = slider_value / 1000.0
        logging.info(f"Выполняем перемотку на позицию {target_position:.3f} ({slider_value}/1000)")

        # Получаем длительность
        duration_ms = self.vlc_player.get_length()

        if duration_ms > 0:
            try:
                # Используем set_time как основной метод
                target_time_ms = int(target_position * duration_ms)

                logging.info(f"Перематываем на время: {target_time_ms} мс из {duration_ms} мс")

                result = self.vlc_player.set_time(target_time_ms)

                # В Python VLC, None означает успех
                if result is None:
                    logging.info("Перемотка по клику выполнена успешно")
                    # Даем VLC время обновить позицию
                    QTimer.singleShot(100, self.force_position_update)
                else:
                    logging.info("set_time не сработал, пробуем set_position")
                    result2 = self.vlc_player.set_position(target_position)
                    logging.info(f"set_position результат: {result2}")

            except Exception as e:
                logging.error(f"Ошибка при перемотке по клику: {e}")
        else:
            logging.warning("Клик по слайдеру: нет длительности, перемотка может не работать")
    
    def update_media_info(self):
        """Обновляет информацию о медиа (длительность, возможность перемотки)"""
        if not self.vlc_player:
            return

        # Получаем актуальную информацию
        duration_ms = self.vlc_player.get_length()
        is_seekable = self.vlc_player.is_seekable()
        state = self.vlc_player.get_state()
        current_time = self.vlc_player.get_time()

        # Логируем подробную информацию
        logging.info(f"Медиа проверка: state={state}, duration_ms={duration_ms}, seekable={is_seekable}, time={current_time}")

        # Сохраняем старые значения
        old_duration = self.duration

        # Обновляем длительность
        if duration_ms > 0:
            self.duration = duration_ms / 1000
            self.is_seekable = True  # Принудительно включаем для файлов с длительностью

            # Если длительность изменилась значительно, обновляем UI
            if abs(self.duration - old_duration) > 1:
                logging.info(f"Длительность обновлена: {old_duration} -> {self.duration} сек")
                self.update_seek_ui()

                # Таймер позиции не нужен - обновление через основной UI таймер
                # if not self.position_timer.isActive():
                #     self.position_timer.start()
                logging.info("Длительность получена, обновление позиции через основной UI таймер")
        else:
            # Длительность пока неизвестна
            if duration_ms == 0:
                logging.debug("Длительность пока 0 - ждем загрузки медиа")
            elif duration_ms == -1:
                logging.info("Длительность -1 - вероятно live поток")
                # Обновляем UI для live потока
                if old_duration > 0:  # Было значение, теперь нет
                    self.duration = 0
                    self.update_seek_ui()
    
    def update_seek_ui(self):
        """Обновляет UI элементы перемотки"""
        # Слайдер ВСЕГДА активен
        self.position_slider.setEnabled(True)

        # Определяем тип потока по URL
        stream_type = self.detect_stream_type_by_url()

        # ВСЕГДА обновляем метку длительности
        if self.duration > 0:
            duration_text = self.format_time(int(self.duration))
            self.duration_label.setText(duration_text)
            logging.info(f"Длительность отображена: {duration_text} ({self.duration} сек)")
        else:
            self.duration_label.setText("--:--")
            logging.info("Длительность неизвестна, показываем --:--")

        # Устанавливаем индикатор типа потока
        if stream_type == 'REC':
            self.stream_type_label.setText("REC")
            self.stream_type_label.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 2px 6px;
                    background-color: rgba(76, 175, 80, 0.2);
                    border-radius: 3px;
                    min-width: 30px;
                }
            """)
            logging.info(f"UI: REC (по URL) - длительность: {self.duration} сек")
        elif stream_type == 'LIVE':
            self.stream_type_label.setText("LIVE")
            self.stream_type_label.setStyleSheet("""
                QLabel {
                    color: #ff6b6b;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 2px 6px;
                    background-color: rgba(255, 107, 107, 0.2);
                    border-radius: 3px;
                    min-width: 30px;
                }
            """)
            logging.info(f"UI: LIVE (по URL) - длительность: {self.duration} сек")
        else:
            # Неизвестный тип - используем длительность как раньше
            if self.duration > 0:
                self.stream_type_label.setText("VOD")
                self.stream_type_label.setStyleSheet("""
                    QLabel {
                        color: #FFA500;
                        font-size: 10px;
                        font-weight: bold;
                        padding: 2px 6px;
                        background-color: rgba(255, 165, 0, 0.2);
                        border-radius: 3px;
                        min-width: 30px;
                    }
                """)
                logging.info(f"UI: VOD (по длительности) - длительность: {self.duration} сек")
            else:
                self.stream_type_label.setText("UNKNOWN")
                self.stream_type_label.setStyleSheet("""
                    QLabel {
                        color: #888888;
                        font-size: 10px;
                        font-weight: bold;
                        padding: 2px 6px;
                        background-color: rgba(136, 136, 136, 0.2);
                        border-radius: 3px;
                        min-width: 30px;
                    }
                """)
                logging.info("UI: UNKNOWN - нет информации о типе потока")
    
    def update_position(self):
        """Обновляет текущую позицию воспроизведения"""
        if not self.vlc_player:
            logging.debug("update_position: VLC плеер не инициализирован")
            return

        if self.updating_position:
            logging.debug("update_position: пропускаем, идет обновление позиции")
            return

        # Получаем актуальную информацию о медиа
        current_duration_ms = self.vlc_player.get_length()
        current_time_ms = self.vlc_player.get_time()
        position = self.vlc_player.get_position()
        state = self.vlc_player.get_state()

        # Отладочная информация каждые 5 секунд
        import time
        if not hasattr(self, '_last_debug_time'):
            self._last_debug_time = 0
        if time.time() - self._last_debug_time > 5:
            logging.info(f"update_position: state={state}, time={current_time_ms}ms, duration={current_duration_ms}ms, position={position}")
            self._last_debug_time = time.time()

        # Проверяем длительность
        if current_duration_ms > 0:
            current_duration = current_duration_ms / 1000

            # Если длительность изменилась или появилась впервые
            if abs(current_duration - self.duration) > 1:
                self.duration = current_duration
                logging.info(f"Длительность обновлена в update_position: {self.duration} сек")
                self.update_seek_ui()
            elif self.duration > 0:
                # Принудительно обновляем метку длительности каждые несколько секунд
                if not hasattr(self, '_last_duration_update'):
                    self._last_duration_update = 0
                if time.time() - self._last_duration_update > 5:  # каждые 5 секунд
                    duration_text = self.format_time(int(self.duration))
                    self.duration_label.setText(duration_text)
                    self._last_duration_update = time.time()
                    logging.debug(f"Принудительное обновление метки длительности: {duration_text}")

        # Обновляем позицию и время ВСЕГДА, даже если нет длительности
        if current_time_ms >= 0:
            # Обновляем метку времени
            current_seconds = current_time_ms / 1000
            time_text = self.format_time(int(current_seconds))
            self.current_time_label.setText(time_text)

            # Обновляем слайдер
            if current_duration_ms > 0:
                # Есть длительность - обновляем слайдер
                if position >= 0:
                    # Используем позицию от VLC
                    slider_value = int(position * 1000)
                    self.updating_position = True
                    self.position_slider.setValue(slider_value)
                    self.updating_position = False
                else:
                    # Вычисляем позицию из времени
                    position_calc = current_time_ms / current_duration_ms
                    slider_value = int(position_calc * 1000)
                    self.updating_position = True
                    self.position_slider.setValue(slider_value)
                    self.updating_position = False
            else:
                # Нет длительности - показываем время, но слайдер на 0
                if not hasattr(self, '_slider_reset_for_live'):
                    self.updating_position = True
                    self.position_slider.setValue(0)
                    self.updating_position = False
                    self._slider_reset_for_live = True
        else:
            # Время недоступно
            if not hasattr(self, '_time_unavailable_logged'):
                logging.debug("update_position: время недоступно")
                self._time_unavailable_logged = True
    
    def detect_stream_type_by_url(self):
        """Определяет тип потока по URL

        Returns:
            str: 'LIVE', 'REC', или 'UNKNOWN'
        """
        if not self.vlc_player:
            return 'UNKNOWN'

        try:
            media = self.vlc_player.get_media()
            if not media:
                return 'UNKNOWN'

            mrl = media.get_mrl()
            if not mrl:
                return 'UNKNOWN'

            mrl_lower = mrl.lower()
            logging.info(f"Анализ URL: {mrl}")

            # Live потоки
            if any(ext in mrl_lower for ext in ['.m3u8', '.m3u', '/live/', '/stream/', 'rtmp://', 'rtsp://']):
                return 'LIVE'

            # Записи/файлы
            elif any(ext in mrl_lower for ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.ts', '.vob']):
                return 'REC'

            # По умолчанию
            else:
                return 'UNKNOWN'

        except Exception as e:
            logging.error(f"Ошибка при анализе URL: {e}")
            return 'UNKNOWN'

    def format_time(self, seconds):
        """Форматирует время в формат MM:SS или HH:MM:SS

        Args:
            seconds (int): Время в секундах

        Returns:
            str: Отформатированное время
        """
        if seconds < 0:
            return "--:--"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def seek_forward(self, seconds=30):
        """Перемотка вперед на указанное количество секунд

        Args:
            seconds (int): Количество секунд для перемотки
        """
        logging.info(f"Попытка перемотки вперед: seekable={self.is_seekable}, duration={self.duration}")

        if self.vlc_player:
            current_time = self.vlc_player.get_time()
            duration_ms = self.vlc_player.get_length()

            logging.info(f"Текущее время: {current_time} мс, длительность: {duration_ms} мс")

            if current_time >= 0 and duration_ms > 0:
                new_time = min(current_time + (seconds * 1000), duration_ms - 1000)
                logging.info(f"Перематываем с {current_time} на {new_time}")
                result = self.vlc_player.set_time(new_time)
                if result is None:
                    logging.info(f"Перемотка вперед на {seconds} секунд выполнена успешно")
                    # Принудительно обновляем позицию слайдера
                    QTimer.singleShot(200, self.force_position_update)
                else:
                    logging.warning(f"Ошибка перемотки вперед: {result}")
            else:
                logging.warning("Не удалось получить текущее время или длительность для перемотки")
        else:
            logging.error("VLC плеер не инициализирован")

    def seek_backward(self, seconds=10):
        """Перемотка назад на указанное количество секунд

        Args:
            seconds (int): Количество секунд для перемотки
        """
        logging.info(f"Попытка перемотки назад: seekable={self.is_seekable}, duration={self.duration}")

        if self.vlc_player:
            current_time = self.vlc_player.get_time()

            logging.info(f"Текущее время: {current_time} мс")

            if current_time >= 0:
                new_time = max(0, current_time - (seconds * 1000))
                logging.info(f"Перематываем с {current_time} на {new_time}")
                result = self.vlc_player.set_time(new_time)
                if result is None:
                    logging.info(f"Перемотка назад на {seconds} секунд выполнена успешно")
                    # Принудительно обновляем позицию слайдера
                    QTimer.singleShot(200, self.force_position_update)
                else:
                    logging.warning(f"Ошибка перемотки назад: {result}")
            else:
                logging.warning("Не удалось получить текущее время для перемотки")
        else:
            logging.error("VLC плеер не инициализирован")

    def set_playback_rate(self, rate):
        """Устанавливает скорость воспроизведения

        Args:
            rate (float): Скорость воспроизведения (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)

        Returns:
            bool: True если скорость установлена успешно
        """
        if not self.vlc_player:
            logging.error("VLC плеер не инициализирован")
            return False

        try:
            result = self.vlc_player.set_rate(rate)
            if result == 0:  # 0 означает успех в VLC
                old_rate = self.playback_rate
                self.playback_rate = rate
                logging.info(f"Скорость воспроизведения изменена с {old_rate}x на {rate}x")
                self.update_speed_label()
                return True
            else:
                logging.warning(f"Не удалось установить скорость {rate}x, результат: {result}")
                return False
        except Exception as e:
            logging.error(f"Ошибка при установке скорости воспроизведения: {e}")
            return False

    def get_playback_rate(self):
        """Получает текущую скорость воспроизведения

        Returns:
            float: Текущая скорость воспроизведения
        """
        if self.vlc_player:
            try:
                vlc_rate = self.vlc_player.get_rate()
                # Обновляем наше значение
                self.playback_rate = vlc_rate
                return vlc_rate
            except Exception as e:
                logging.error(f"Ошибка при получении скорости воспроизведения: {e}")
                return self.playback_rate
        return self.playback_rate

    def reset_playback_rate(self):
        """Сбрасывает скорость воспроизведения на нормальную (1.0x)"""
        return self.set_playback_rate(1.0)

    def increase_playback_rate(self):
        """Увеличивает скорость воспроизведения на один шаг"""
        rates = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        current_rate = self.get_playback_rate()

        # Находим ближайшую большую скорость
        for rate in rates:
            if rate > current_rate + 0.01:  # Небольшая погрешность для сравнения float
                return self.set_playback_rate(rate)

        # Если уже максимальная, оставляем как есть
        logging.info("Уже максимальная скорость воспроизведения")
        return False

    def decrease_playback_rate(self):
        """Уменьшает скорость воспроизведения на один шаг"""
        rates = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        current_rate = self.get_playback_rate()

        # Находим ближайшую меньшую скорость
        for rate in reversed(rates):
            if rate < current_rate - 0.01:  # Небольшая погрешность для сравнения float
                return self.set_playback_rate(rate)

        # Если уже минимальная, оставляем как есть
        logging.info("Уже минимальная скорость воспроизведения")
        return False

    def update_speed_label(self):
        """Обновляет метку скорости воспроизведения"""
        current_rate = self.get_playback_rate()
        speed_text = f"{current_rate:.1f}x"
        self.speed_label.setText(speed_text)

        # Меняем цвет в зависимости от скорости
        if current_rate == 1.0:
            # Нормальная скорость - синий
            color = "#2196F3"
            bg_color = "rgba(33, 150, 243, 0.2)"
        elif current_rate < 1.0:
            # Медленная скорость - оранжевый
            color = "#FF9800"
            bg_color = "rgba(255, 152, 0, 0.2)"
        else:
            # Быстрая скорость - зеленый
            color = "#4CAF50"
            bg_color = "rgba(76, 175, 80, 0.2)"

        self.speed_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                background-color: {bg_color};
                border-radius: 3px;
                min-width: 30px;
            }}
        """)

        logging.debug(f"Метка скорости обновлена: {speed_text}")

    def update_tracks_label(self):
        """Обновляет метку информации о треках"""
        try:
            audio_info = self.get_audio_track_info()
            subtitle_info = self.get_subtitle_info()

            # Формируем текст для аудио
            audio_text = f"A:{audio_info['current_track_index']}/{audio_info['total_tracks']}"

            # Формируем текст для субтитров
            if subtitle_info['total_tracks'] > 0:
                if subtitle_info['enabled']:
                    # Находим индекс текущих субтитров
                    current_index = 0
                    tracks = self.get_subtitle_tracks()
                    for i, (track_id, _) in enumerate(tracks):
                        if track_id == subtitle_info['current_track_id']:
                            current_index = i + 1
                            break
                    subtitle_text = f"S:{current_index}/{subtitle_info['total_tracks']}"
                else:
                    subtitle_text = f"S:0/{subtitle_info['total_tracks']}"
            else:
                subtitle_text = "S:0/0"

            # Объединяем информацию
            tracks_text = f"{audio_text} {subtitle_text}"
            self.tracks_label.setText(tracks_text)

            # Меняем цвет в зависимости от наличия субтитров
            if subtitle_info['enabled']:
                # Субтитры включены - зеленый оттенок
                color = "#4CAF50"
                bg_color = "rgba(76, 175, 80, 0.2)"
            elif subtitle_info['total_tracks'] > 0:
                # Субтитры доступны но отключены - фиолетовый
                color = "#9C27B0"
                bg_color = "rgba(156, 39, 176, 0.2)"
            else:
                # Субтитры недоступны - серый
                color = "#757575"
                bg_color = "rgba(117, 117, 117, 0.2)"

            self.tracks_label.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    font-size: 10px;
                    font-weight: bold;
                    padding: 2px 6px;
                    background-color: {bg_color};
                    border-radius: 3px;
                    min-width: 35px;
                }}
            """)

            logging.debug(f"Метка треков обновлена: {tracks_text}")

        except Exception as e:
            logging.error(f"Ошибка при обновлении метки треков: {e}")
            self.tracks_label.setText("A:?/? S:?/?")

    def take_snapshot(self, filepath=None, channel_name=None):
        """Делает снимок текущего кадра

        Args:
            filepath (str, optional): Путь для сохранения снимка
            channel_name (str, optional): Имя канала для автоматического именования

        Returns:
            tuple: (success: bool, filepath: str, message: str)
        """
        if not self.vlc_player:
            return False, "", "VLC плеер не инициализирован"

        try:
            # Создаем папку для снимков если не указан путь
            if not filepath:
                import os
                from datetime import datetime

                # Создаем папку screenshots в директории приложения
                app_dir = os.path.dirname(os.path.abspath(__file__))
                screenshots_dir = os.path.join(app_dir, "screenshots")

                if not os.path.exists(screenshots_dir):
                    os.makedirs(screenshots_dir)
                    logging.info(f"Создана папка для снимков: {screenshots_dir}")

                # Формируем имя файла
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                if channel_name:
                    # Очищаем имя канала от недопустимых символов
                    clean_name = ''.join(c if c.isalnum() or c in ' -_[]()' else '_' for c in channel_name)
                    clean_name = clean_name.strip('_').replace('__', '_')[:50]  # Ограничиваем длину
                    filename = f"{clean_name}_{timestamp}.png"
                else:
                    filename = f"snapshot_{timestamp}.png"

                filepath = os.path.join(screenshots_dir, filename)

            # Получаем размеры видео для качественного снимка
            video_width = 0
            video_height = 0

            # Пытаемся получить размеры видео
            try:
                # Эти методы могут не работать во всех версиях VLC
                if hasattr(self.vlc_player, 'video_get_size'):
                    size = self.vlc_player.video_get_size()
                    if size and len(size) >= 2:
                        video_width, video_height = size[0], size[1]
            except:
                pass

            # Если не удалось получить размеры, используем стандартные
            if video_width <= 0 or video_height <= 0:
                video_width, video_height = 1920, 1080  # Full HD по умолчанию

            # Делаем снимок
            result = self.vlc_player.video_take_snapshot(0, filepath, video_width, video_height)

            if result == 0:  # 0 означает успех в VLC
                logging.info(f"Снимок экрана сохранен: {filepath}")
                return True, filepath, f"Снимок сохранен: {os.path.basename(filepath)}"
            else:
                logging.error(f"Ошибка при создании снимка, код: {result}")
                return False, "", f"Ошибка VLC при создании снимка (код: {result})"

        except Exception as e:
            logging.error(f"Ошибка при создании снимка экрана: {e}")
            return False, "", f"Ошибка: {str(e)}"

    def get_video_info(self):
        """Получает информацию о видео

        Returns:
            dict: Информация о видео (размеры, FPS, etc.)
        """
        if not self.vlc_player:
            return {}

        info = {
            'has_video': False,
            'width': 0,
            'height': 0,
            'fps': 0,
            'aspect_ratio': '16:9'
        }

        try:
            # Проверяем наличие видео
            info['has_video'] = self.vlc_player.has_vout() > 0

            if info['has_video']:
                # Пытаемся получить размеры видео
                try:
                    if hasattr(self.vlc_player, 'video_get_size'):
                        size = self.vlc_player.video_get_size()
                        if size and len(size) >= 2:
                            info['width'], info['height'] = size[0], size[1]

                            # Вычисляем соотношение сторон
                            if info['height'] > 0:
                                ratio = info['width'] / info['height']
                                if abs(ratio - 16/9) < 0.1:
                                    info['aspect_ratio'] = '16:9'
                                elif abs(ratio - 4/3) < 0.1:
                                    info['aspect_ratio'] = '4:3'
                                else:
                                    info['aspect_ratio'] = f"{info['width']}:{info['height']}"
                except:
                    pass

                # Пытаемся получить FPS
                try:
                    if hasattr(self.vlc_player, 'get_fps'):
                        fps = self.vlc_player.get_fps()
                        if fps > 0:
                            info['fps'] = round(fps, 2)
                except:
                    pass

        except Exception as e:
            logging.error(f"Ошибка при получении информации о видео: {e}")

        return info

    def get_audio_tracks(self):
        """Получает список доступных аудио треков

        Returns:
            list: Список кортежей (track_id, track_name)
        """
        if not self.vlc_player:
            return []

        try:
            # Получаем описания аудио треков
            track_descriptions = self.vlc_player.audio_get_track_description()
            tracks = []

            if track_descriptions:
                for track_id, track_name in track_descriptions:
                    # Декодируем имя трека если это bytes
                    if isinstance(track_name, bytes):
                        try:
                            track_name = track_name.decode('utf-8')
                        except:
                            track_name = track_name.decode('latin-1', errors='ignore')

                    tracks.append((track_id, track_name))

            logging.info(f"Найдено аудио треков: {len(tracks)}")
            for track_id, track_name in tracks:
                logging.debug(f"  Трек {track_id}: {track_name}")

            return tracks

        except Exception as e:
            logging.error(f"Ошибка при получении аудио треков: {e}")
            return []

    def get_current_audio_track(self):
        """Получает ID текущего аудио трека

        Returns:
            int: ID текущего трека или -1 если не определен
        """
        if not self.vlc_player:
            return -1

        try:
            current_track = self.vlc_player.audio_get_track()
            logging.debug(f"Текущий аудио трек: {current_track}")
            return current_track
        except Exception as e:
            logging.error(f"Ошибка при получении текущего аудио трека: {e}")
            return -1

    def set_audio_track(self, track_id):
        """Устанавливает аудио трек

        Args:
            track_id (int): ID трека для установки

        Returns:
            bool: True если трек установлен успешно
        """
        if not self.vlc_player:
            logging.error("VLC плеер не инициализирован")
            return False

        try:
            result = self.vlc_player.audio_set_track(track_id)
            if result == 0:  # 0 означает успех
                old_track = self.current_audio_track
                self.current_audio_track = track_id
                logging.info(f"Аудио трек изменен с {old_track} на {track_id}")
                return True
            else:
                logging.warning(f"Не удалось установить аудио трек {track_id}, результат: {result}")
                return False
        except Exception as e:
            logging.error(f"Ошибка при установке аудио трека: {e}")
            return False

    def next_audio_track(self):
        """Переключает на следующий аудио трек

        Returns:
            bool: True если переключение успешно
        """
        tracks = self.get_audio_tracks()
        if len(tracks) <= 1:
            logging.info("Недостаточно аудио треков для переключения")
            return False

        current_track = self.get_current_audio_track()

        # Находим индекс текущего трека
        current_index = -1
        for i, (track_id, _) in enumerate(tracks):
            if track_id == current_track:
                current_index = i
                break

        # Переключаемся на следующий трек
        next_index = (current_index + 1) % len(tracks)
        next_track_id, next_track_name = tracks[next_index]

        if self.set_audio_track(next_track_id):
            logging.info(f"Переключен на аудио трек: {next_track_name}")
            self.update_tracks_label()
            return True

        return False

    def get_audio_track_info(self):
        """Получает информацию о текущем аудио треке

        Returns:
            dict: Информация о треке
        """
        tracks = self.get_audio_tracks()
        current_track = self.get_current_audio_track()

        info = {
            'total_tracks': len(tracks),
            'current_track_id': current_track,
            'current_track_name': 'Неизвестно',
            'current_track_index': 0
        }

        # Находим информацию о текущем треке
        for i, (track_id, track_name) in enumerate(tracks):
            if track_id == current_track:
                info['current_track_name'] = track_name
                info['current_track_index'] = i + 1  # Человеко-читаемый индекс (с 1)
                break

        return info

    def get_subtitle_tracks(self):
        """Получает список доступных субтитров

        Returns:
            list: Список кортежей (track_id, track_name)
        """
        if not self.vlc_player:
            return []

        try:
            # Получаем описания субтитров
            subtitle_descriptions = self.vlc_player.video_get_spu_description()
            tracks = []

            if subtitle_descriptions:
                for track_id, track_name in subtitle_descriptions:
                    # Декодируем имя трека если это bytes
                    if isinstance(track_name, bytes):
                        try:
                            track_name = track_name.decode('utf-8')
                        except:
                            track_name = track_name.decode('latin-1', errors='ignore')

                    tracks.append((track_id, track_name))

            logging.info(f"Найдено субтитров: {len(tracks)}")
            for track_id, track_name in tracks:
                logging.debug(f"  Субтитры {track_id}: {track_name}")

            return tracks

        except Exception as e:
            logging.error(f"Ошибка при получении субтитров: {e}")
            return []

    def get_current_subtitle_track(self):
        """Получает ID текущих субтитров

        Returns:
            int: ID текущих субтитров или -1 если отключены
        """
        if not self.vlc_player:
            return -1

        try:
            current_track = self.vlc_player.video_get_spu()
            logging.debug(f"Текущие субтитры: {current_track}")
            return current_track
        except Exception as e:
            logging.error(f"Ошибка при получении текущих субтитров: {e}")
            return -1

    def set_subtitle_track(self, track_id):
        """Устанавливает субтитры

        Args:
            track_id (int): ID субтитров для установки (-1 для отключения)

        Returns:
            bool: True если субтитры установлены успешно
        """
        if not self.vlc_player:
            logging.error("VLC плеер не инициализирован")
            return False

        try:
            result = self.vlc_player.video_set_spu(track_id)
            if result == 0:  # 0 означает успех
                old_track = self.current_subtitle_track
                self.current_subtitle_track = track_id
                if track_id == -1:
                    logging.info("Субтитры отключены")
                else:
                    logging.info(f"Субтитры изменены с {old_track} на {track_id}")
                self.update_tracks_label()
                return True
            else:
                logging.warning(f"Не удалось установить субтитры {track_id}, результат: {result}")
                return False
        except Exception as e:
            logging.error(f"Ошибка при установке субтитров: {e}")
            return False

    def toggle_subtitles(self):
        """Переключает субтитры (включает/отключает или переключает между треками)

        Returns:
            bool: True если переключение успешно
        """
        tracks = self.get_subtitle_tracks()
        current_track = self.get_current_subtitle_track()

        if len(tracks) == 0:
            logging.info("Субтитры недоступны")
            return False

        if current_track == -1:
            # Субтитры отключены, включаем первый доступный трек
            first_track_id = tracks[0][0]
            if self.set_subtitle_track(first_track_id):
                logging.info(f"Включены субтитры: {tracks[0][1]}")
                return True
        else:
            # Субтитры включены, находим следующий трек или отключаем
            current_index = -1
            for i, (track_id, _) in enumerate(tracks):
                if track_id == current_track:
                    current_index = i
                    break

            if current_index == len(tracks) - 1:
                # Это последний трек, отключаем субтитры
                if self.set_subtitle_track(-1):
                    logging.info("Субтитры отключены")
                    return True
            else:
                # Переключаемся на следующий трек
                next_index = current_index + 1
                next_track_id, next_track_name = tracks[next_index]
                if self.set_subtitle_track(next_track_id):
                    logging.info(f"Переключены субтитры на: {next_track_name}")
                    return True

        return False

    def get_subtitle_info(self):
        """Получает информацию о текущих субтитрах

        Returns:
            dict: Информация о субтитрах
        """
        tracks = self.get_subtitle_tracks()
        current_track = self.get_current_subtitle_track()

        info = {
            'total_tracks': len(tracks),
            'current_track_id': current_track,
            'current_track_name': 'Отключены',
            'enabled': current_track != -1
        }

        # Находим информацию о текущих субтитрах
        if current_track != -1:
            for track_id, track_name in tracks:
                if track_id == current_track:
                    info['current_track_name'] = track_name
                    break

        return info

    def reset(self):
        """Сбрасывает состояние медиаплеера"""
        self.is_seekable = False
        self.duration = 0
        self.position = 0

        # Сбрасываем скорость воспроизведения на нормальную
        self.playback_rate = 1.0
        if self.vlc_player:
            try:
                self.vlc_player.set_rate(1.0)
                logging.debug("Скорость воспроизведения сброшена на 1.0x")
            except Exception as e:
                logging.debug(f"Ошибка при сбросе скорости: {e}")

        # Сбрасываем информацию о треках
        self.audio_tracks = []
        self.subtitle_tracks = []
        self.current_audio_track = -1
        self.current_subtitle_track = -1

        if self.position_timer.isActive():
            self.position_timer.stop()

        self.update_seek_ui()
        self.update_speed_label()
        self.update_tracks_label()
    
    def on_media_changed(self):
        """Обработчик смены медиа"""
        self.reset()
        # Обновление информации о медиа - много попыток для надежности
        QTimer.singleShot(500, self.update_media_info)    # 0.5 сек
        QTimer.singleShot(1000, self.update_media_info)   # 1 сек
        QTimer.singleShot(2000, self.update_media_info)   # 2 сек
        QTimer.singleShot(3000, self.update_media_info)   # 3 сек
        QTimer.singleShot(5000, self.update_media_info)   # 5 сек
        QTimer.singleShot(8000, self.update_media_info)   # 8 сек
        QTimer.singleShot(12000, self.update_media_info)  # 12 сек
        QTimer.singleShot(20000, self.update_media_info)  # 20 сек

    def on_playback_started(self):
        """Обработчик начала воспроизведения - правильное время для получения длительности"""
        logging.info("Воспроизведение началось, получаем длительность...")

        # Используем рекомендованный подход: sleep после play()
        QTimer.singleShot(1000, self.get_duration_after_play)   # 1 сек после play()
        QTimer.singleShot(1500, self.get_duration_after_play)   # 1.5 сек после play()
        QTimer.singleShot(2000, self.get_duration_after_play)   # 2 сек после play()
        QTimer.singleShot(3000, self.get_duration_after_play)   # 3 сек после play()

        # Получаем информацию о треках с задержкой
        QTimer.singleShot(2000, self.update_tracks_info)   # 2 сек после play()
        QTimer.singleShot(4000, self.update_tracks_info)   # 4 сек после play()

    def update_tracks_info(self):
        """Обновляет информацию о доступных треках"""
        if not self.vlc_player:
            return

        try:
            # Обновляем информацию об аудио треках
            self.audio_tracks = self.get_audio_tracks()
            self.current_audio_track = self.get_current_audio_track()

            # Обновляем информацию о субтитрах
            self.subtitle_tracks = self.get_subtitle_tracks()
            self.current_subtitle_track = self.get_current_subtitle_track()

            # Логируем информацию
            audio_info = self.get_audio_track_info()
            subtitle_info = self.get_subtitle_info()

            logging.info(f"Треки обновлены: аудио {audio_info['current_track_index']}/{audio_info['total_tracks']}, "
                        f"субтитры {'включены' if subtitle_info['enabled'] else 'отключены'} ({subtitle_info['total_tracks']} доступно)")

            # Обновляем метку треков в UI
            self.update_tracks_label()

        except Exception as e:
            logging.error(f"Ошибка при обновлении информации о треках: {e}")

    def get_duration_after_play(self):
        """Получает длительность после начала воспроизведения с задержкой"""
        if not self.vlc_player:
            return

        duration_ms = self.vlc_player.get_length()
        state = self.vlc_player.get_state()

        logging.info(f"Получение длительности после play(): state={state}, duration_ms={duration_ms}")

        if duration_ms > 0:
            old_duration = self.duration
            self.duration = duration_ms / 1000

            if abs(self.duration - old_duration) > 1:
                logging.info(f"Длительность получена после play(): {self.duration} сек")
                self.update_seek_ui()

                # Таймер позиции не нужен - обновление через основной UI таймер
                # if not self.position_timer.isActive():
                #     self.position_timer.start()
                logging.info("Длительность получена после play(), обновление через основной UI таймер")
        else:
            logging.debug(f"Длительность пока недоступна: {duration_ms}")

    def set_vlc_player(self, vlc_player):
        """Устанавливает VLC плеер и подключает события"""
        self.vlc_player = vlc_player
        self.setup_vlc_events()

        # Подключаем сигнал для безопасного обновления UI
        self.media_info_changed.connect(self.update_seek_ui)
