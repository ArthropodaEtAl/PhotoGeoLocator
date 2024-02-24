import os
import datetime
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

from exif import Image
import tzlocal
import pandas as pd
import numpy as np
import argparse

parser = argparse.ArgumentParser(
    description="""Add gps coordinates to photos by comparing photo timestamps
 against a .gpx file and interpolating latitude and longitude.""",
    usage="geolocate_photos.py PHOTOS_FOLDER GPX_FILE [--offset OFFSET_MINS] [-h]",
    epilog="Example: geolocate_photos.py './photos/' ",
)
parser.add_argument("photos_folder", help="Folder containing photos to be processed")
parser.add_argument("gpx_file", help=".gpx file containing latitude, longitude, and timestamps")
parser.add_argument(
    "--offset_mins",
    help="Offset (in minutes) to be added to photo times to correct for camera clock",
)


def extract_points(filepath) -> pd.DataFrame:
    """
    Extracts gps coordinates and timestamps from a .gpx file to a dataframe
    """
    points = ET.parse(filepath)
    root = points.getroot()

    header = ["Time", "Datetime", "Timestamp", "Latitude", "Longitude"]
    point_list = []

    tz = get_timezone()

    namespace = "{http://www.topografix.com/GPX/1/1}"
    for elm in root.findall(f".//{namespace}trkpt"):
        time = elm.findall(f".//{namespace}time")[0].text
        dt = datetime.datetime.strptime(time, "%Y-%m-%dT%H:%M:%S%z").astimezone(tz).replace(tzinfo=None)
        ts = dt.timestamp()
        lon = float(elm.get("lon"))
        lat = float(elm.get("lat"))
        point_list.append([time, dt, ts, lat, lon])

    points_df = pd.DataFrame(point_list, columns=header)
    return points_df


def deg_to_dms(deg):
    """Convert from decimal degrees to degrees, minutes, seconds.
    Modified from:
    https://scipython.com/book/chapter-2-the-core-python-language-i/additional-problems/converting-decimal-degrees-to-deg-min-sec/
    """

    mins, secs = divmod(abs(deg) * 3600, 60)
    degs, mins = divmod(mins, 60)
    if deg < 0:
        degs = -degs
    degs, mins = int(degs), int(mins)
    hemi = 1 if degs > 0 else -1
    degs *= hemi

    return degs, mins, secs, hemi


def get_timezone() -> ZoneInfo:
    return tzlocal.get_localzone()


def load_photo(path: str) -> Image:
    with open(path, "rb") as image_file:
        return Image(image_file)


def photo_has_lat_long(photo: Image) -> bool:
    try:
        _, _, _, _ = (
            photo.gps_latitude,
            photo.gps_longitude,
            photo.gps_latitude_ref,
            photo.gps_longitude_ref,
        )
        return True
    except (AttributeError, KeyError):
        return False


def photo_has_datetime(photo: Image) -> bool:
    try:
        _ = photo.datetime_original
        return True
    except (AttributeError, KeyError):
        return False


def get_photo_datetime(photo: Image, timezone: ZoneInfo = None) -> datetime.datetime:
    try:
        dt = datetime.datetime.strptime(photo.datetime_original, "%Y:%m:%d %H:%M:%S")
        if timezone:
            return dt.astimezone(timezone)
        else:
            return dt
    except Exception as e:
        print("get_photo_datetime", e, photo)


def tag_photos(
    points_df: pd.DataFrame,
    photo_paths: list[str],
    photo_date_offset: pd.Timedelta = None,
    valid_filetypes=[".jpg", ".jpeg"],
    overwrite=False,  # TODO add checkbox to GUI
):
    """
    Adds location data to photos by interpolating timestamps from gps data
    """

    mindt = points_df["Datetime"].min()
    maxdt = points_df["Datetime"].max()

    paths = [f for f in photo_paths if os.path.splitext(f)[1].lower() in valid_filetypes]

    for photo_path in paths:
        with open(photo_path, "rb") as image_file:
            photo = Image(image_file)

        # Check if file has a time to interpolate from
        if not photo_has_datetime(photo):
            print(f"{photo_path} : skipping, no time available")
            continue

        # Check if lat/long already exist on file. If so, skip
        if photo_has_lat_long(photo) and not overwrite:
            print(f"{photo_path} : skipping, location already exists")
            continue

        # Retrieve datetime from photo, check if inside bounds
        photodt = get_photo_datetime(photo) + photo_date_offset
        photots = photodt.timestamp()

        if photodt < mindt or photodt > maxdt:
            photo_t = photodt.isoformat()
            min_t = mindt.isoformat()
            max_t = maxdt.isoformat()
            print(f"{photo_path} : skipping, time {photo_t} outside of bounds {min_t} - {max_t}")
            continue

        print(f"{photo_path} : adding location")
        photolat = np.interp(photots, points_df["Timestamp"], points_df["Latitude"])
        photolon = np.interp(photots, points_df["Timestamp"], points_df["Longitude"])

        # Write new location data to image
        with open(photo_path, "wb") as image_file:
            if overwrite and (hasattr(photo, "gps_latitude") or hasattr(photo, "gps_longitude")):
                try:
                    del photo.gps_latitude
                    del photo.gps_longitude
                except Exception as e:
                    print(e, "Could not delete location data on photo", photo_path, e)

            lat_d, lat_m, lat_s, lat_hemi = deg_to_dms(photolat)
            dms_lat = (lat_d, lat_m, lat_s)
            photo.gps_latitude_ref = "N" if lat_hemi == 1 else "S"
            photo.gps_latitude = dms_lat

            lon_d, lon_m, lon_s, lon_hemi = deg_to_dms(photolon)
            dms_lon = (lon_d, lon_m, lon_s)
            photo.gps_longitude_ref = "E" if lon_hemi == 1 else "W"
            photo.gps_longitude = dms_lon

            image_file.write(photo.get_file())


def DO_GUI():
    import tkinter as tk
    from tkinter import ttk, filedialog
    from tkinterdnd2 import DND_FILES, TkinterDnD

    root = TkinterDnD.Tk()
    root.geometry("1000x600")

    class AppState:
        def __init__(self):
            self.all_files = []
            self.images = []
            self.points_df = pd.DataFrame()
            self.offset_mins = datetime.timedelta(0)

        def add_folder(self):
            folder = filedialog.askdirectory()
            if len(folder) > 0:
                self.process_paths([folder])

        def add_files(self):
            files = filedialog.askopenfilenames()
            if len(files) > 0:
                self.process_paths(files)

        def generic_drag(self, event):
            # parse space-separated, {}-delimited list of paths
            paths = []
            parts = event.data.split(" ")
            i = 0
            while i < len(parts):
                part = parts[i]
                if part[0] != "{":
                    paths.append(part)
                else:
                    j = 0
                    while i + j < len(parts):
                        if parts[i + j][-1] == "}":
                            full = " ".join(parts[i : i + j + 1])
                            full = full[1:-1]
                            paths.append(full)
                            i += j
                            break
                        j += 1
                i += 1

            self.process_paths(paths)

        def process_paths(self, paths):
            for path in paths:
                if os.path.isfile(path) and os.path.splitext(path)[1] == ".gpx":
                    self.set_gpx_path(path)
                elif os.path.isdir(path):
                    # TODO support walk instead of listdir?
                    full_paths = [os.path.join(path, file) for file in os.listdir(path)]
                    self.add_photos(full_paths)
                elif os.path.isfile(path):
                    self.add_photos([path])

        def clear_photos(self):
            file_listbox.delete(0, tk.END)
            self.images = []
            self.all_files = []
            self.update_details()

        def add_photos(self, photo_paths: list[str]):
            for full_filepath in photo_paths:
                try:
                    self.images.append(load_photo(full_filepath))
                    self.all_files.append(full_filepath)
                    file_listbox.insert(tk.END, full_filepath)
                except Exception as e:
                    print(e)
            self.update_details()

        def set_gpx_path(self, path: str):
            gpx_sv.set(path)  # triggers self.edit_gpx()

        def update_details(self):
            folder_details = [""]
            gpx_details = [""]
            both_details = ""
            same_day = False
            min_photo_dt = None
            max_photo_dt = None
            min_gps_dt = None
            max_gps_dt = None

            loaded_files = len(self.all_files) > 0
            loaded_gpx = len(self.points_df) > 0

            if loaded_files:
                image_times = [get_photo_datetime(i) + self.offset_mins for i in self.images]
                min_photo_dt = min(image_times)
                max_photo_dt = max(image_times)
                if min_photo_dt.date() == max_photo_dt.date():
                    same_day = True
                count_has_loc = sum([photo_has_lat_long(image) for image in self.images])
                folder_details = [
                    f"{len(self.all_files)} images",
                    f"{count_has_loc} with location data",
                ]

            if loaded_gpx:
                min_gps_dt = self.points_df["Datetime"].min()
                max_gps_dt = self.points_df["Datetime"].max()
                if min_gps_dt.date() == max_gps_dt.date():
                    same_day = True
                gpx_details = [
                    f"{len(self.points_df)} gpx points",
                ]

            if loaded_files and loaded_gpx:
                if min_photo_dt.date() == max_photo_dt.date() == min_gps_dt.date() == max_gps_dt.date():
                    same_day = True
                else:
                    same_day = False
                good_images = [it for it in image_times if it >= min_gps_dt and it <= max_gps_dt]
                both_details = [f"{len(good_images)} images in bounds"]

            if same_day:
                dt_format = "%H:%M:%S"
            else:
                dt_format = "%Y-%m-%d %H:%M:%S"
            if loaded_files:
                folder_details.append(f"{min_photo_dt.strftime(dt_format)} - {max_photo_dt.strftime(dt_format)}")
            if loaded_gpx:
                gpx_details.append(f"{min_gps_dt.strftime(dt_format)} - {max_gps_dt.strftime(dt_format)}")

            self.set_details(
                "\n".join(
                    [
                        "\n".join(folder_details),
                        "",
                        "\n".join(gpx_details),
                        "",
                        "\n".join(both_details),
                    ]
                )
            )

        def edit_gpx(self, event):
            path = event.get()
            try:
                self.points_df = extract_points(path)
            except Exception as e:
                print(type(e), e)
                self.points_df = pd.DataFrame()
            self.update_details()

        def edit_offset(self, event):
            entry = event.get()
            try:
                value = float(entry)
            except ValueError:
                value = 0
            self.offset_mins = datetime.timedelta(minutes=value)
            self.update_details()

        def set_details(self, text):
            detail_sv.set(text)

        def on_go_button_click(self):
            tag_photos(self.points_df, self.all_files, self.offset_mins)

            # reload photos
            for i, file in enumerate(self.all_files):
                self.images[i] = load_photo(file)

            self.update_details()

    AS = AppState()

    # Main window
    root.title("Geolocate photos")

    # Frames
    left_col = ttk.Frame(root)
    left_col.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    right_col = ttk.Frame(root)
    right_col.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

    bottom_row = ttk.Frame(root)
    bottom_row.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

    verybottom_row = ttk.Frame(root)
    verybottom_row.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=2)
    root.rowconfigure(0, weight=1)

    # Widgets
    root.drop_target_register(DND_FILES)
    root.dnd_bind("<<Drop>>", AS.generic_drag)

    addfile_button = ttk.Button(left_col, text="Add files", command=AS.add_files)
    addfile_button.pack(expand=False, fill="both")

    addfolder_button = ttk.Button(left_col, text="Add folder", command=AS.add_folder)
    addfolder_button.pack(expand=False, fill="both")

    file_listbox = tk.Listbox(left_col, height=60, width=60)
    file_listbox.pack(side="top", fill="both", expand=True)

    clear_button = ttk.Button(left_col, text="Clear photos", command=AS.clear_photos)
    clear_button.pack(expand=False, fill="both")

    gpx_sv = tk.StringVar(value="Path to .gpx file")
    gpx_sv.trace_add("write", lambda name, index, mode, sv=gpx_sv: AS.edit_gpx(sv))
    gpx_input = ttk.Entry(left_col, textvar=gpx_sv, width=60)
    gpx_input.pack(side="left", fill="x", expand=True)

    detail_sv = tk.StringVar(value="Upload photos and a .gpx file")
    detail_text_scrolled = tk.Label(right_col, textvariable=detail_sv, height=20, width=40)
    detail_text_scrolled.pack(fill="both", expand=True)

    offset_label = tk.Label(bottom_row, text="Offset added to photos (minutes)")
    offset_label.pack(side="left")

    offset_sv = tk.StringVar(value="0")
    offset_sv.trace_add("write", lambda name, index, mode, sv=offset_sv: AS.edit_offset(sv))
    offset_entry = ttk.Entry(bottom_row, textvar=offset_sv, width=60)
    offset_entry.pack(side="right", fill="x", expand=True)

    go_button = ttk.Button(verybottom_row, text="Add locations to photos", command=AS.on_go_button_click)
    go_button.pack(expand=True, fill="both")

    # Set minimum sizes for the listbox and text widget
    file_listbox.config(height=3)
    detail_text_scrolled.config(height=3)

    AS.update_details()

    # Start GUI loop
    root.mainloop()


def test_strip_locations(folder):
    paths = [os.path.join(folder, f) for f in os.listdir(folder)]
    for photo_path in paths:
        try:
            with open(photo_path, "rb") as image_file:
                photo = Image(image_file)
            with open(photo_path, "wb") as image_file:
                try:
                    del photo.gps_latitude_ref
                except Exception as e:
                    print(e)
                try:
                    del photo.gps_latitude
                except Exception as e:
                    print(e)
                try:
                    del photo.gps_longitude_ref
                except Exception as e:
                    print(e)
                try:
                    del photo.gps_longitude
                except Exception as e:
                    print(e)
                image_file.write(photo.get_file())
        except Exception as e:
            print(e)


if __name__ == "__main__":
    # args = parser.parse_args()
    # photos_folder = args.photos_folder
    # gpx_file = args.gpx_file
    # offset = args.offset_mins
    # try:
    #     offset_num = float(offset)
    # except:
    #     offset_num = 0
    # offset_mins = datetime.timedelta(minutes=float(offset_num))

    # points_df = extract_points(gpx_file)
    # tag_photos(points_df, photos_folder, offset_mins)

    DO_GUI()
