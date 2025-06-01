#!/usr/bin/env python3
"""
Альтернативный скрипт для компиляции MaksIPTV Player в папку
Версия 0.13.0

Создает папочную сборку (быстрее запускается, но больше файлов).
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_folder():
    """Компилирует приложение в папку"""
    
    print("🚀 Начинаем компиляцию MaksIPTV Player (папочная сборка)...")
    
    # Основные параметры
    app_name = "MaksIPTV_Player"
    main_script = "main.py"
    icon_file = "maksiptv.ico"
    
    # Команда PyInstaller для папочной сборки
    cmd = [
        "pyinstaller",
        "--onedir",                     # Папочная сборка
        "--windowed",                   # Без консоли
        f"--name={app_name}",          # Имя папки
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
        
        # Показываем путь к папке
        app_folder = Path("dist") / app_name
        exe_path = app_folder / f"{app_name}.exe"
        
        if exe_path.exists():
            print(f"📁 Приложение создано в папке: {app_folder.absolute()}")
            print(f"🎯 Исполняемый файл: {exe_path.name}")
            
            # Подсчитываем размер папки
            total_size = sum(f.stat().st_size for f in app_folder.rglob('*') if f.is_file())
            print(f"📊 Общий размер: {total_size / 1024 / 1024:.1f} MB")
            
            # Подсчитываем количество файлов
            file_count = len([f for f in app_folder.rglob('*') if f.is_file()])
            print(f"📄 Количество файлов: {file_count}")
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
    files_to_remove = ["MaksIPTV_Player.spec"]
    
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"🗑️ Удален файл: {file_name}")

def main():
    """Основная функция"""
    
    print("=" * 50)
    print("🎬 MaksIPTV Player - Папочная сборка")
    print("=" * 50)
    
    # Проверяем наличие основных файлов
    required_files = ["main.py", "threads.py", "maksiptv.ico"]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Отсутствуют файлы: {', '.join(missing_files)}")
        return
    
    # Компилируем
    if build_folder():
        print("\n🎉 Сборка завершена успешно!")
        
        # Спрашиваем об очистке
        response = input("\n🧹 Очистить временные файлы? (y/n): ").lower().strip()
        if response in ['y', 'yes', 'да', 'д']:
            clean_build()
            print("✨ Очистка завершена!")
        
        print("\n📋 Готово! Приложение находится в папке 'dist/MaksIPTV_Player'")
        print("💡 Для запуска используйте MaksIPTV_Player.exe в этой папке")
    else:
        print("\n💥 Сборка завершилась с ошибками")

if __name__ == "__main__":
    main()
