import sys

sys.path.append("..")
from geolocate_photos import extract_points


def test_gpx10():
    df = extract_points("tests/test10.gpx")
    assert len(df) > 0


def test_gpx11():
    df = extract_points("tests/test11.gpx")
    assert len(df) > 0
