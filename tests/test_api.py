"""
Tests for the chart API (api/main.py).
Reference chart: Priya S., 15-Mar-1990, 14:32 IST, Bangalore (same as test_astro.py).

Run:  venv/bin/python tests/test_api.py
"""
import os
import sys
import unittest
from datetime import date, datetime, time
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from api import main
from astro.chart import generate_birth_chart
from astro.dasha import calculate_dasha
from astro.serialization import chart_to_dict, dasha_to_dict, yogas_to_list
from astro.yogas import scan_yogas

AUTH = {"X-API-Key": "test-key"}

BANGALORE = {
    "birth_date": "1990-03-15",
    "birth_time": "14:32",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "timezone": "Asia/Kolkata",
    "reference_date": "2024-06-01",
}


class ChartApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def post(self, body, headers=AUTH):
        return self.client.post("/v1/chart", json=body, headers=headers)

    # ── Correctness ───────────────────────────────────────────────────────────

    def test_known_reference_values(self):
        r = self.post(BANGALORE)
        self.assertEqual(r.status_code, 200, r.text)
        chart = r.json()["chart"]
        self.assertEqual(chart["lagna"], "Cancer")
        self.assertEqual(chart["moon_sign"], "Libra")
        self.assertEqual(chart["moon_nakshatra"], "Swati")

    def test_parity_with_direct_calls(self):
        """The HTTP layer must add nothing and drop nothing except PII."""
        c = generate_birth_chart(
            name="client", birth_date=date(1990, 3, 15), birth_time=time(14, 32),
            birth_place="", latitude=12.9716, longitude=77.5946, timezone="Asia/Kolkata",
        )
        expected_chart = chart_to_dict(c)
        for f in ("name", "birth_place"):
            expected_chart.pop(f)
        body = self.post(BANGALORE).json()
        self.assertEqual(body["chart"], expected_chart)
        self.assertEqual(
            body["dasha"], dasha_to_dict(calculate_dasha(c, reference_date=datetime(2024, 6, 1, 12)))
        )
        self.assertEqual(body["yogas"], yogas_to_list(scan_yogas(c)))

    def test_deterministic(self):
        self.assertEqual(self.post(BANGALORE).json(), self.post(BANGALORE).json())

    def test_meta_records_conventions(self):
        meta = self.post(BANGALORE).json()["meta"]
        self.assertEqual(meta["ayanamsa"], "lahiri")
        self.assertEqual(meta["house_system"], "whole_sign")
        self.assertEqual(meta["timezone"], "Asia/Kolkata")

    def test_no_client_pii_in_response(self):
        chart = self.post(BANGALORE).json()["chart"]
        self.assertNotIn("name", chart)
        self.assertNotIn("birth_place", chart)

    # ── Timezone handling ─────────────────────────────────────────────────────

    def test_timezone_resolved_from_coordinates(self):
        body = {k: v for k, v in BANGALORE.items() if k != "timezone"}
        r = self.post(body)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["meta"]["timezone"], "Asia/Kolkata")
        # Same chart as when the timezone is passed explicitly.
        self.assertEqual(r.json()["chart"], self.post(BANGALORE).json()["chart"])

    def test_unresolvable_timezone_is_an_error_not_utc(self):
        body = {k: v for k, v in BANGALORE.items() if k != "timezone"}
        class NoTimezone:
            def timezone_at(self, lat, lng):
                return None

        with patch.object(main, "_timezone_finder", return_value=NoTimezone()):
            r = self.post(body)
        self.assertEqual(r.status_code, 422)
        self.assertIn("timezone", r.text)

    def test_unknown_timezone_rejected(self):
        r = self.post({**BANGALORE, "timezone": "Mars/Olympus_Mons"})
        self.assertEqual(r.status_code, 422)

    # ── Validation ────────────────────────────────────────────────────────────

    def test_reference_date_required(self):
        body = {k: v for k, v in BANGALORE.items() if k != "reference_date"}
        self.assertEqual(self.post(body).status_code, 422)

    def test_latitude_out_of_range(self):
        self.assertEqual(self.post({**BANGALORE, "latitude": 91}).status_code, 422)

    def test_bad_time_format(self):
        self.assertEqual(self.post({**BANGALORE, "birth_time": "2:32pm"}).status_code, 422)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_missing_key_rejected(self):
        self.assertEqual(self.post(BANGALORE, headers={}).status_code, 401)

    def test_wrong_key_rejected(self):
        self.assertEqual(self.post(BANGALORE, headers={"X-API-Key": "nope"}).status_code, 401)

    def test_unconfigured_server_fails_closed(self):
        with patch.dict(os.environ, {"API_KEY": ""}):
            self.assertEqual(self.post(BANGALORE).status_code, 503)

    def test_healthz_needs_no_auth(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)


if __name__ == "__main__":
    unittest.main()
