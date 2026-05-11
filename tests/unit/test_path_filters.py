import unittest

from nexus_core.path_filters import is_runtime_noise_path


class PathFilterTests(unittest.TestCase):
    def test_runtime_noise_paths_are_ignored(self):
        noisy_paths = [
            "/repo/data/zeus_memory.db",
            "/repo/nexus_events.db-journal",
            "/repo/nexus_core.log",
            "/repo/logs/watcher.log",
            "/repo/.venv/lib/site.py",
            "/repo/target/release/watcher_rs",
            "/repo/data/vector_memory.json.tmp",
            "/repo/models/piper/pt_BR_maria_low.onnx",
        ]

        for path in noisy_paths:
            with self.subTest(path=path):
                self.assertTrue(is_runtime_noise_path(path))

    def test_source_paths_are_not_ignored(self):
        source_paths = [
            "/repo/apps/web_gui.py",
            "/repo/nexus_core/events/watcher.py",
            "/repo/README.md",
            "/repo/public/index.html",
        ]

        for path in source_paths:
            with self.subTest(path=path):
                self.assertFalse(is_runtime_noise_path(path))


if __name__ == "__main__":
    unittest.main()
