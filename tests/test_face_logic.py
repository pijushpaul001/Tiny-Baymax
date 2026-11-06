import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FaceLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if cls.node is None:
            raise unittest.SkipTest("Node.js is not installed")

    def test_face_parameters(self):
        source = r"""
const assert = require("node:assert/strict");
const { faceParams } = require(process.argv[1]);
const { pickVoice } = require(process.argv[2]);
const baseline = faceParams({ concern: 0.10, happiness: 0.50 }, false);
assert.deepEqual(baseline, { eyeScaleX: 1.0, eyeScaleY: 1.0, blinkIntervalMs: 5000, blinkDurationMs: 160, blinkEnabled: true });
const concernMid = faceParams({ concern: 0.35, happiness: 0.5 }, false);
assert.ok(Math.abs(concernMid.eyeScaleX - 1.075) < 1e-12);
assert.ok(Math.abs(concernMid.eyeScaleY - 1.20) < 1e-12);
assert.equal(concernMid.blinkIntervalMs, 7000);
const concernMax = faceParams({ concern: 0.6, happiness: 0.5 }, false);
assert.equal(concernMax.eyeScaleX, 1.15);
assert.equal(concernMax.eyeScaleY, 1.40);
assert.equal(faceParams({ concern: 0.9, happiness: 0.5 }, false).eyeScaleY, 1.40);
assert.equal(concernMax.blinkIntervalMs, 9000);
const happyMid = faceParams({ concern: 0.1, happiness: 0.7 }, false);
assert.ok(Math.abs(happyMid.eyeScaleX - 1.0666666666666667) < 1e-12);
assert.ok(Math.abs(happyMid.eyeScaleY - 0.7666666666666667) < 1e-12);
assert.equal(happyMid.blinkIntervalMs, 4000);
assert.equal(happyMid.blinkDurationMs, 200);
const happyMax = faceParams({ concern: 0.1, happiness: 0.8 }, false);
assert.equal(happyMax.eyeScaleX, 1.10);
assert.equal(happyMax.eyeScaleY, 0.65);
assert.equal(faceParams({ concern: 100, happiness: -5 }, false).eyeScaleX, 1.15);
assert.equal(faceParams({ concern: 100, happiness: -5 }, false).eyeScaleY, 1.40);
assert.equal(faceParams({ concern: -5, happiness: 100 }, false).eyeScaleX, 1.10);
assert.equal(faceParams({ concern: -5, happiness: 100 }, false).eyeScaleY, 0.65);
assert.equal(faceParams({ concern: 0.1, happiness: 100 }, false).blinkIntervalMs, 3500);
assert.equal(faceParams({ concern: "bad", happiness: NaN }, false).eyeScaleX, 1.0);
assert.equal(faceParams({ concern: Infinity, happiness: -Infinity }, false).blinkIntervalMs, 5000);
assert.deepEqual(faceParams({ concern: "bad", happiness: null }, false), baseline);
assert.equal(faceParams(undefined, false).blinkIntervalMs, 5000);
assert.equal(faceParams({}, true).blinkEnabled, false);
const voices = [
  { name: "English remote", lang: "en-US", localService: false },
  { name: "English local", lang: "en-US", localService: true },
  { name: "Hindi local", lang: "hi-IN", localService: true },
  { name: "British local", lang: "en-GB", localService: true }
];
assert.equal(pickVoice(voices, "hi-IN").name, "Hindi local");
assert.equal(pickVoice(voices, "fr-FR").name, "English local");
assert.equal(pickVoice(voices, "en-US").name, "English local");
assert.equal(pickVoice([{ name: "English remote", lang: "en-US", localService: false }], "fr").name, "English remote");
assert.equal(pickVoice([{ name: "Hindi", lang: "hi-IN" }], "fr-FR"), null);
assert.equal(pickVoice([], "en-US"), null);
"""
        result = subprocess.run(
            [self.node, "-e", source, str(ROOT / "web" / "face.js"), str(ROOT / "web" / "speech.js")],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
