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
const { faceParams, reactionFor } = require(process.argv[1]);
const { pickVoice } = require(process.argv[2]);
function near(actual, expected, eps = 1e-9) {
  assert.ok(Math.abs(actual - expected) < eps, `expected ${actual} to be within ${eps} of ${expected}`);
}
const baseline = faceParams({ concern: 0.10, happiness: 0.50 }, false);
near(baseline.eyeScaleX, 1.0);
near(baseline.eyeScaleY, 1.0);
near(baseline.blinkIntervalMs, 5000);
near(baseline.blinkDurationMs, 160);
near(baseline.smileDepth, 1.5);
near(baseline.eyeTiltDeg, 0);
assert.equal(baseline.blinkEnabled, true);
const concernMid = faceParams({ concern: 0.35, happiness: 0.5 }, false);
near(concernMid.eyeScaleX, 1.075);
near(concernMid.eyeScaleY, 1.20);
near(concernMid.blinkIntervalMs, 7000);
const concernMax = faceParams({ concern: 0.6, happiness: 0.5 }, false);
assert.equal(concernMax.eyeScaleX, 1.15);
assert.equal(concernMax.eyeScaleY, 1.40);
assert.equal(faceParams({ concern: 0.9, happiness: 0.5 }, false).eyeScaleY, 1.40);
near(concernMax.blinkIntervalMs, 9000);
near(concernMid.smileDepth, 0);
assert.equal(concernMax.smileDepth, 0);
const happyMid = faceParams({ concern: 0.1, happiness: 0.7 }, false);
near(happyMid.eyeScaleX, 1.0666666666666667);
near(happyMid.eyeScaleY, 0.7666666666666667);
near(happyMid.blinkIntervalMs, 4000);
near(happyMid.blinkDurationMs, 200);
near(happyMid.smileDepth, 3.5);
const happyMax = faceParams({ concern: 0.1, happiness: 0.8 }, false);
assert.equal(happyMax.eyeScaleX, 1.10);
assert.equal(happyMax.eyeScaleY, 0.65);
assert.equal(happyMax.smileDepth, 4.5);
assert.equal(faceParams({ concern: 0.1, happiness: 0.9 }, false).smileDepth, 4.5);
assert.equal(faceParams({ concern: 100, happiness: -5 }, false).eyeScaleX, 1.15);
assert.equal(faceParams({ concern: 100, happiness: -5 }, false).eyeScaleY, 1.40);
assert.equal(faceParams({ concern: -5, happiness: 100 }, false).eyeScaleX, 1.10);
assert.equal(faceParams({ concern: -5, happiness: 100 }, false).eyeScaleY, 0.65);
near(faceParams({ concern: 0.1, happiness: 100 }, false).blinkIntervalMs, 3500);
near(faceParams({ concern: "bad", happiness: NaN }, false).eyeScaleX, 1.0);
near(faceParams({ concern: Infinity, happiness: -Infinity }, false).blinkIntervalMs, 5000);
assert.deepEqual(faceParams({ concern: "bad", happiness: null }, false), baseline);
near(faceParams({ concern: "garbage", happiness: "garbage" }, false).smileDepth, 1.5);
near(faceParams(undefined, false).blinkIntervalMs, 5000);
assert.equal(faceParams({}, true).blinkEnabled, false);

assert.equal(baseline.eyeTiltDeg, 0);
near(concernMid.eyeTiltDeg, 4);
assert.equal(concernMax.eyeTiltDeg, 8);
assert.equal(faceParams({ concern: 0.8, happiness: 0.5 }, false).eyeTiltDeg, 8);
assert.equal(faceParams({ concern: 0.1, happiness: 0.9 }, false).eyeTiltDeg, 0);
near(faceParams({ concern: "bad", happiness: "bad" }, false).eyeTiltDeg, 0);
near(faceParams(null, false).eyeTiltDeg, 0);

const reactionCases = [
  ["celebrate chat below threshold", { kind: "chat", emotion: { concern: 0.29 }, mode: "celebrate" }, "hop"],
  ["playful chat below threshold", { kind: "chat", emotion: { concern: 0.29 }, mode: "playful" }, "wink"],
  ["concern exactly 0.30", { kind: "chat", emotion: { concern: 0.30 }, mode: "celebrate" }, null],
  ["concern 0.40", { kind: "chat", emotion: { concern: 0.40 }, mode: "playful" }, null],
  ["safety", { kind: "safety", emotion: { concern: 0.1 }, mode: "celebrate" }, null],
  ["ritual", { kind: "ritual", emotion: { concern: 0.1 }, mode: "playful" }, null],
  ["command", { kind: "command", emotion: { concern: 0.1 }, mode: "celebrate" }, null],
  ["error", { kind: "error", emotion: { concern: 0.1 }, mode: "playful" }, null],
  ["null mode", { kind: "chat", emotion: { concern: 0.1 }, mode: null }, null],
  ["missing emotion", { kind: "chat", mode: "celebrate" }, null],
  ["string concern", { kind: "chat", emotion: { concern: "0.1" }, mode: "celebrate" }, null],
  ["missing result", undefined, null],
  ["null result", null, null],
  ["malformed result", "chat", null]
];
for (const [name, result, expected] of reactionCases) {
  assert.equal(reactionFor(result), expected, name);
}

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
