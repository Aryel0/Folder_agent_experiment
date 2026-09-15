import unittest
import shutil
from pathlib import Path
from sandbox_world.observer import WorldObserver, WorldSnapshot


class TestStandaloneObserver(unittest.TestCase):
    def setUp(self):
        self.test_ws = Path("./tmp_stand_obs").resolve()
        self.test_ws.mkdir(parents=True, exist_ok=True)
        self.observer = WorldObserver(str(self.test_ws))

    def tearDown(self):
        if self.test_ws.exists():
            shutil.rmtree(self.test_ws)

    def test_snapshot_and_delta(self):
        snap1 = WorldSnapshot(str(self.test_ws))
        (self.test_ws / "artifact.txt").write_text("content")
        snap2 = WorldSnapshot(str(self.test_ws))
        delta = snap2.diff(snap1)
        self.assertIn("artifact.txt", delta.created)

    def test_loop_detection(self):
        self.observer.record_action("bash", "pwd", "/workspace", 0.05)
        self.assertFalse(self.observer.detect_loop("pwd"))
        self.observer.record_action("bash", "pwd", "/workspace", 0.05)
        self.assertTrue(self.observer.detect_loop("pwd"))


if __name__ == "__main__":
    unittest.main()
