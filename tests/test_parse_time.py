import datetime
from zoneinfo import ZoneInfo

from geolocate_photos import get_timezone, timestring_to_datetime


def test_get_timezone():
    assert str(get_timezone()) == "America/Denver"


def test_parse_local_time():
    time_str = "2025-08-23T12:30:49.928Z"
    dt_utc = datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=datetime.timezone.utc
    )
    dt_mtn = dt_utc.astimezone(ZoneInfo("America/Denver"))
    dt_local = timestring_to_datetime(time_str, get_timezone())
    print(dt_utc)
    print(dt_mtn)
    print(dt_local)
