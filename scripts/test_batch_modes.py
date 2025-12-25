import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from autoaudit.batch_runner import BatchRunner
from autoaudit.models import TraceStep
from autoaudit.worker import FetchResult

class TestBatchRunnerModes(unittest.TestCase):
    def setUp(self):
        self.mock_rulepack = Path("mock_rulepack")
        self.mock_rulepack.mkdir(exist_ok=True)
        (self.mock_rulepack / "rules.json").write_text("[]", encoding="utf-8")
        (self.mock_rulepack / "rulepack.json").write_text('{"rule_pack_id": "test", "version": "v1"}', encoding="utf-8")

    def tearDown(self):
        import shutil
        if self.mock_rulepack.exists():
            shutil.rmtree(self.mock_rulepack)

    @patch("autoaudit.batch_runner.BrowserWorker")
    @patch("autoaudit.batch_runner.RuleEngine")
    def test_run_modes(self, MockRuleEngine, MockWorker):
        # Setup RuleEngine mock
        mock_engine_instance = MockRuleEngine.return_value
        mock_engine_instance.evaluate.return_value = []

        # Setup Worker mock
        mock_worker_instance = MockWorker.return_value
        mock_worker_instance.save_trace.return_value = "trace.json"

        modes = ["entry_only", "content_only", "mixed"]
        
        for mode in modes:
            with self.subTest(mode=mode):
                # Prepare mock results based on mode
                entry_res = []
                content_res = []
                
                if mode == "entry_only" or mode == "mixed":
                    entry_res = [FetchResult("http://entry", 200, "entry body", 0.1, "s.png", "s.html")]
                
                if mode == "content_only" or mode == "mixed":
                    content_res = [FetchResult("http://content", 200, "content body", 0.1, "s.png", "s.html")]

                mock_worker_instance.run_site.return_value = (entry_res, content_res)

                # Run Batch
                runner = BatchRunner(self.mock_rulepack, [{"site_id": "s1"}])
                result = runner._run_site({"site_id": "s1"})

                # Verify RuleEngine called with correct pages
                # The critical check: pages_payload should contain BOTH if mixed, or just one if single mode
                self.assertTrue(MockRuleEngine.called)
                args, _ = mock_engine_instance.evaluate.call_args
                pages_payload = args[0]
                
                expected_count = 0
                if mode == "entry_only": expected_count = 1
                elif mode == "content_only": expected_count = 1
                elif mode == "mixed": expected_count = 2
                
                self.assertEqual(len(pages_payload), expected_count, f"Failed for mode {mode}")
                
                # Reset mocks for next subtest
                MockRuleEngine.reset_mock()
                mock_worker_instance.reset_mock()
                mock_engine_instance.reset_mock()

if __name__ == "__main__":
    unittest.main()
