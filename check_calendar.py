
from datetime import date
import chinese_calendar

dates_to_check = [
    date(2026, 2, 13),
    date(2026, 2, 14),
    date(2026, 2, 15),
    date(2026, 2, 16),
    date(2026, 2, 17)
]

print("Date | Is Workday? | Holiday Name")
print("-" * 35)
for d in dates_to_check:
    is_work = chinese_calendar.is_workday(d)
    h_name = chinese_calendar.get_holiday_detail(d)[1]
    h_name_str = h_name if h_name else "N/A"
    print(f"{d} | {is_work} | {h_name_str}")
