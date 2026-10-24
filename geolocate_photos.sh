#!/bin/bash

if [ -f ".venv/bin/python" ]; then
	.venv/bin/python geolocate_photos.py
else
	python geolocate_photos.py
fi
