@echo off
cd /d "C:\Users\81194081\OneDrive - Pepsico\PVSmartFinder"
echo Launching PV Smart Finder (safe PATH)...
python -m pip install -r requirements.txt
python -m streamlit run pv_finder_app.py
pause
