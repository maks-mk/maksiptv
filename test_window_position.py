#!/usr/bin/env python3
"""
Утилита для тестирования позиции окна MaksIPTV Player
Версия 0.13.1

Позволяет:
1. Проверить текущую позицию окна из конфигурации
2. Удалить конфигурацию для тестирования значений по умолчанию
3. Установить кастомную позицию
"""

import os
import json
import sys

def load_config():
    """Загружает конфигурацию из файла"""
    config_file = "player_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Ошибка чтения конфигурации: {e}")
            return None
    else:
        print("📄 Файл конфигурации не найден")
        return None

def save_config(config):
    """Сохраняет конфигурацию в файл"""
    config_file = "player_config.json"
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        print(f"✅ Конфигурация сохранена в {config_file}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def show_current_position():
    """Показывает текущую позицию окна"""
    config = load_config()
    if config:
        position = config.get('window_position', [50, 40])
        size = config.get('window_size', [1280, 720])
        print(f"📍 Текущая позиция окна: {position}")
        print(f"📏 Текущий размер окна: {size}")
    else:
        print("📍 Позиция по умолчанию: [50, 40]")
        print("📏 Размер по умолчанию: [1280, 720]")

def delete_config():
    """Удаляет файл конфигурации"""
    config_file = "player_config.json"
    if os.path.exists(config_file):
        try:
            # Создаем резервную копию
            backup_file = f"{config_file}.backup"
            with open(config_file, 'r') as src:
                with open(backup_file, 'w') as dst:
                    dst.write(src.read())
            
            os.remove(config_file)
            print(f"🗑️ Конфигурация удалена (резервная копия: {backup_file})")
            print("🔄 При следующем запуске будут использованы значения по умолчанию:")
            print("   Позиция: [50, 40]")
            print("   Размер: [1280, 720]")
        except Exception as e:
            print(f"❌ Ошибка удаления: {e}")
    else:
        print("📄 Файл конфигурации не найден")

def set_custom_position():
    """Устанавливает кастомную позицию окна"""
    try:
        print("📍 Введите новую позицию окна:")
        x = int(input("X координата: "))
        y = int(input("Y координата: "))
        
        # Проверяем разумные пределы
        if x < -100 or y < -100 or x > 5000 or y > 5000:
            print("⚠️ Предупреждение: координаты выходят за разумные пределы")
            confirm = input("Продолжить? (y/n): ").lower()
            if confirm != 'y':
                print("❌ Отменено")
                return
        
        config = load_config() or {}
        config['window_position'] = [x, y]
        
        if save_config(config):
            print(f"✅ Позиция окна установлена: [{x}, {y}]")
        
    except ValueError:
        print("❌ Ошибка: введите числовые значения")
    except KeyboardInterrupt:
        print("\n❌ Отменено пользователем")

def restore_backup():
    """Восстанавливает конфигурацию из резервной копии"""
    backup_file = "player_config.json.backup"
    config_file = "player_config.json"
    
    if os.path.exists(backup_file):
        try:
            with open(backup_file, 'r') as src:
                with open(config_file, 'w') as dst:
                    dst.write(src.read())
            print(f"✅ Конфигурация восстановлена из {backup_file}")
            show_current_position()
        except Exception as e:
            print(f"❌ Ошибка восстановления: {e}")
    else:
        print("📄 Резервная копия не найдена")

def main():
    """Главная функция"""
    print("=" * 50)
    print("🪟 Тестирование позиции окна MaksIPTV Player")
    print("=" * 50)
    
    while True:
        print("\nВыберите действие:")
        print("1. 📍 Показать текущую позицию")
        print("2. 🗑️ Удалить конфигурацию (тест значений по умолчанию)")
        print("3. ⚙️ Установить кастомную позицию")
        print("4. 🔄 Восстановить из резервной копии")
        print("5. 🚀 Запустить приложение")
        print("0. ❌ Выход")
        
        try:
            choice = input("\nВаш выбор: ").strip()
            
            if choice == '1':
                show_current_position()
            elif choice == '2':
                delete_config()
            elif choice == '3':
                set_custom_position()
            elif choice == '4':
                restore_backup()
            elif choice == '5':
                print("🚀 Запуск MaksIPTV Player...")
                os.system("python main.py")
            elif choice == '0':
                print("👋 До свидания!")
                break
            else:
                print("❌ Неверный выбор")
                
        except KeyboardInterrupt:
            print("\n👋 До свидания!")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()
