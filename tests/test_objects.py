import datetime
import pytz
import tzlocal

from caldav.objects import _add_missing_tz

SOMEWHERE_REMOTE = pytz.timezone('Brazil/DeNoronha')

def test_add_missing_tz_date():
    sample = datetime.date(2019,5,14)
    res = _add_missing_tz(sample)
    assert res == sample


def test_add_missing_tz_dt_with_some_tzinfo():
    sample = datetime.datetime(2019, 5, 14, 21, 10, 23, 23, tzinfo=SOMEWHERE_REMOTE)
    res = _add_missing_tz(sample)
    assert res == sample


def test_add_missing_tz_dt_with_local_tz():
    sample = datetime.datetime(2019,5,14,21,10,23,23).astimezone()
    res = _add_missing_tz(sample)
    assert res == sample


def test_add_missing_tz_naive_dt():
    naive_input = datetime.datetime(2019,5,14,21,10,23,23)
    res = _add_missing_tz(naive_input)
    # we use pytz as comparison here - could be swapped with the expresssion used in implementation
    exp = tzlocal.get_localzone().localize(naive_input)
    assert res == exp