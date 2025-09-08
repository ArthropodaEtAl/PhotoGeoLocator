Written to assign photo locations for posts on Inaturalist

This code will read your local time zone from the computer and assign it to the .JPG files, so if you took your photos in a different time zone than your computer clock, you will have to change this in the interface.

The code will skip photos outside of the GPX data time window, and skip photos that already have location data! This is really helpful if your store all of your photos in one folder.

Follow these instructions:
1. Get your GPX file from Strava or other website

2. [Optional] create a python virtual environment with `python -m venv .venv` and activate it with `.venv/Scripts/activate` or `.venv/bin/activate`

3. Use the requirements.txt to install the required libraries.

4. Double click on the .bat or .sh file.

5. Input the file locations for the gpx data 

6. If your camera clock is off compared to your computer time. (This can also be another way to manually offset the photo timezone with your computer clock.)

7. Add locations

8. Profit by having located your bugs

Demonstration: https://youtu.be/SuSal7x5lFQ

Use case: https://www.inaturalist.org/journal/melspippin/85592-adding-location-to-dcim-photos-using-gpx-data
