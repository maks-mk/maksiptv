"""
Модуль платформенных утилит для MaksIPTV Player
Версия 0.13.0

Содержит PlatformManager для управления платформенно-зависимой логикой.
Обеспечивает унифицированный доступ к функциям, которые различаются
в зависимости от операционной системы (Windows, Linux, macOS).
"""

import sys


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
