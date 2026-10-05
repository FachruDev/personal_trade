from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest


FREQTRADE_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = FREQTRADE_ROOT / "scripts" / "validate_live_release.py"
LIVE_TEMPLATE = FREQTRADE_ROOT / "config" / "profiles" / "live.template.json"
sys.path.insert(0, str(VALIDATOR.parent))
import validate_live_release as validator


class LiveReleaseValidatorTests(unittest.TestCase):
    def approval_record(self, report_hash: str = "a" * 64, strategy_hash: str = "a" * 64) -> dict:
        return {
            "acknowledgement": "LIMITED_LIVE_APPROVED",
            "approved_at": "2026-10-05T00:00:00Z",
            "owner": "approved-owner",
            "strategy_revision": "immutable-revision",
            "strategy_source_sha256": strategy_hash,
            "quant_report_sha256": report_hash,
            "paper_run_end": "2026-10-05T00:00:00Z",
        }

    def profile(self) -> dict:
        return json.loads(LIVE_TEMPLATE.read_text(encoding="utf-8"))

    def passed_report(self) -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
        directory = tempfile.TemporaryDirectory()
        report_path = Path(directory.name) / "quant-report.json"
        report_path.write_text(json.dumps({"passes": True}), encoding="utf-8")
        return directory, report_path, hashlib.sha256(report_path.read_bytes()).hexdigest()

    def strategy_source(self, directory: Path) -> tuple[Path, str]:
        source_path = directory / "FrozenStrategy.py"
        source_path.write_text("class FrozenStrategy: pass\n", encoding="utf-8")
        return source_path, hashlib.sha256(source_path.read_bytes()).hexdigest()

    def test_valid_profile_and_approval_are_accepted(self) -> None:
        directory, report_path, report_hash = self.passed_report()
        with directory:
            strategy_path, strategy_hash = self.strategy_source(Path(directory.name))
            errors = validator.validation_errors(self.profile(), self.approval_record(report_hash, strategy_hash), report_path, strategy_path, clock_drift_fetcher=lambda: 0.1)
            self.assertEqual(errors, [])

    def test_missing_approval_acknowledgement_is_rejected(self) -> None:
        directory, report_path, report_hash = self.passed_report()
        with directory:
            strategy_path, strategy_hash = self.strategy_source(Path(directory.name))
            approval = self.approval_record(report_hash, strategy_hash)
            approval["acknowledgement"] = ""
            errors = validator.validation_errors(self.profile(), approval, report_path, strategy_path, clock_drift_fetcher=lambda: 0.1)
            self.assertTrue(any("acknowledgement" in error for error in errors))

    def test_clock_drift_and_clock_fetch_failure_reject_release(self) -> None:
        directory, report_path, report_hash = self.passed_report()
        with directory:
            strategy_path, strategy_hash = self.strategy_source(Path(directory.name))
            approval = self.approval_record(report_hash, strategy_hash)
            drift_errors = validator.validation_errors(self.profile(), approval, report_path, strategy_path, clock_drift_fetcher=lambda: 2.01)
            self.assertTrue(any("clock drift" in error for error in drift_errors))

            unavailable_errors = validator.validation_errors(
                self.profile(), approval, report_path, strategy_path, clock_drift_fetcher=lambda: (_ for _ in ()).throw(ValueError("offline"))
            )
            self.assertTrue(any("could not verify Binance server time" in error for error in unavailable_errors))

    def test_failed_or_mismatched_quant_report_rejects_release(self) -> None:
        directory, report_path, report_hash = self.passed_report()
        with directory:
            strategy_path, strategy_hash = self.strategy_source(Path(directory.name))
            mismatched = validator.validation_errors(self.profile(), self.approval_record("b" * 64, strategy_hash), report_path, strategy_path, clock_drift_fetcher=lambda: 0.1)
            self.assertTrue(any("SHA-256" in error for error in mismatched))

            report_path.write_text(json.dumps({"passes": False}), encoding="utf-8")
            failed = validator.validation_errors(self.profile(), self.approval_record(report_hash, strategy_hash), report_path, strategy_path, clock_drift_fetcher=lambda: 0.1)
            self.assertTrue(any("does not pass" in error for error in failed))

    def test_changed_strategy_source_rejects_release(self) -> None:
        directory, report_path, report_hash = self.passed_report()
        with directory:
            strategy_path, strategy_hash = self.strategy_source(Path(directory.name))
            strategy_path.write_text("class FrozenStrategy: changed = True\n", encoding="utf-8")
            errors = validator.validation_errors(self.profile(), self.approval_record(report_hash, strategy_hash), report_path, strategy_path, clock_drift_fetcher=lambda: 0.1)
            self.assertTrue(any("strategy source SHA-256" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
