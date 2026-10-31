"""Additional injected failures beyond the seven before/after incident tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import lab
import release
from service_core import ServiceState
import time

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'fixture';lab.initialize(self.root)
    def test_atomic_error_leaves_pointer_and_no_temporary(self):
        before=(self.root/'accepted.json').read_bytes()
        with patch('os.replace',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):release.publish(lab.read(self.root/'manifest-B.json'),lab.read(self.root/'report-B.json'),self.root/'accepted.json')
        self.assertEqual(before,(self.root/'accepted.json').read_bytes())
        self.assertEqual(list(self.root.glob('*.tmp')),[])
    def test_load_tampered_artifact_never_becomes_ready(self):
        (self.root/'model-A.txt').write_text('tampered')
        state=ServiceState(self.root)
        state.thread.join(timeout=3)
        self.assertFalse(state.ready)
        self.assertIn('Artifact changed',state.error)
    def test_runtime_change_creates_distinct_release_identity(self):
        m,r=lab.read(self.root/'manifest-B.json'),lab.read(self.root/'report-B.json')
        old=release.publish_event(m,r,self.root)
        m['runtime']['dtype']='bfloat16'
        m['runtime_sha256']=release.digest(release.canonical(m['runtime']))
        r['runtime_sha256']=m['runtime_sha256']
        new=release.publish_event(m,r,self.root)
        self.assertNotEqual(old,new)
        self.assertEqual(len((self.root/'publications.jsonl').read_text().splitlines()),2)
    def test_new_decision_creates_distinct_release_identity(self):
        m,r=lab.read(self.root/'manifest-B.json'),lab.read(self.root/'report-B.json')
        old=release.publish_event(m,r,self.root)
        r['evaluation_run_id']='another-evaluation'
        self.assertNotEqual(old,release.publish_event(m,r,self.root))
    def test_preparation_checks_real_schema_before_caching(self):
        config=lab.read(self.root/'config.json');config['data_format']='golden-jsonl'
        lab.write(self.root/'config.json',config)
        (self.root/'input.txt').write_text('{"id":"broken"}\n')
        with self.assertRaises(ValueError):lab.prepare(self.root)
