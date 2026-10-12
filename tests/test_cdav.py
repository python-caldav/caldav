import datetime

import pytest
import tzlocal

from caldav.elements.cdav import CalendarQuery, _to_utc_date_string

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

SOMEWHERE_REMOTE = zoneinfo.ZoneInfo("Brazil/DeNoronha")  # UTC-2 and no DST


def test_element():
    cq = CalendarQuery()
    assert str(cq).startswith("<?xml")
    assert "xml" not in repr(cq)
    assert "CalendarQuery" in repr(cq)
    assert "calendar-query" in str(cq)


def test_to_utc_date_string_date():
    input = datetime.date(2019, 5, 14)
    res = _to_utc_date_string(input)
    assert res == "20190514T000000Z"


def test_to_utc_date_string_utc():
    input = datetime.datetime(2019, 5, 14, 21, 10, 23, 23, tzinfo=datetime.timezone.utc)
    try:
        res = _to_utc_date_string(input.astimezone())
    except:
        ## old python does not support astimezone() without a parameter given
        res = _to_utc_date_string(input.astimezone(tzlocal.get_localzone()))
    assert res == "20190514T211023Z"


def test_to_utc_date_string_dt_with_zoneinfo_tzinfo():
    input = datetime.datetime(2019, 5, 14, 21, 10, 23, 23, tzinfo=SOMEWHERE_REMOTE)
    res = _to_utc_date_string(input)
    assert res == "20190514T231023Z"


def test_to_utc_date_string_dt_with_local_tz():
    input = datetime.datetime(2019, 5, 14, 21, 10, 23, 23)
    try:
        res = _to_utc_date_string(input.astimezone())
    except:
        res = _to_utc_date_string(tzlocal.get_localzone())
    exp_dt = datetime.datetime(
        2019, 5, 14, 21, 10, 23, 23, tzinfo=tzlocal.get_localzone()
    ).astimezone(datetime.timezone.utc)
    exp = exp_dt.strftime("%Y%m%dT%H%M%SZ")
    assert res == exp


def test_to_utc_date_string_naive_dt():
    input = datetime.datetime(2019, 5, 14, 21, 10, 23, 23)
    res = _to_utc_date_string(input)
    exp_dt = datetime.datetime(
        2019, 5, 14, 21, 10, 23, 23, tzinfo=tzlocal.get_localzone()
    ).astimezone(datetime.timezone.utc)
    exp = exp_dt.strftime("%Y%m%dT%H%M%SZ")
    assert res == exp


## (min, max) where UTC cannot hold the local time and it is clamped;
## None where it converts.  Year 1 has the zone's local mean time:
## Europe/Oslo is ahead of UTC then, Pacific/Kiritimati (UTC+14 today)
## behind it.
@pytest.mark.parametrize(
    "process_tz, clamped_min, clamped_max",
    [
        ("UTC", "00010101T000000Z", "99991231T235959Z"),
        ("Europe/Oslo", "00010101T000000Z", None),
        ("America/New_York", None, "99991231T235959Z"),
        ("Pacific/Kiritimati", None, None),
    ],
    indirect=["process_tz"],
)
def test_to_utc_date_string_naive_min_max(process_tz, clamped_min, clamped_max):
    ## a naive datetime.min/max (e.g. an open-ended search) is local time
    res_min = _to_utc_date_string(datetime.datetime.min)
    res_max = _to_utc_date_string(datetime.datetime.max)
    assert res_min.startswith("00010101T")
    assert res_max.startswith("99991231T")
    if clamped_min:
        assert res_min == clamped_min
    if clamped_max:
        assert res_max == clamped_max


@pytest.mark.parametrize("process_tz", ["UTC", "Europe/Oslo", "America/New_York"], indirect=True)
def test_to_utc_date_string_aware_out_of_range(process_tz):
    ## an aware datetime keeps its own time zone, whatever the local one
    east = datetime.timezone(datetime.timedelta(hours=5))
    west = datetime.timezone(datetime.timedelta(hours=-5))
    assert _to_utc_date_string(datetime.datetime(1, 1, 1, tzinfo=east)) == "00010101T000000Z"
    late = datetime.datetime(9999, 12, 31, 23, tzinfo=west)
    assert _to_utc_date_string(late) == "99991231T235959Z"


class TestRegressionUnitTestBot:
    def test_to_utc_date_string_min(self):
        input_datetime = datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc)
        res = _to_utc_date_string(input_datetime)
        ## RFC 5545 DATE-TIME has a four-digit year; strftime("%Y")
        ## does not zero-pad it on Linux with Python < 3.14
        assert res == "00010101T000000Z"
        assert _to_utc_date_string(datetime.date(999, 12, 31)) == "09991231T000000Z"
        aware = datetime.datetime(5, 6, 7, tzinfo=datetime.timezone.utc)
        assert _to_utc_date_string(aware) == "00050607T000000Z"
