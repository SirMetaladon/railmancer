"""Path settings: env override, local file, then Isaiah's defaults."""

import json
import os
import tempfile
import unittest

from railmancer import settings


class SettingsTests(unittest.TestCase):

    def setUp(self):

        self._saved_env = {name: os.environ.get(name) for name in settings.ENV.values()}
        self._saved_local = settings.LOCAL_PATH
        for name in settings.ENV.values():
            os.environ.pop(name, None)
        # Point the local file at a path that does not exist.
        settings.LOCAL_PATH = os.path.join(
            tempfile.gettempdir(), "no-such-railmancer-settings.json"
        )

    def tearDown(self):

        settings.LOCAL_PATH = self._saved_local
        for name, value in self._saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_example_file_matches_the_builtin_defaults(self):

        example = os.path.join(
            os.path.dirname(settings.__file__), "settings.example.json"
        )
        with open(example, encoding="utf-8") as handle:
            loaded = json.load(handle)
        self.assertEqual(loaded, settings.DEFAULTS)

    def test_missing_file_uses_his_paths(self):

        self.assertEqual(
            settings.get("vmf_output_dir"),
            "C:/Users/Metaladon/Desktop/Model Data/VMFS/railmancer",
        )
        self.assertTrue(settings.get("track_library").endswith("trakpak3_rsg"))
        self.assertEqual(settings.get("vmf_input"), "vmf inputs/gm_cascadia.vmf")

    def test_local_file_then_env(self):

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.local.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"vmf_output_dir": "/from/file"}, handle)
            settings.LOCAL_PATH = path
            self.assertEqual(settings.get("vmf_output_dir"), "/from/file")
            # A key the file does not set still falls back.
            self.assertEqual(settings.get("vmf_input"), "vmf inputs/gm_cascadia.vmf")
            os.environ["RAILMANCER_VMF_OUTPUT_DIR"] = "/from/env"
            self.assertEqual(settings.get("vmf_output_dir"), "/from/env")
