#!/usr/bin/env python3
"""
Скрипт для диагностики проблем с конфигурацией
Версия 0.13.1

Проверяет:
1. Создание файла конфигурации
2. Загрузку конфигурации
3. Валидацию параметров
"""

import os
import json
import sys
import time
from threading import Lock

class ConfigManager:
    """Упрощенная версия ConfigManager для тестирования"""
    
    def __init__(self):
        self.config_file = "player_config.json"
        self.default_config = {
            "volume": 50,
            "last_channel": "",
            "last_category": "Все каналы",
            "favorites": [],
            "hidden_channels": [],
            "recent_playlists": ["local.m3u"],
            "playlist_names": {},
            "show_hidden": False,
            "show_logos": True,
            "window_size": [1000, 650],
            "window_position": [50, 40],
            "always_on_top": False
        }
        self.config = self.default_config.copy()
        self._config_lock = Lock()

    def load_config(self):
        """Загружает конфигурацию из файла с диагностикой"""
        print("🔄 Начинаем загрузку конфигурации...")
        
        with self._config_lock:
            try:
                print(f"📁 Проверяем существование файла: {self.config_file}")
                
                if os.path.exists(self.config_file):
                    print("✅ Файл конфигурации найден")
                    
                    print("📖 Читаем файл...")
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        loaded_config = json.load(f)
                    
                    print(f"📊 Загружено параметров: {len(loaded_config)}")
                    
                    # Обновляем конфигурацию
                    self.config.update(loaded_config)
                    print("✅ Конфигурация обновлена")
                    
                    # Валидируем
                    print("🔍 Валидируем конфигурацию...")
                    self._validate_and_fix_config()
                    print("✅ Валидация завершена")
                    
                else:
                    print("❌ Файл конфигурации не найден")
                    print("🆕 Создаем файл с настройками по умолчанию...")

                    # Создаем файл конфигурации без блокировки
                    self._save_config_internal()
                    print("✅ Файл конфигурации создан")

            except Exception as e:
                print(f"❌ Ошибка при загрузке конфигурации: {str(e)}")
                print("🔄 Используем значения по умолчанию")
                self.config = self.default_config.copy()

    def save_config(self):
        """Сохраняет конфигурацию в файл с диагностикой"""
        print("💾 Начинаем сохранение конфигурации...")

        with self._config_lock:
            self._save_config_internal()

    def _save_config_internal(self):
        """Внутренний метод сохранения без блокировки"""
        try:
            # Создаем резервную копию если файл существует
            if os.path.exists(self.config_file):
                print("📋 Создаем резервную копию...")
                backup_file = f"{self.config_file}.backup"
                with open(self.config_file, 'r', encoding='utf-8') as src:
                    with open(backup_file, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                print(f"✅ Резервная копия создана: {backup_file}")

            print("✍️ Записываем конфигурацию...")
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)

            print("✅ Конфигурация успешно сохранена")

            # Проверяем размер файла
            file_size = os.path.getsize(self.config_file)
            print(f"📏 Размер файла: {file_size} байт")

        except Exception as e:
            print(f"❌ Ошибка при сохранении конфигурации: {str(e)}")

    def _validate_and_fix_config(self):
        """Валидирует и исправляет конфигурацию с диагностикой"""
        print("🔍 Проверяем размер окна...")
        window_size = self.config.get('window_size', self.default_config['window_size'])
        if not isinstance(window_size, list) or len(window_size) != 2:
            print("⚠️ Некорректный размер окна, исправляем...")
            self.config['window_size'] = self.default_config['window_size']
        else:
            width, height = window_size
            if width < 800 or height < 600 or width > 3840 or height > 2160:
                print(f"⚠️ Размер окна вне пределов: {window_size}, исправляем...")
                self.config['window_size'] = self.default_config['window_size']
            else:
                print(f"✅ Размер окна корректный: {window_size}")

        print("🔍 Проверяем позицию окна...")
        window_position = self.config.get('window_position', self.default_config['window_position'])
        if not isinstance(window_position, list) or len(window_position) != 2:
            print("⚠️ Некорректная позиция окна, исправляем...")
            self.config['window_position'] = self.default_config['window_position']
        else:
            x, y = window_position
            if x < -100 or y < -100 or x > 5000 or y > 5000:
                print(f"⚠️ Позиция окна вне пределов: {window_position}, исправляем...")
                self.config['window_position'] = self.default_config['window_position']
            else:
                print(f"✅ Позиция окна корректная: {window_position}")

        print("🔍 Проверяем громкость...")
        volume = self.config.get('volume', self.default_config['volume'])
        if not isinstance(volume, (int, float)) or volume < 0 or volume > 100:
            print(f"⚠️ Некорректная громкость: {volume}, исправляем...")
            self.config['volume'] = self.default_config['volume']
        else:
            print(f"✅ Громкость корректная: {volume}")

def test_config_creation():
    """Тестирует создание конфигурации"""
    print("=" * 60)
    print("🧪 ТЕСТ: Создание конфигурации")
    print("=" * 60)
    
    # Удаляем файл если существует
    config_file = "player_config.json"
    if os.path.exists(config_file):
        print(f"🗑️ Удаляем существующий файл: {config_file}")
        os.remove(config_file)
    
    # Создаем менеджер конфигурации
    print("🏗️ Создаем ConfigManager...")
    config_manager = ConfigManager()
    
    # Загружаем конфигурацию (должна создаться)
    print("📥 Загружаем конфигурацию...")
    start_time = time.time()
    
    config_manager.load_config()
    
    end_time = time.time()
    print(f"⏱️ Время загрузки: {end_time - start_time:.3f} секунд")
    
    # Проверяем результат
    if os.path.exists(config_file):
        print("✅ Файл конфигурации создан успешно")
        
        # Читаем и проверяем содержимое
        with open(config_file, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        print(f"📊 Параметров в файле: {len(content)}")
        print(f"📍 Позиция окна: {content.get('window_position')}")
        print(f"📏 Размер окна: {content.get('window_size')}")
        print(f"🔊 Громкость: {content.get('volume')}")
        
        return True
    else:
        print("❌ Файл конфигурации НЕ создан!")
        return False

def test_config_loading():
    """Тестирует загрузку существующей конфигурации"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ: Загрузка существующей конфигурации")
    print("=" * 60)
    
    config_manager = ConfigManager()
    
    print("📥 Загружаем существующую конфигурацию...")
    start_time = time.time()
    
    config_manager.load_config()
    
    end_time = time.time()
    print(f"⏱️ Время загрузки: {end_time - start_time:.3f} секунд")
    
    print("✅ Загрузка завершена")
    return True

def test_config_corruption():
    """Тестирует обработку поврежденной конфигурации"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ: Обработка поврежденной конфигурации")
    print("=" * 60)
    
    config_file = "player_config.json"
    
    # Создаем поврежденный файл
    print("💥 Создаем поврежденный файл конфигурации...")
    with open(config_file, 'w') as f:
        f.write("{ invalid json content")
    
    config_manager = ConfigManager()
    
    print("📥 Пытаемся загрузить поврежденную конфигурацию...")
    start_time = time.time()
    
    config_manager.load_config()
    
    end_time = time.time()
    print(f"⏱️ Время обработки: {end_time - start_time:.3f} секунд")
    
    # Проверяем, что файл восстановлен
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
            print("✅ Конфигурация восстановлена после повреждения")
            return True
        except:
            print("❌ Файл все еще поврежден")
            return False
    else:
        print("❌ Файл конфигурации не создан")
        return False

def main():
    """Главная функция тестирования"""
    print("🔧 Диагностика конфигурации MaksIPTV Player")
    print("Версия 0.13.1")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 3
    
    try:
        # Тест 1: Создание конфигурации
        if test_config_creation():
            tests_passed += 1
        
        # Тест 2: Загрузка существующей конфигурации
        if test_config_loading():
            tests_passed += 1
        
        # Тест 3: Обработка поврежденной конфигурации
        if test_config_corruption():
            tests_passed += 1
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    
    # Результаты
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    print(f"✅ Пройдено тестов: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("💡 Конфигурация работает корректно")
    else:
        print("⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ!")
        print("💡 Возможны проблемы с конфигурацией")
    
    print("\n🔍 Для запуска основного приложения используйте: python main.py")

if __name__ == "__main__":
    main()
