import datetime

import pytz
import tzlocal
from caldav.elements.cdav import _to_utc_date_string
from caldav.elements.cdav import CalendarQuery

SOMEWHERE_REMOTE = pytz.timezone("Brazil/DeNoronha")  # UTC-2 and no DST


def test_element():
    cq = CalendarQuery()
    assert str(cq).startswith("<?xml")
    assert not "xml" in repr(cq)
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


def test_to_utc_date_string_dt_with_pytz_tzinfo():
    input = datetime.datetime(2019, 5, 14, 21, 10, 23, 23)
    res = _to_utc_date_string(SOMEWHERE_REMOTE.localize(input))
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
