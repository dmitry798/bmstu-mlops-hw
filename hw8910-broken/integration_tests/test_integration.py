"""Real subprocess/filesystem/HTTP tests; also run unchanged against original commit."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

PROJECT = Path(os.environ.get('PROJECT_UNDER_TEST', Path(__file__).resolve().parents[1]))

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'workspace'
        self.command('init')

    def command(self, *args):
        return subprocess.run([sys.executable, str(PROJECT/'lab.py'), '--workspace', str(self.root), *args], capture_output=True, text=True)

    def read(self, name):
        return json.loads((self.root/name).read_text())

    def test_process_recovery_and_changed_input(self):
        failed = self.command('run', '--fail-after-prepare')
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('PREPARED', failed.stdout)
        recovered = self.command('run')
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertIn('CACHE_HIT', recovered.stdout)
        (self.root/'input.txt').write_text('Changed input at same path\n')
        changed = self.command('run')
        self.assertIn('PREPARED', changed.stdout)

    def test_process_incomplete_foreign_and_rejected_reports(self):
        before = (self.root/'accepted.json').read_bytes()
        for report in ['report-incomplete.json', 'report-A.json', 'report-reject.json']:
            with self.subTest(report=report):
                result = self.command('run', '--report', report)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(before, (self.root/'accepted.json').read_bytes())

    def test_process_repeat_has_one_event(self):
        for _ in range(2):
            result = self.command('run')
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len((self.root/'publications.jsonl').read_text().splitlines()), 1)

    def start_service(self, warmup=0):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        extra = ['--framework', 'fastapi'] if os.environ.get('SERVICE_FRAMEWORK') == 'fastapi' else []
        proc = subprocess.Popen([sys.executable, str(PROJECT/'service.py'), '--workspace', str(self.root), '--port', str(port), '--warmup-seconds', str(warmup), *extra], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        def stop():
            if proc.poll() is None: proc.terminate()
            proc.communicate(timeout=15)
        self.addCleanup(stop)
        self.url = f'http://127.0.0.1:{port}'
        for _ in range(200):
            if proc.poll() is not None: self.fail(proc.stdout.read())
            try:
                self.http('/health'); return proc
            except OSError: time.sleep(.05)
        self.fail('HTTP startup timed out')

    def http(self, path, payload=None):
        req = Request(self.url+path, data=None if payload is None else json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        try:
            with urlopen(req, timeout=10) as response: return response.status, json.load(response)
        except HTTPError as error: return error.code, json.load(error)

    def await_ready(self):
        for _ in range(200):
            if self.http('/ready')[0] == 200: return
            time.sleep(.05)
        self.fail('warmup timed out')

    def test_http_readiness_gates_generation(self):
        self.start_service(2)
        self.assertEqual(self.http('/health')[0], 200)
        self.assertEqual(self.http('/ready')[0], 503)
        calls = self.http('/debug')[1]['calls']
        self.assertEqual(self.http('/generate', {'prompt':'hello'})[0], 503)
        self.assertEqual(self.http('/debug')[1]['calls'], calls)
        self.await_ready()
        self.assertEqual(self.http('/generate', {'prompt':'hello'})[0], 200)

    def test_http_loaded_version_restart_and_rollback(self):
        proc = self.start_service(); self.await_ready()
        self.assertEqual(self.http('/generate', {'prompt':'hello'})[1]['model_id'], 'fixture-A')
        self.assertEqual(self.command('run').returncode, 0)
        answer = self.http('/generate', {'prompt':'hello'})[1]
        self.assertEqual(answer['model_id'], 'fixture-A')
        self.assertIn('fixture-A', answer['answer'])
        proc.terminate(); proc.wait(timeout=10)
        proc = self.start_service(); self.await_ready()
        self.assertEqual(self.http('/generate', {'prompt':'hello'})[1]['model_id'], 'fixture-B')
        # Restore a previously accepted manifest through the same validated publication API.
        result = subprocess.run([sys.executable, '-c', 'import lab,release;from pathlib import Path; r=Path(__import__("sys").argv[1]);release.publish(lab.read(r/"manifest-A.json"),lab.read(r/"report-A.json"),r/"accepted.json")', str(self.root)], cwd=PROJECT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        proc.terminate(); proc.wait(timeout=10)
        self.start_service(); self.await_ready()
        self.assertEqual(self.http('/generate', {'prompt':'hello'})[1]['model_id'], 'fixture-A')

    def test_http_invalid_request_never_calls_backend(self):
        self.start_service(); self.await_ready()
        calls = self.http('/debug')[1]['calls']
        for payload in [{'prompt':''}, {'prompt':'x','max_new_tokens':0}, {'prompt':'x','max_new_tokens':100000}, {'prompt':'x','max_new_tokens':'2'}, {'prompt':'x','max_new_tokens':True}, {'prompt':'x'*9000}]:
            with self.subTest(payload=str(payload)[:80]):
                status, _ = self.http('/generate', payload)
                self.assertTrue(400 <= status < 500, status)
                self.assertEqual(self.http('/debug')[1]['calls'], calls)
        self.assertEqual(self.http('/generate', {'prompt':'hello','max_new_tokens':32})[0], 200)
        self.assertEqual(self.http('/debug')[1]['calls'], calls+1)

    def test_process_artifact_tampering_blocks_publication(self):
        before = (self.root/'accepted.json').read_bytes()
        (self.root/'model-B.txt').write_text('tampered')
        self.assertNotEqual(self.command('run').returncode, 0)
        self.assertEqual((self.root/'accepted.json').read_bytes(), before)

    def test_process_pointer_crash_recovered_without_duplicate(self):
        result = self.command('run', '--fail-after-pointer')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.read('accepted.json')['model_id'], 'fixture-B')
        for _ in range(2):
            recovered = self.command('run')
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
        events = (self.root/'publications.jsonl').read_text().splitlines()
        self.assertEqual(len(events), 1)
        self.assertEqual(self.read('pending.json')['completed'], True)
