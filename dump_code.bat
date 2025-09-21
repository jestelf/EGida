@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ===== НАСТРОЙКИ =====
set "OUTPUT=code.txt"

rem ===== ВРЕМЕННЫЕ ФАЙЛЫ =====
set "TMP1=%TEMP%\code_list_%RANDOM%_%RANDOM%.tmp"
set "TMP2=%TEMP%\code_list_filtered_%RANDOM%_%RANDOM%.tmp"
set "TMP3=%TEMP%\code_list_sorted_%RANDOM%_%RANDOM%.tmp"

> "%OUTPUT%" (
  echo === СТРУКТУРА ПРОЕКТА ===
  echo Папка: "%CD%"
  echo Дата: %DATE% %TIME%
  echo Исключения: изображения, ^.gitignore, сам %OUTPUT%, а при наличии Git учитывается .gitignore.
  echo.
)

rem ===== ПРОВЕРКА GIT =====
set "HASGIT="
where git >nul 2>nul && git rev-parse --is-inside-work-tree >nul 2>nul && set "HASGIT=1"

if defined HASGIT (
  >> "%OUTPUT%" echo Режим: Git найден, учитываю .gitignore.
  git ls-files --cached --others --exclude-standard > "%TMP1%"
) else (
  >> "%OUTPUT%" echo Режим: Git не найден или это не репозиторий — учитываю только расширения/имена.
  dir /b /s /a:-d > "%TMP1%"
)

rem ===== ФИЛЬТРАЦИЯ (одной строкой, без переносов) =====
findstr /I /V /R /C:"[/\\]\.git[/\\]" /C:"\.gitignore$" /C:"[/\\]code\.txt$" /C:"^code\.txt$" "%TMP1%" | findstr /I /V /R /C:".*\.png$" /C:".*\.jpg$" /C:".*\.jpeg$" /C:".*\.gif$" /C:".*\.bmp$" /C:".*\.webp$" /C:".*\.tif$" /C:".*\.tiff$" /C:".*\.ico$" /C:".*\.svg$" /C:".*\.psd$" /C:".*\.ai$" /C:".*\.heic$" /C:".*\.heif$" > "%TMP2%"

rem Сортировка = аккуратная «структура»
sort "%TMP2%" /O "%TMP3%"

rem ===== РАЗДЕЛ 1: СТРУКТУРА =====
>> "%OUTPUT%" type "%TMP3%"
>> "%OUTPUT%" echo.
>> "%OUTPUT%" echo === КОД ФАЙЛОВ ===

rem ===== РАЗДЕЛ 2: КОНТЕНТ =====
for /f "usebackq delims=" %%F in ("%TMP3%") do (
  set "p=%%F"
  rem В Git-режиме пути с '/', конвертируем:
  set "p=!p:/=\!"
  >> "%OUTPUT%" echo.
  >> "%OUTPUT%" echo ----------[ !p! ]----------
  type "!p!" >> "%OUTPUT%" 2>nul
)

rem ===== УБОРКА =====
del /q "%TMP1%" "%TMP2%" "%TMP3%" >nul 2>nul

echo Готово. Результат: "%OUTPUT%"
exit /b 0
