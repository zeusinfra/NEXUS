import unittest

from zeus_core.rust_sensors import RUST_SENSORS_AVAILABLE, get_os_snapshot


class RustSensorsTests(unittest.TestCase):
    @unittest.skipUnless(RUST_SENSORS_AVAILABLE, "zeus_sensors Rust extension is not installed")
    def test_rust_os_snapshot_shape(self):
        snapshot = get_os_snapshot()

        self.assertIsInstance(snapshot, dict)
        self.assertIn("cpu_per_core", snapshot)
        self.assertIn("cpu_avg", snapshot)
        self.assertIn("ram", snapshot)
        self.assertIn("disk", snapshot)
        self.assertIn("top_processes", snapshot)
        self.assertIn("pressure", snapshot)
        self.assertIsInstance(snapshot["top_processes"], list)
        self.assertIn(snapshot["pressure"], {"calm", "stable", "active", "critical"})


if __name__ == "__main__":
    unittest.main()
