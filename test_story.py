import datetime as dt
import unittest

from story import TZ, choose_slots, music_for_day


def event(title, date, start, end):
    return {"summary": title,
            "start": {"dateTime": f"{date}T{start}:00+08:00"},
            "end": {"dateTime": f"{date}T{end}:00+08:00"}}


class SlotRulesTest(unittest.TestCase):
    def test_booked_slot_is_removed_and_three_available_days_selected(self):
        events = [
            event("牙齒淨白_可預約", "2026-10-07", "14:00", "21:00"),
            event("牙齒淨白_可預約", "2026-10-08", "13:00", "21:00"),
            event("已預約", "2026-10-08", "16:00", "17:00"),
            event("牙齒淨白_可預約", "2026-10-09", "12:00", "21:00"),
        ]
        slots = choose_slots(events, dt.datetime(2026, 10, 6, 9, tzinfo=TZ))
        self.assertEqual([x["date"] for x in slots], ["2026-10-07", "2026-10-08", "2026-10-09"])
        self.assertNotIn("16:00", slots[1]["hours"])
        self.assertIn("17:00", slots[1]["hours"])

    def test_partial_hour_and_past_hour_are_not_published(self):
        events = [event("牙齒淨白_可預約", "2026-10-07", "14:30", "17:00")]
        slots = choose_slots(events, dt.datetime(2026, 10, 7, 15, 30, tzinfo=TZ))
        self.assertEqual(slots[0]["hours"], ["16:00"])

    def test_five_tracks_rotate_by_taipei_day(self):
        days = [dt.date(2026, 10, 11) + dt.timedelta(days=offset) for offset in range(6)]
        self.assertEqual([music_for_day(day).name for day in days],
                         ["track_01.mp3", "track_02.mp3", "track_03.mp3", "track_04.mp3",
                          "track_05.mp3", "track_01.mp3"])


if __name__ == "__main__":
    unittest.main()
