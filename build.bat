@echo off
chcp 65001 >nul
echo ================================================
echo 🎬 MaksIPTV Player - Быстрая сборка
echo ================================================
echo.

echo 🚀 Запуск сборки...
python build.py

echo.
echo ✅ Готово! Нажмите любую клавишу для выхода...
pause >nul
