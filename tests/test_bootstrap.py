"""Exercise host control flow with a fake OrbStack transport; never touch a real VM."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE_ORB = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args=sys.argv[1:]
mode=os.environ.get('BOOTSTRAP_TEST_MODE','ok')
with open(os.environ['BOOTSTRAP_TEST_LOG'],'a') as log:
    log.write(json.dumps(args)+'\n')
if args[0]=='status':
    print('Running'); sys.exit(0)
if args[0]=='list':
    print('hermes running ubuntu resolute arm64'); sys.exit(0)
if args[0]=='run':
    script=args[args.index('-lc')+1]
    if mode=='transport-failure' and 'key-state check' in script: sys.exit(42)
    if mode=='runtime-failure' and 'hermes --version' in script: sys.exit(43)
    if mode=='gateway-failure' and 'gateway install' in script: sys.exit(44)
    if mode=='repo-failure' and 'git clone' in script: sys.exit(45)
    if mode=='profile-failure' and 'validate_profile' in script: sys.exit(46)
    if 'key-state check' in script: print('present')
    sys.exit(0)
sys.exit(1)
'''


class BootstrapTests(unittest.TestCase):
    def run_bootstrap(self, mode='ok', repo=None, extra=None):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            orb = base / 'orb'
            orb.write_text(FAKE_ORB)
            orb.chmod(0o755)
            env = dict(os.environ, PATH=str(base) + os.pathsep + os.environ['PATH'],
                       BOOTSTRAP_TEST_MODE=mode, BOOTSTRAP_TEST_LOG=str(base / 'calls'))
            if repo:
                env['HERMES_REPO'] = repo
            result = subprocess.run(['bash', str(ROOT / 'onboarder/bootstrap.sh'), *(extra or [])],
                                    input='', text=True, capture_output=True, env=env, timeout=10)
            calls = [json.loads(line) for line in (base / 'calls').read_text().splitlines()] if (base / 'calls').exists() else []
            return result, calls

    def test_failed_prerequisites_never_report_ready_or_launch(self):
        for mode in ('runtime-failure', 'gateway-failure', 'repo-failure', 'profile-failure', 'transport-failure'):
            with self.subTest(mode=mode):
                result, calls = self.run_bootstrap(mode, extra=['--launch'])
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Runtime prerequisites verified.', result.stdout)
                self.assertFalse(any('exec hermes chat' in str(call) for call in calls))

    def test_verified_runtime_preserves_existing_key_and_waits_for_human_setup(self):
        result, calls = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Account connections and message delivery are NOT verified', result.stdout)
        self.assertNotIn('Anthropic API key:', result.stdout)
        self.assertFalse(any('exec hermes chat' in str(call) for call in calls))
        self.assertFalse(any('sys.stdin.read' in str(call) for call in calls))

    def test_remote_runtime_checks_catch_partial_installer_and_both_gateway_failures(self):
        _, calls = self.run_bootstrap()
        call = next(c for c in calls if any('gateway install' in part for part in c))
        script = call[call.index('-lc') + 1]
        # Shell functions intercept every external runtime command. The original remote
        # body runs under bash, including its pipefail, fallback, and postconditions.
        common = "python3() { return 0; }; systemctl() { echo not-found; }; "
        scenarios = [
            common + "hermes() { return 127; }; curl() { echo ':'; }; command() { if [ \"${2:-}\" = hermes ]; then return 1; fi; builtin command \"$@\"; }; ",
            common + "hermes() { if [ \"$1\" = --version ]; then return 0; fi; return 44; }; ",
        ]
        for prefix in scenarios:
            with self.subTest(prefix=prefix):
                result = subprocess.run(['bash', '-c', prefix + script], capture_output=True, text=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)

    def test_repo_url_is_passed_as_data_not_shell_code(self):
        url = 'https://example.invalid/repo?q=$(false)`false`'
        result, calls = self.run_bootstrap(repo=url)
        self.assertEqual(result.returncode, 0, result.stderr)
        clone_call = next(call for call in calls if any('git clone' in part for part in call))
        self.assertEqual(clone_call[-1], url)
        self.assertNotIn(url, clone_call[clone_call.index('-lc') + 1])

    def test_bad_argument_is_rejected_without_contacting_vm(self):
        result, calls = self.run_bootstrap(extra=['--unknown'])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
