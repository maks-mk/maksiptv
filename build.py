#!/usr/bin/env python3
"""
Простой скрипт для компиляции MaksIPTV Player в exe
Версия 0.13.0

Использует PyInstaller для создания исполняемого файла.
Предполагается, что все зависимости уже установлены.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_exe():
    """Компилирует приложение в exe файл"""
    
    print("🚀 Начинаем компиляцию MaksIPTV Player...")
    
    # Основные параметры
    app_name = "MaksIPTV_Player"
    main_script = "main.py"
    icon_file = "maksiptv.ico"
    
    # Команда PyInstaller
    cmd = [
        "pyinstaller",
        "--onefile",                    # Один exe файл
        "--windowed",                   # Без консоли
        f"--name={app_name}",          # Имя exe файла
        f"--icon={icon_file}",         # Иконка
        "--add-data=threads.py;.",     # Добавляем модуль потоков
        "--add-data=local.m3u;.",      # Добавляем плейлист
        "--hidden-import=vlc",         # VLC модуль
        "--hidden-import=qtawesome",   # QtAwesome иконки
        "--hidden-import=requests",    # Requests для загрузки
        "--hidden-import=PIL",         # PIL для обработки изображений
        "--clean",                     # Очистка перед сборкой
        main_script
    ]
    
    print(f"📦 Выполняем команду: {' '.join(cmd)}")
    
    try:
        # Запускаем PyInstaller
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Компиляция завершена успешно!")
        
        # Показываем путь к exe файлу
        exe_path = Path("dist") / f"{app_name}.exe"
        if exe_path.exists():
            print(f"📁 Исполняемый файл создан: {exe_path.absolute()}")
            print(f"📊 Размер файла: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
        else:
            print("⚠️ Exe файл не найден в папке dist")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка компиляции:")
        print(f"Код ошибки: {e.returncode}")
        print(f"Вывод: {e.stdout}")
        print(f"Ошибки: {e.stderr}")
        return False
    
    except FileNotFoundError:
        print("❌ PyInstaller не найден!")
        print("Установите его командой: pip install pyinstaller")
        return False
    
    return True

def clean_build():
    """Очищает временные файлы сборки"""
    
    print("🧹 Очистка временных файлов...")
    
    # Папки для удаления
    dirs_to_remove = ["build", "__pycache__"]
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"🗑️ Удалена папка: {dir_name}")
    
    # Файлы для удаления
    files_to_remove = [f"{app_name}.spec" for app_name in ["MaksIPTV_Player"]]
    
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"🗑️ Удален файл: {file_name}")

def main():
    """Основная функция"""
    
    print("=" * 50)
    print("🎬 MaksIPTV Player - Сборка в exe")
    print("=" * 50)
    
    # Проверяем наличие основных файлов
    required_files = ["main.py", "threads.py", "maksiptv.ico"]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Отсутствуют файлы: {', '.join(missing_files)}")
        return
    
    # Компилируем
    if build_exe():
        print("\n🎉 Сборка завершена успешно!")
        
        # Спрашиваем об очистке
        response = input("\n🧹 Очистить временные файлы? (y/n): ").lower().strip()
        if response in ['y', 'yes', 'да', 'д']:
            clean_build()
            print("✨ Очистка завершена!")
        
        print("\n📋 Готово! Exe файл находится в папке 'dist'")
    else:
        print("\n💥 Сборка завершилась с ошибками")

if __name__ == "__main__":
    main()
