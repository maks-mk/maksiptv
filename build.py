import os
import sys
import shutil
import subprocess
from typing import List, Tuple

def install_requirements() -> None:
    """Устанавливает необходимые пакеты"""
    requirements = [
        'pyinstaller',
        'PyQt5',
        'python-vlc'
    ]
    
    print("Проверка и установка необходимых пакетов...")
    for package in requirements:
        try:
            __import__(package.replace('-', '_'))
            print(f"✓ {package} уже установлен")
        except ImportError:
            print(f"Установка {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def get_project_resources() -> List[str]:
    """Возвращает список ресурсов проекта"""
    return ['maksiptv.ico']

def check_requirements() -> Tuple[bool, str]:
    """Проверяет наличие необходимых зависимостей"""
    try:
        import PyQt5
        import vlc
        # Используем subprocess для проверки pyinstaller
        subprocess.run(['pyinstaller', '--version'], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE,
                      check=True)
        return True, ""
    except ImportError as e:
        return False, f"Отсутствует необходимый пакет: {str(e)}"
    except subprocess.CalledProcessError:
        return False, "PyInstaller не установлен или не доступен"
    except Exception as e:
        return False, f"Неизвестная ошибка: {str(e)}"

def cleanup_build_dirs() -> None:
    """Очищает директории сборки"""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Очищена директория: {dir_name}")

def build_exe() -> bool:
    """Выполняет сборку exe файла"""
    try:
        # Проверка зависимостей
        requirements_ok, error_msg = check_requirements()
        if not requirements_ok:
            print(f"Ошибка: {error_msg}")
            print("Попытка установить необходимые пакеты...")
            install_requirements()
            # Повторная проверка после установки
            requirements_ok, error_msg = check_requirements()
            if not requirements_ok:
                print(f"Ошибка после попытки установки: {error_msg}")
                return False

        # Очистка директорий сборки
        cleanup_build_dirs()

        # Запуск PyInstaller с указанными параметрами
        cmd = [
            'pyinstaller',
            '--noconfirm',
            '--add-data', 'maksiptv.ico;.',
           # '--add-data', 'config.py;.',
            #'--add-data', 'ffmpeg.exe;.',
            #'--add-data', 'ffprobe.exe;.',
            '--onefile',
            '--windowed',
            '--icon', 'maksiptv.ico',
            '--clean',
            '--name', 'MaksIPTV',
            'main.py'
        ]
        subprocess.run(cmd, check=True)

        # Проверка результата сборки
        exe_path = os.path.join('dist', 'MaksIPTV.exe')
        if os.path.exists(exe_path):
            print(f"\nСборка успешно завершена!")
            print(f"Исполняемый файл создан: {exe_path}")
            return True
        else:
            print("\nОшибка: Файл exe не найден после сборки")
            return False

    except subprocess.CalledProcessError as e:
        print(f"\nОшибка при выполнении команды PyInstaller: {e}")
        return False
    except Exception as e:
        print(f"\nНеожиданная ошибка при сборке: {e}")
        return False

def main() -> None:
    """Основная функция сборки"""
    print("Начало сборки MaksIPTV...")
    
    # Проверяем наличие обоих файлов - и .png для GUI, и .ico для иконки exe
    if not os.path.exists('maksiptv.ico'):
        print("Ошибка: Файл maksiptv.ico не найден!")
        sys.exit(1)
        
    if not os.path.exists('maksiptv.ico'):
        print("Ошибка: Файл maksiptv.ico не найден!")
        sys.exit(1)

    if build_exe():
        print("\nПроцесс сборки успешно завершен!")
    else:
        print("\nПроцесс сборки завершился с ошибками")
        sys.exit(1)

if __name__ == '__main__':
    main() 