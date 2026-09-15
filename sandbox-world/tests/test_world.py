import unittest
import shutil
from pathlib import Path
from sandbox_world.world import ScenarioManager, BrokenPipelineScenario, WorldObserver


class TestStandaloneWorld(unittest.TestCase):
    def setUp(self):
        self.test_ws = Path("./tmp_stand_world").resolve()
        self.test_ws.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_ws.exists():
            shutil.rmtree(self.test_ws)

    def test_manager_scenarios(self):
        mgr = ScenarioManager()
        self.assertEqual(len(mgr.list_scenarios()), 3)
        sc = mgr.get("broken_pipeline")
        self.assertIsNotNone(sc)

    def test_broken_pipeline_setup(self):
        sc = BrokenPipelineScenario()
        sc.setup(str(self.test_ws))
        self.assertTrue((self.test_ws / "raw_telemetry.csv").exists())
        self.assertTrue((self.test_ws / "data_pipeline.py").exists())


if __name__ == "__main__":
    unittest.main()
