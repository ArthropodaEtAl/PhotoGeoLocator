@echo off
if exist ".venv\Scripts\python.exe" (
	".venv\Scripts\python.exe" geolocate_photos.py
) else (
	python geolocate_photos.py
)
