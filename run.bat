@echo off
cd /d "%~dp0"
if not defined BOT_TOKEN if exist token.txt set /p BOT_TOKEN=<token.txt
py -3.13 bot.py
pause
