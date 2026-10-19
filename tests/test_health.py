from datetime import datetime, timezone
import subprocess
import unittest
from test_sync import Fixture
import health_engine as health


class HealthTests(Fixture):
    def setUp(self):
        super().setUp()
        self.write('.env', 'ANTHROPIC_API_KEY=placeholder\nSIGNAL_ACCOUNT=placeholder\nSIGNAL_HTTP_URL=placeholder\nSIGNAL_ALLOWED_USERS=placeholder\nSIGNAL_HOME_CHANNEL=placeholder\n')
        (self.home / '.env').chmod(0o600)

    def check(self, **kwargs):
        runner = kwargs.pop('runner', lambda args: subprocess.CompletedProcess(args, 0, '', ''))
        return health.health(self.root, self.home, runner=runner,
                             now=datetime(2026, 9, 8, 12, tzinfo=timezone.utc), mountinfo=kwargs.pop('mountinfo', ''), **kwargs)

    def test_services_and_failed_or_overdue_jobs_report_failure_without_content(self):
        self.enable()
        self.job(last_status='error', last_error='private email', next_run_at='2026-09-08T08:00:00+00:00')
        before = self.snapshot()
        results = self.check(runner=lambda args: subprocess.CompletedProcess(args, 1, '', 'private stderr'))
        self.assertTrue(any(level == 'FAIL' and label == 'hermes-gateway' for level, label, _ in results))
        self.assertTrue(any('overdue' in detail for _, _, detail in results))
        self.assertNotIn('private email', str(results))
        self.assertNotIn('private stderr', str(results))
        self.assertEqual(before, self.snapshot())

    def test_delivery_failure_and_never_run_are_distinct(self):
        self.enable()
        self.job(last_status='ok', last_delivery_error='private address', next_run_at='2026-09-09T08:00:00+00:00')
        self.assertTrue(any(level == 'FAIL' and label == 'morning-brief' for level, label, _ in self.check()))
        self.job(next_run_at='2026-09-09T08:00:00+00:00')
        self.assertTrue(any(level == 'WARN' and label == 'morning-brief' for level, label, _ in self.check()))

    def test_host_share_warning_and_strict_failure(self):
        mounts = '50 1 0:50 / /Users rw - virtiofs host rw\n51 1 0:50 / /elsewhere rw - virtiofs host rw'
        self.assertEqual(len(health.host_shares(mounts)), 2)
        for strict, expected in ((False, 'WARN'), (True, 'FAIL')):
            results = self.check(require_isolation=strict, mountinfo=mounts)
            self.assertTrue(any(level == expected and label == 'host filesystem sharing' for level, label, _ in results))

    def test_probe_is_opt_in_and_never_invokes_account_tools(self):
        self.enable()
        calls = []
        def runner(args):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, 'Connected (10ms)\nTools discovered: 2\nprivate output', '')
        self.check(runner=runner)
        self.assertFalse(any('mcp' in c for c in calls))
        results = self.check(runner=runner, probe=True)
        self.assertIn(['hermes', 'mcp', 'test', 'gmail'], calls)
        self.assertNotIn('private output', str(results))

    def test_zero_exit_without_discovery_evidence_is_failure(self):
        self.enable()
        results = self.check(probe=True, runner=lambda args: subprocess.CompletedProcess(args, 0, 'Connection failed', ''))
        self.assertTrue(any(level == 'FAIL' and label == 'gmail' for level, label, _ in results))

    def test_invalid_profile_is_failure(self):
        self.write('sidekick/profile.yaml', '[]')
        self.assertEqual(self.check()[0][0], 'FAIL')

    def test_missing_registration_and_insecure_env_permissions_fail(self):
        self.enable()
        self.config['mcp_servers'].pop('gmail')
        self.save_config()
        (self.home / '.env').chmod(0o644)
        failures = {label for level, label, _ in self.check() if level == 'FAIL'}
        self.assertIn('gmail', failures)
        self.assertIn('secrets permissions', failures)


if __name__ == '__main__':
    unittest.main()
