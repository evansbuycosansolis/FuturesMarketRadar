from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.automation_service import ensure_utc as automation_ensure_utc
from app.services.exit_automation_service import ensure_utc as exit_automation_ensure_utc
from app.services.risk_service import ensure_utc as risk_ensure_utc


class DateTimeNormalizationTest(unittest.TestCase):
    def test_risk_service_normalizes_naive_datetime_to_utc(self) -> None:
        value = risk_ensure_utc(datetime(2026, 6, 20, 22, 30, 0))

        self.assertIsNotNone(value)
        assert value is not None
        self.assertEqual(value.tzinfo, timezone.utc)

    def test_automation_service_normalizes_aware_datetime_to_utc(self) -> None:
        value = automation_ensure_utc(datetime(2026, 6, 20, 18, 30, 0, tzinfo=timezone.utc))

        self.assertIsNotNone(value)
        assert value is not None
        self.assertEqual(value.tzinfo, timezone.utc)

    def test_exit_automation_service_normalizes_naive_datetime_to_utc(self) -> None:
        value = exit_automation_ensure_utc(datetime(2026, 6, 20, 22, 30, 0))

        self.assertIsNotNone(value)
        assert value is not None
        self.assertEqual(value.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
