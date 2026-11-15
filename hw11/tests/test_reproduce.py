import importlib.util
from pathlib import Path
import unittest,uuid
class ReproductionTests(unittest.TestCase):
 def module(self):
  path=Path(__file__).resolve().parents[1]/'scripts/run_all.py';spec=importlib.util.spec_from_file_location('run_all',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
 def test_existing_results_are_never_reused_or_overwritten(self):
  module=self.module();root=Path('/tmp')/('hw11-reproduction-'+str(uuid.uuid4()));root.mkdir();module.require_empty_results(root);(root/'old-evidence.json').write_text('keep')
  with self.assertRaises(RuntimeError):module.require_empty_results(root)
  self.assertEqual((root/'old-evidence.json').read_text(),'keep')
 def test_complete_pipeline_collects_all_audit_dependencies(self):
  stages=self.module().STAGES
  for name in ['experiment_a.py','recheck_a.py','kubernetes_checks.py','experiments.py B','experiment_c.py','fetch_metrics.py','network_analysis.py','hot_analysis.py','warmup_analysis.py','hpa_analysis.py','analyze.py','check_monitoring.py','audit.py','resources.sh','report.py']:
   self.assertIn(name,stages)
