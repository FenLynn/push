from datetime import date

import core.trading_calendar as calendar


def test_holiday_cn_current_is_off_day_schema_is_supported():
    calendar._holiday_data.clear()

    assert calendar.is_china_holiday(date(2026, 9, 25)) is True
    assert calendar.is_china_workday(date(2026, 9, 20)) is True
    assert calendar.get_china_holiday_name(date(2026, 9, 25)) == '中秋节'


def test_2026_mid_autumn_has_no_makeup_day():
    upcoming = calendar.get_upcoming_china_holidays(
        date(2026, 7, 21),
        limit=2,
        years_ahead=1,
    )

    assert upcoming[0]['name'] == '中秋节'
    assert upcoming[0]['date_iso'] == '2026-09-25'
    assert upcoming[0]['end_date_iso'] == '2026-09-27'
    assert upcoming[0]['makeup_days'] is None
    assert upcoming[1]['name'] == '国庆节'
    assert upcoming[1]['makeup_days'] == '09/20, 10/10'
