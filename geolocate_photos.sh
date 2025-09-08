if [ -f ".venv/Scripts/python" ]; then
	.venv/Scripts/python geolocate_photos.py
else
	python geolocate_photos.py
fi