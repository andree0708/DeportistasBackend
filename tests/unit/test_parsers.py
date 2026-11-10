"""Tests de parsers de archivos deportivos."""
import pytest
from datetime import datetime, timezone
from app.services.imports.gpx_parser import GPXParser
from app.services.imports.tcx_parser import TCXParser
from app.services.imports.csv_parser import CSVParser


GPX_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <trk>
    <name>Test Run</name>
    <trkseg>
      <trkpt lat="40.4168" lon="-3.7038">
        <ele>667</ele>
        <time>2024-03-15T08:00:00</time>
      </trkpt>
      <trkpt lat="40.4178" lon="-3.7028">
        <ele>670</ele>
        <time>2024-03-15T08:05:00</time>
      </trkpt>
      <trkpt lat="40.4188" lon="-3.7018">
        <ele>672</ele>
        <time>2024-03-15T08:10:00</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>"""

CSV_SAMPLE = b"""date,distance (km),elapsed time,avg hr,max hr,avg cadence
2024-03-10 08:00:00,5.2,00:28:30,152,178,170
2024-03-12 07:30:00,8.1,00:45:20,158,180,172
2024-03-15 08:00:00,10.0,00:55:00,160,182,174
"""

TCX_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities>
    <Activity Sport="Running">
      <Id>2024-03-15T08:00:00Z</Id>
      <Lap StartTime="2024-03-15T08:00:00Z">
        <TotalTimeSeconds>1800</TotalTimeSeconds>
        <DistanceMeters>5000</DistanceMeters>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>"""


class TestGPXParser:
    def test_can_parse_gpx(self):
        parser = GPXParser()
        assert parser.can_parse("activity.gpx") is True
        assert parser.can_parse("activity.fit") is False

    def test_parse_basic_gpx(self):
        parser = GPXParser()
        activities = parser.parse(GPX_SAMPLE, "test.gpx")
        assert len(activities) == 1
        a = activities[0]
        assert a.distance_meters > 0
        assert a.started_at is not None
        assert a.title == "Test Run"

    def test_parse_gpx_computes_derived(self):
        parser = GPXParser()
        activities = parser.parse(GPX_SAMPLE, "test.gpx")
        a = activities[0]
        assert a.avg_speed_kmh is not None or a.avg_pace_sec_per_km is not None


class TestCSVParser:
    def test_can_parse_csv(self):
        parser = CSVParser()
        assert parser.can_parse("history.csv") is True
        assert parser.can_parse("history.gpx") is False

    def test_parse_csv_multiple_rows(self):
        parser = CSVParser()
        activities = parser.parse(CSV_SAMPLE, "history.csv")
        assert len(activities) == 3

    def test_parse_csv_values(self):
        parser = CSVParser()
        activities = parser.parse(CSV_SAMPLE, "history.csv")
        a = activities[0]
        assert abs(a.distance_meters - 5200) < 1
        assert a.avg_heart_rate_bpm == 152.0

    def test_parse_csv_empty_rows_skipped(self):
        empty_csv = b"date,distance (km),elapsed time\n,,"
        parser = CSVParser()
        activities = parser.parse(empty_csv, "empty.csv")
        assert len(activities) == 0


class TestTCXParser:
    def test_can_parse_tcx(self):
        parser = TCXParser()
        assert parser.can_parse("activity.tcx") is True

    def test_parse_tcx_basic(self):
        parser = TCXParser()
        activities = parser.parse(TCX_SAMPLE, "test.tcx")
        assert len(activities) == 1
        a = activities[0]
        assert a.distance_meters == 5000.0
        assert a.duration_seconds == 1800.0
