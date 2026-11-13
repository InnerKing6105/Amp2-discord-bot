import unittest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from server_ops import (SparkSampler, parse_time, backup_list, last_backup, backup_age_hours,
                        parse_restart_clock, restart_actions)


class ServerOperationsTests(unittest.TestCase):
    def test_backups_require_a_real_record(self):
        self.assertIsNone(last_backup([]))
        self.assertIsNone(last_backup([{'name': 'no timestamp'}]))
        with self.assertRaises(ValueError):
            backup_list({'unrelated': []})

    def test_backups_sort_by_datetime_not_name(self):
        data = [{'name':'older', 'timestamp':'2026-11-12T14:00:00Z'},
                {'name':'newer', 'timestamp':'2026-11-13T13:00:00Z'}]
        when, item = last_backup(data)
        self.assertEqual(item['name'], 'newer')
        self.assertEqual(backup_age_hours((when,item), datetime(2026,11,13,14,tzinfo=timezone.utc)),1)

    def test_amp_backup_wrappers(self):
        self.assertEqual(len(backup_list({'Backups':[{'Timestamp': '2026-10-25'}]})),1)
        self.assertEqual(len(backup_list({'Result':[]})),0)

    def test_time_parser_naive_assumed_utc(self):
        self.assertEqual(parse_time('2026-11-13T14:00:00').tzinfo, timezone.utc)
        self.assertIsNone(parse_time('nonsense'))

    def test_parse_spark_multi_window(self):
        now = datetime.now(timezone.utc)
        s = SparkSampler(); s.start(now)
        texts = [
            '[17:26:51 INFO]: [⚡] TPS from last 5s, 10s, 1m, 5m, 15m:',
            '[17:26:51 INFO]: [⚡]  11.6, 16.7, 13.5, 10.9, 12.1',
            '[17:26:51 INFO]: [⚡] Tick durations (min/med/95%ile/max ms) from last 10s, 1m:',
            '[17:26:51 INFO]: [⚡]  27.1/61.5/74.3/136.8;  39.2/65.8/73.0/101.0',
        ]
        for line in texts:
            self.assertTrue(s.consume({'Contents':line,'Type':'Console','Source':'Console'},now))
        self.assertEqual(s.display(now),('13.50 TPS (1m)','61.5 median / 74.3 p95 ms (10s)'))

    def test_spark_stale_is_not_presented_as_live(self):
        now=datetime.now(timezone.utc); s=SparkSampler(); s.start(now)
        for t in ['TPS from last 5s, 10s, 1m, 5m, 15m:', '20.0, 19.9, 19.7, 19.8, 19.8']:
            s.consume({'Contents':t},now)
        self.assertEqual(s.display(now+timedelta(hours=1)), ('Not available','Not available'))

    def test_spark_ignores_chat_entries(self):
        now=datetime.now(timezone.utc); s=SparkSampler(); s.start(now)
        self.assertFalse(s.consume({'Contents':'TPS from last 5s, 10s, 1m:', 'Type':'chat'},now))

    def test_restart_clock(self):
        self.assertEqual(parse_restart_clock('05:00'),(5,0))
        for bad in ['5:00','24:00','05:60','yes']:
            with self.assertRaises(ValueError): parse_restart_clock(bad)

    def test_restart_warnings_and_once_per_day(self):
        tz=ZoneInfo('America/Toronto')
        d=datetime(2026,11,14,4,45,0,tzinfo=tz)
        self.assertEqual(restart_actions(d,(5,0),set(),None), [('warn',15)])
        self.assertEqual(restart_actions(d,(5,0),{15},None), [])
        self.assertEqual(restart_actions(d.replace(hour=5,minute=0),(5,0),set(),None), [('restart',0)])
        self.assertEqual(restart_actions(d.replace(hour=5,minute=3),(5,0),set(),None), [])
        self.assertEqual(restart_actions(d.replace(hour=5,minute=0),(5,0),set(),'2026-11-14'),[])

    def test_restart_dst_local_time(self):
        tz=ZoneInfo('America/Toronto')
        before=datetime(2026,3,8,4,59,0,tzinfo=tz)
        self.assertEqual(restart_actions(before,(5,0),set(),None),[('warn',1)])


if __name__ == '__main__': unittest.main()
