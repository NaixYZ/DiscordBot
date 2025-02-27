@echo off

:: Erstelle eine virtuelle Umgebung
python -m venv venv

:: Aktiviere die virtuelle Umgebung
call venv\Scripts\activate

:: Installiere die benötigten Pakete
pip install -U discord.py

:: Starte den Bot
python main.py

:: Warte auf Benutzereingabe, um das Fenster offen zu halten
pause
