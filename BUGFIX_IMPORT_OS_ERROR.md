# 🐛 Исправление ошибки импорта os в add_playlist()

## Версия 0.13.1 - Исправление UnboundLocalError

### 🚨 **Проблема:**

При добавлении плейлиста из файла возникала ошибка:

```
Traceback (most recent call last):
  File "main.py", line 261, in <lambda>
    add_button.clicked.connect(lambda: self.add_playlist(dialog, tabs.currentIndex()))
  File "main.py", line 295, in add_playlist
    if not os.path.exists(file_path):
           ^^
UnboundLocalError: cannot access local variable 'os' where it is not associated with a value
```

### 🔍 **Причина ошибки:**

#### **Конфликт области видимости:**
В методе `add_playlist()` модуль `os` использовался в двух местах:

1. **Раннее использование** (строка 295):
```python
if not os.path.exists(file_path):  # ❌ os еще не импортирован
```

2. **Локальный импорт** (строка 306):
```python
import os  # ✅ Импорт происходит позже
default_name = os.path.splitext(os.path.basename(file_path))[0]
```

#### **Проблема Python:**
Python видит, что `os` импортируется локально в функции, поэтому считает его локальной переменной. Но попытка использовать `os` до его импорта приводит к `UnboundLocalError`.

### ✅ **Решение:**

#### **Перенос импорта в начало метода:**

**До (ошибочный код):**
```python
def add_playlist(self, dialog, tab_index):
    """Добавляет плейлист в зависимости от выбранной вкладки"""
    if tab_index == 0:  # Файл
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(dialog, "Ошибка", "Выберите файл плейлиста")
            return
        if not os.path.exists(file_path):  # ❌ ОШИБКА: os не импортирован
            QMessageBox.warning(dialog, "Ошибка", "Файл не найден")
            return

        # Получаем название плейлиста
        file_name = self.file_name_edit.text().strip()
        if file_name:
            self.parent.playlist_names[file_path] = file_name
        else:
            # Используем имя файла без расширения как название по умолчанию
            import os  # ✅ Импорт происходит здесь, но слишком поздно
            default_name = os.path.splitext(os.path.basename(file_path))[0]
            self.parent.playlist_names[file_path] = default_name
```

**После (исправленный код):**
```python
def add_playlist(self, dialog, tab_index):
    """Добавляет плейлист в зависимости от выбранной вкладки"""
    import os  # ✅ Импортируем os в начале метода
    
    if tab_index == 0:  # Файл
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(dialog, "Ошибка", "Выберите файл плейлиста")
            return
        if not os.path.exists(file_path):  # ✅ Теперь os доступен
            QMessageBox.warning(dialog, "Ошибка", "Файл не найден")
            return

        # Получаем название плейлиста
        file_name = self.file_name_edit.text().strip()
        if file_name:
            self.parent.playlist_names[file_path] = file_name
        else:
            # Используем имя файла без расширения как название по умолчанию
            default_name = os.path.splitext(os.path.basename(file_path))[0]  # ✅ os уже импортирован
            self.parent.playlist_names[file_path] = default_name
```

### 🔧 **Техническое объяснение:**

#### **Область видимости в Python:**
1. **Глобальный импорт** - модуль доступен во всей функции
2. **Локальный импорт** - модуль доступен только после строки импорта
3. **Конфликт** - если есть локальный импорт, Python считает переменную локальной во всей функции

#### **Правильные подходы:**
1. **Импорт в начале файла** (лучший вариант):
```python
import os  # В начале файла

def add_playlist(self, dialog, tab_index):
    if not os.path.exists(file_path):  # ✅ Работает
```

2. **Импорт в начале функции** (наш случай):
```python
def add_playlist(self, dialog, tab_index):
    import os  # В начале функции
    if not os.path.exists(file_path):  # ✅ Работает
```

3. **Избегать** локального импорта в середине функции после использования

### 📊 **Результат исправления:**

#### **До исправления:**
- ❌ **UnboundLocalError** при добавлении файлового плейлиста
- ❌ **Невозможность использовать** функцию добавления плейлистов
- ❌ **Критическая ошибка** в основной функциональности

#### **После исправления:**
- ✅ **Функция работает корректно**
- ✅ **Можно добавлять плейлисты** из файлов
- ✅ **Проверка существования файла** работает
- ✅ **Автозаполнение названий** функционирует

### 🧪 **Тестирование:**

#### **Создан тестовый плейлист:**
```m3u
#EXTM3U
#EXTINF:-1,Тестовый канал 1
http://example.com/stream1.m3u8
#EXTINF:-1,Тестовый канал 2
http://example.com/stream2.m3u8
#EXTINF:-1,Тестовый канал 3
http://example.com/stream3.m3u8
```

#### **Проверенные сценарии:**
1. ✅ **Запуск приложения** - без ошибок
2. ✅ **Открытие диалога** добавления плейлиста
3. ✅ **Выбор файла** через кнопку "Обзор"
4. ✅ **Автозаполнение названия** плейлиста
5. ✅ **Добавление плейлиста** без ошибок

### 🎯 **Извлеченные уроки:**

#### **Лучшие практики импорта:**
1. **Импортировать модули в начале файла** когда это возможно
2. **Если нужен локальный импорт** - размещать в начале функции
3. **Избегать импорта в середине функции** после использования модуля
4. **Тестировать все пути выполнения** кода

#### **Отладка подобных ошибок:**
1. **Искать локальные импорты** в функции
2. **Проверять порядок использования** переменных
3. **Понимать область видимости** Python
4. **Использовать IDE** для выявления таких проблем

### 🔮 **Предотвращение в будущем:**

1. **Статический анализ кода** - использование pylint, flake8
2. **Тестирование всех веток** кода
3. **Code review** - проверка импортов
4. **IDE предупреждения** - внимание к подсветке синтаксиса

Ошибка исправлена, функциональность восстановлена, и теперь пользователи могут без проблем добавлять плейлисты из файлов с пользовательскими названиями!
