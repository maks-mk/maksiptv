import subprocess
import sys
import os
import shutil
import platform
import datetime
import tempfile

# Проверяем наличие colorama или добавляем поддержку цветов для Windows
try:
    from colorama import init, Fore, Style
    COLORAMA_AVAILABLE = True
    # Инициализируем colorama для поддержки ANSI цветов в Windows
    init(convert=True, strip=False)
except ImportError:
    COLORAMA_AVAILABLE = False
    # Создаем заглушки для совместимости
    class Fore:
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        MAGENTA = ""
        CYAN = ""
        WHITE = ""
        LIGHTBLACK_EX = ""
        RESET = ""

    class Style:
        RESET_ALL = ""

APP_NAME = "MaksIPTV"
APP_VERSION = "1.3.0"  # Версия после рефакторинга
ENTRY_POINT = "main.py"  # Точка входа остается прежней
ICON_PATH = "maksiptv.ico"  # Путь к иконке

HIDDEN_IMPORTS = [
    # Новые модули после рефакторинга
    "config",           # Управление конфигурацией
    "constants",        # Константы и стили
    "platform_utils",   # Платформенные утилиты
    "playlist",         # Управление плейлистами
    "ui_components",    # UI компоненты
    "media_player",     # Медиаплеер с поддержкой перемотки
    "threads",          # Управление потоками
    # Дополнительные зависимости
    "vlc",
    "qtawesome",
    "PIL",              # Для обработки изображений логотипов
    "requests",         # Для загрузки данных
    "urllib3"
]
EXTRA_DATA = ["maksiptv.ico", "README.md", "REFACTORING_REPORT.md"]  # Добавлен отчет о рефакторинге
CLEANUP_DIRS = ["build", "__pycache__"]
CLEANUP_FILES_EXT = [".spec", ".log"]

# Настройки установщика
INSTALLER_COMPANY = "MaksIPTV Team"
INSTALLER_DESCRIPTION = "IPTV плеер с модульной архитектурой, улучшенной производительностью и современным интерфейсом"
INSTALLER_FILENAME = f"{APP_NAME}_Setup_{APP_VERSION}"
INSTALLER_COPYRIGHT = f"© {datetime.datetime.now().year} {INSTALLER_COMPANY}"

# Цветовые константы для более понятного использования
COLOR_INFO = "96"      # Голубой - информация
COLOR_SUCCESS = "92"   # Зеленый - успешное действие
COLOR_WARNING = "93"   # Желтый - предупреждение
COLOR_ERROR = "91"     # Красный - ошибка
COLOR_COMMAND = "90"   # Серый - команды
COLOR_PROMPT = "95"    # Пурпурный - ввод пользователя

def color(text, code):
    """
    Добавляет цветовое форматирование к выводу в консоль
    Учитывает наличие colorama и возможности терминала
    """
    # Если colorama доступна, используем её
    if COLORAMA_AVAILABLE:
        color_map = {
            "90": Fore.LIGHTBLACK_EX,
            "91": Fore.RED,
            "92": Fore.GREEN, 
            "93": Fore.YELLOW,
            "94": Fore.BLUE,
            "95": Fore.MAGENTA,
            "96": Fore.CYAN,
            "97": Fore.WHITE
        }
        
        return f"{color_map.get(code, Fore.RESET)}{text}{Style.RESET_ALL}"
    elif supports_ansi_colors():
        # Используем ANSI-коды, если терминал их поддерживает
        return f"\033[{code}m{text}\033[0m"
    else:
        # Если нет поддержки цветов, возвращаем текст без форматирования
        return text

def install_colorama():
    """Устанавливает библиотеку colorama для поддержки цветов в консоли Windows"""
    print("Для цветного отображения рекомендуется установить colorama")
    try_install = input("Установить colorama? (y/n): ")
    if try_install.lower() == 'y':
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "colorama"], check=True)
            print("colorama успешно установлена. Перезапустите скрипт для цветного отображения.")
            return True
        except Exception as e:
            print(f"Ошибка при установке colorama: {e}")
            return False
    return False

def build():
    """Собирает приложение с помощью PyInstaller"""
    print(color(f"[+] Сборка {APP_NAME}.exe (версия {APP_VERSION})...", COLOR_INFO))

    command = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        f"--name={APP_NAME}",
    ]

    if os.path.exists(ICON_PATH):
        command.append(f"--icon={ICON_PATH}")
    else:
        print(color("[!] Иконка не найдена, сборка без иконки", COLOR_WARNING))

    for mod in HIDDEN_IMPORTS:
        command.append(f"--hidden-import={mod}")
    
    # Добавляем дополнительные файлы данных
    for data_file in EXTRA_DATA:
        if os.path.exists(data_file):
            command.append(f"--add-data={data_file};.")

    command.append(ENTRY_POINT)

    print(color("> Команда:", COLOR_COMMAND), " ".join(command))
    result = subprocess.run(command)

    if result.returncode == 0:
        print(color(f"\n[+] Сборка завершена. → dist/{APP_NAME}.exe", COLOR_SUCCESS))
        return True
    else:
        print(color("\n[-] Сборка не удалась.", COLOR_ERROR))
        return False

def create_installer():
    """Создает установщик для Windows с помощью Inno Setup"""
    dist_dir = os.path.abspath("dist")
    exe_path = os.path.join(dist_dir, f"{APP_NAME}.exe")
    
    if not os.path.exists(exe_path):
        print(color(f"\n[-] Невозможно создать установщик: исполняемый файл не найден по пути {exe_path}", COLOR_ERROR))
        return False

    # Проверяем наличие iscc (Inno Setup Compiler)
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe"
    ]
    
    iscc_path = next((path for path in iscc_paths if os.path.exists(path)), None)
    if not iscc_path:
        print(color("\n[!] Inno Setup не найден. Установщик не будет создан.", COLOR_WARNING))
        print(color("   Загрузите Inno Setup с https://jrsoftware.org/isdl.php", COLOR_WARNING))
        return False

    print(color("\n[+] Создание установщика для Windows...", COLOR_INFO))

    if not os.path.exists(dist_dir):
        os.makedirs(dist_dir)

    icon_path = os.path.abspath(ICON_PATH) if os.path.exists(ICON_PATH) else ""

    # Генерация Inno Setup-скрипта без использования f-строки,
    # чтобы избежать проблем с интерпретацией фигурных скобок
    iss_script = """
[Setup]
AppName=""" + APP_NAME + """
AppVersion=""" + APP_VERSION + """
AppPublisher=""" + INSTALLER_COMPANY + """
AppPublisherURL=https://github.com/maksimKorzh/iptvplayer
AppSupportURL=https://github.com/maksimKorzh/iptvplayer/issues
AppComments=""" + INSTALLER_DESCRIPTION + """
DefaultDirName={localappdata}\\""" + APP_NAME + """
DefaultGroupName=""" + APP_NAME + """
UninstallDisplayIcon={app}\\""" + APP_NAME + """.exe
Compression=lzma2
SolidCompression=yes
OutputDir=""" + dist_dir + """
OutputBaseFilename=""" + INSTALLER_FILENAME + """
SetupIconFile=""" + icon_path + """
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
UsePreviousAppDir=yes
DisableDirPage=auto
DisableProgramGroupPage=auto
CreateAppDir=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать значок на рабочем столе"; GroupDescription: "Дополнительные значки:"; Flags: unchecked

[Dirs]
Name: "{app}"; Permissions: users-full
Name: "{app}\\cache"; Permissions: users-full
Name: "{userappdata}\\MaksIPTV"; Permissions: users-full

[Files]
Source: \"""" + exe_path + """"; DestDir: "{app}"; Flags: ignoreversion
"""

    for data_file in EXTRA_DATA:
        if os.path.exists(data_file):
            data_path = os.path.abspath(data_file)
            iss_script += 'Source: "' + data_path + '"; DestDir: "{app}"; Flags: ignoreversion\n'

    iss_script += """
[Icons]
Name: "{group}\\""" + APP_NAME + """"; Filename: "{app}\\""" + APP_NAME + """.exe"; IconFilename: "{app}\\""" + APP_NAME + """.exe"; Comment: "IPTV плеер с модульной архитектурой";
Name: "{group}\\Удалить """ + APP_NAME + """"; Filename: "{uninstallexe}"; IconFilename: "{uninstallexe}"; Comment: "Удалить """ + APP_NAME + """";
Name: "{userdesktop}\\""" + APP_NAME + """"; Filename: "{app}\\""" + APP_NAME + """.exe"; IconFilename: "{app}\\""" + APP_NAME + """.exe"; Tasks: desktopicon; Comment: "IPTV плеер с модульной архитектурой";

[Run]
Filename: "{app}\\""" + APP_NAME + """.exe"; Description: "Запустить """ + APP_NAME + """ (IPTV плеер)"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}";

[Code]
var
  InstallVLC: Boolean;

function VLCInstalled: String;
begin
  if FileExists(ExpandConstant('{pf}\\VideoLAN\\VLC\\vlc.exe')) then
    Result := 'yes'
  else if FileExists(ExpandConstant('{pf32}\\VideoLAN\\VLC\\vlc.exe')) then
    Result := 'yes'
  else if FileExists(ExpandConstant('{pf64}\\VideoLAN\\VLC\\vlc.exe')) then
    Result := 'yes'
  else
    Result := 'no';
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  
  if VLCInstalled = 'no' then
    InstallVLC := (MsgBox('VLC плеер не обнаружен. Он необходим для работы """ + APP_NAME + """. Установить VLC?', 
                     mbConfirmation, MB_YESNO) = IDYES)
  else
    InstallVLC := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  VLCUrl: String;
begin
  if (CurStep = ssPostInstall) and InstallVLC then
  begin    
    if IsWin64 then
      VLCUrl := 'https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.exe'
    else
      VLCUrl := 'https://get.videolan.org/vlc/3.0.21/win32/vlc-3.0.21-win32.exe';
    
    ShellExec('open', VLCUrl, '', '', SW_SHOWNORMAL, ewNoWait, ResultCode);
  end;
end;
"""

    # Запись скрипта во временный файл
    with tempfile.NamedTemporaryFile(suffix=".iss", delete=False) as temp_file:
        temp_filename = temp_file.name
        temp_file.write(iss_script.encode('utf-8'))

    try:
        cmd = f'"{iscc_path}" "{temp_filename}"'
        print(color("> Команда:", COLOR_COMMAND), cmd)
        result = subprocess.run(cmd, shell=True)
        
        if result.returncode == 0:
            print(color(f"\n[+] Установщик создан: dist/{INSTALLER_FILENAME}.exe", COLOR_SUCCESS))
            return True
        else:
            print(color("\n[-] Не удалось создать установщик", COLOR_ERROR))
            return False
    finally:
        try:
            os.unlink(temp_filename)
        except:
            pass

def cleanup():
    """Очищает временные файлы после сборки"""
    print(color("\n[*] Очистка временных файлов...", COLOR_INFO))

    for d in CLEANUP_DIRS:
        if os.path.isdir(d):
            try:
                shutil.rmtree(d, ignore_errors=True)
                print(color(f"  - Удалено: {d}/", COLOR_INFO))
            except Exception as e:
                print(color(f"  - Ошибка при удалении {d}: {e}", COLOR_ERROR))

    for f in os.listdir("."):
        if any(f.endswith(ext) for ext in CLEANUP_FILES_EXT):
            try:
                os.remove(f)
                print(color(f"  - Удалено: {f}", COLOR_INFO))
            except Exception as e:
                print(color(f"  - Ошибка при удалении {f}: {e}", COLOR_ERROR))

    print(color("[+] Очистка завершена.", COLOR_SUCCESS))

def show_menu():
    """Отображает меню с опциями сборки"""
    print(color(f"\n=== MaksIPTV Builder v{APP_VERSION} (Refactored) ===", COLOR_INFO))
    print(color("Модульная архитектура с улучшенной производительностью", COLOR_INFO))
    print(color("=" * 55, COLOR_INFO))
    print(color("1) Собрать приложение", COLOR_INFO))
    print(color("2) Создать установщик", COLOR_INFO))
    print(color("3) Собрать приложение и создать установщик", COLOR_INFO))
    print(color("4) Очистить временные файлы", COLOR_INFO))
    print(color("5) Показать информацию о модулях", COLOR_INFO))
    print(color("0) Выход", COLOR_INFO))

    choice = input(color("\nВыберите действие (0-5): ", COLOR_INFO))
    return choice

def show_module_info():
    """Показывает информацию о модулях после рефакторинга"""
    print(color("\n=== Информация о модулях MaksIPTV ===", COLOR_INFO))

    modules_info = {
        "main.py": "Основной класс приложения и точка входа",
        "config.py": "Управление конфигурацией (ConfigManager)",
        "constants.py": "Константы, стили CSS и настройки по умолчанию",
        "platform_utils.py": "Платформенно-зависимая логика (Windows/Linux/macOS)",
        "playlist.py": "Парсинг и управление плейлистами M3U",
        "ui_components.py": "Переиспользуемые UI компоненты и фабрики",
        "media_player.py": "Медиаплеер с поддержкой перемотки и временных меток",
        "threads.py": "Управление потоками и асинхронными операциями"
    }

    print(color("\nМодули проекта:", COLOR_SUCCESS))
    for module, description in modules_info.items():
        status = "✓" if os.path.exists(module) else "✗"
        color_code = COLOR_SUCCESS if os.path.exists(module) else COLOR_ERROR
        print(color(f"  {status} {module:<20} - {description}", color_code))

    print(color("\nПреимущества рефакторинга:", COLOR_INFO))
    benefits = [
        "Уменьшение размера main.py на ~21% (с 4776 до ~3763 строк)",
        "Соблюдение принципов SOLID (SRP, OCP, LSP, ISP, DIP)",
        "Применение принципов DRY, KISS, YAGNI",
        "Улучшенная читаемость и поддерживаемость кода",
        "Модульная архитектура для легкого тестирования",
        "Централизованное управление стилями и константами"
    ]

    for benefit in benefits:
        print(color(f"  • {benefit}", COLOR_SUCCESS))

    print(color(f"\nВсего строк кода распределено по {len(modules_info)} модулям", COLOR_INFO))

def check_tools():
    """Проверяет наличие необходимых инструментов и файлов"""
    print(color("\n[?] Проверка необходимых инструментов...", COLOR_INFO))

    # Проверяем основные файлы проекта после рефакторинга
    required_files = [
        "main.py",          # Основной файл приложения
        "config.py",        # Управление конфигурацией
        "constants.py",     # Константы и стили
        "platform_utils.py", # Платформенные утилиты
        "playlist.py",      # Управление плейлистами
        "ui_components.py", # UI компоненты
        "media_player.py",  # Медиаплеер с поддержкой перемотки
        "threads.py"        # Управление потоками
    ]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print(color(f"  - Отсутствуют основные файлы: {', '.join(missing_files)}", COLOR_ERROR))
        return False
    else:
        print(color("  + Все основные файлы проекта найдены", COLOR_SUCCESS))

    # Проверяем PyInstaller
    try:
        subprocess.run(["pyinstaller", "--version"], capture_output=True)
        print(color("  + PyInstaller установлен", COLOR_SUCCESS))
    except FileNotFoundError:
        print(color("  - PyInstaller не найден", COLOR_ERROR))
        install = input(color("  Установить PyInstaller? (y/n): ", COLOR_INFO))
        if install.lower() == 'y':
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
                print(color("  + PyInstaller успешно установлен", COLOR_SUCCESS))
            except Exception as e:
                print(color(f"  - Ошибка установки PyInstaller: {e}", COLOR_ERROR))
                return False
    
    # Проверка наличия VLC
    vlc_paths = [
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC"
    ]
    
    vlc_installed = any(os.path.exists(path) for path in vlc_paths)
    if vlc_installed:
        print(color("  + VLC Player установлен", COLOR_SUCCESS))
    else:
        print(color("  - VLC Player не найден", COLOR_ERROR))
        print(color("    Для работы IPTV плеера необходим VLC Player", COLOR_INFO))
        print(color("    Скачайте с https://www.videolan.org/", COLOR_INFO))
    
    # Проверка наличия Inno Setup
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe"
    ]
    
    iscc_installed = any(os.path.exists(path) for path in iscc_paths)
    if iscc_installed:
        print(color("  + Inno Setup установлен", COLOR_SUCCESS))
    else:
        print(color("  - Inno Setup не найден", COLOR_ERROR))
        print(color("    Для создания установщика требуется Inno Setup", COLOR_INFO))
        print(color("    Скачайте с https://jrsoftware.org/isdl.php", COLOR_INFO))
    
    # Проверка наличия дополнительных файлов
    missing_files = [f for f in EXTRA_DATA if not os.path.exists(f)]
    if missing_files:
        print(color(f"  ! Отсутствуют следующие файлы: {', '.join(missing_files)}", COLOR_INFO))
        print(color("    Эти файлы не будут включены в установщик", COLOR_INFO))
    else:
        print(color("  + Все дополнительные файлы найдены", COLOR_SUCCESS))
    
    return True

# Проверка, поддерживает ли терминал ANSI цвета
def supports_ansi_colors():
    """Проверяет, поддерживает ли текущий терминал ANSI-цвета"""
    # В Windows 10 с обновлением 1607+ поддержка ANSI встроена
    if platform.system() == "Windows":
        import ctypes
        from ctypes import windll, wintypes
        
        # Проверка версии Windows 10+
        if platform.release() == "10" and int(platform.version().split('.')[2]) >= 14393:
            try:
                # Получаем дескриптор консоли
                handle = windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
                
                # Проверяем, поддерживает ли консоль ANSI
                mode = wintypes.DWORD()
                if windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    # Проверяем бит ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)
                    if mode.value & 0x0004:
                        return True
                    # Пробуем включить поддержку ANSI
                    return bool(windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004))
            except Exception:
                return False
        return False  # Старая версия Windows
    
    # В Unix/Linux/MacOS обычно есть поддержка ANSI
    return True

if __name__ == "__main__":
    # Проверяем поддержку цветов и предлагаем установить colorama при необходимости
    has_color_support = COLORAMA_AVAILABLE or supports_ansi_colors()
    
    if not has_color_support and platform.system() == "Windows":
        print("\n" + "=" * 60)
        print("Обнаружена консоль Windows без поддержки цветного вывода")
        print("Текст будет отображаться без цветового форматирования")
        print("\nДля цветного отображения:")
        print("1. Установите библиотеку colorama: pip install colorama")
        print("2. Или запустите скрипт в Windows Terminal, который поддерживает ANSI-цвета")
        print("=" * 60 + "\n")
        install = input("Установить colorama сейчас? (y/n): ")
        if install.lower() == 'y':
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "colorama"], check=True)
                print("\nПакет colorama успешно установлен!")
                print("Перезапустите скрипт для применения изменений")
                sys.exit(0)
            except Exception as e:
                print(f"\nОшибка установки colorama: {e}")
                print("Попробуйте установить вручную: pip install colorama")
    
    if len(sys.argv) > 1:
        # Запуск с аргументами командной строки
        if sys.argv[1] == "--build":
            build()
        elif sys.argv[1] == "--installer":
            create_installer()
        elif sys.argv[1] == "--all":
            if build():
                create_installer()
        elif sys.argv[1] == "--clean":
            cleanup()
        else:
            print(color(f"Неизвестный аргумент: {sys.argv[1]}", COLOR_ERROR))
            print(color("Доступные аргументы: --build, --installer, --all, --clean", COLOR_WARNING))
    else:
        # Интерактивный режим с меню
        if check_tools():
            while True:
                choice = show_menu()
                
                if choice == "1":
                    build()
                elif choice == "2":
                    create_installer()
                elif choice == "3":
                    if build():
                        create_installer()
                elif choice == "4":
                    cleanup()
                elif choice == "5":
                    show_module_info()
                elif choice == "0":
                    print(color("\nВыход из программы сборки.", COLOR_WARNING))
                    break
                else:
                    print(color("\nНеверный выбор. Попробуйте снова.", COLOR_ERROR))
                
                input(color("\nНажмите Enter для продолжения...", COLOR_PROMPT))
