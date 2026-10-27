// Contract tests of conversation-loop, Seam 1: createSilenceDetector of conversation.js (slice tester).
// Written from the contract, not the code. Frames come every 50 ms, as the page's interval gives them.
// Edges the contract leaves open (is the frame at exactly calibrateMs still calibration; is startMs measured
// from the first loud frame or as frames × 50 ms) are avoided: every expectation holds under both readings.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { createSilenceDetector } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

// frames of one level from `from` to `to` inclusive, every 50 ms
function seq(level, from, to) {
  const out = [];
  for (let t = from; t <= to; t += 50) out.push([level, t]);
  return out;
}

// push every frame; the events, each with the t of the frame that returned it
function feed(det, frames) {
  const events = [];
  for (const [level, t] of frames) {
    const e = det.push(level, t);
    if (e != null) events.push({ ...e, firedAt: t });
  }
  return events;
}

const types = (events) => events.map((e) => e.type);

test("speech 200 ms then 1600 ms of quiet: speech-end with at = the last speech frame", () => {
  const det = createSilenceDetector();
  const events = feed(det, [...seq(0.005, 0, 450), ...seq(0.3, 500, 700), ...seq(0.005, 750, 2600)]);
  assert.deepEqual(types(events), ["speech-start", "speech-end"]);
  assert.ok(events[0].firedAt >= 500 && events[0].firedAt <= 700, `speech-start at ${events[0].firedAt}`);
  assert.equal(events[1].at, 700, "at is the t of the last frame with speech");
  assert.ok(events[1].firedAt >= 2300, `speech-end fired too early, at frame ${events[1].firedAt}`);
  assert.ok(events[1].firedAt <= 2400, `speech-end fired too late, at frame ${events[1].firedAt}`);
});

test("a click of 100 ms gives no event", () => {
  const det = createSilenceDetector();
  const events = feed(det, [...seq(0.005, 0, 950), ...seq(0.3, 1000, 1050), ...seq(0.005, 1100, 4000)]);
  assert.deepEqual(types(events), []);
});

test("steady car noise from the first frame after reset is calibrated away; speech on top starts and ends", () => {
  const det = createSilenceDetector();
  det.reset();
  const events = feed(det, [...seq(0.05, 0, 2000), ...seq(0.3, 2050, 2400), ...seq(0.05, 2450, 4500)]);
  assert.deepEqual(types(events), ["speech-start", "speech-end"]);
  assert.ok(events[0].firedAt >= 2050, `speech-start came on the noise, at ${events[0].firedAt}`);
  assert.equal(events[1].at, 2400);
});

test("speech 200 ms after reset (inside calibration, noise 0.01): none inside, then speech-start", () => {
  const det = createSilenceDetector();
  feed(det, seq(0.01, 0, 5000));
  det.reset();
  const inside = feed(det, [...seq(0.01, 10000, 10150), ...seq(0.3, 10200, 10250)]);
  assert.deepEqual(types(inside), [], "an event inside the first calibrateMs");
  const after = feed(det, seq(0.3, 10300, 10700));
  assert.deepEqual(types(after), ["speech-start"]);
});

test("a pause of 1000 ms in the middle of speech is not the end", () => {
  const det = createSilenceDetector();
  const events = feed(det, [
    ...seq(0.005, 0, 450),
    ...seq(0.3, 500, 1000),
    ...seq(0.005, 1050, 2000),
    ...seq(0.3, 2050, 2500),
    ...seq(0.005, 2550, 5000),
  ]);
  assert.deepEqual(types(events), ["speech-start", "speech-end"]);
  assert.equal(events[1].at, 2500);
});

test("sound without a break longer than maxMs (default 870000) gives speech-end with at = t", () => {
  const det = createSilenceDetector();
  det.reset();
  const events = feed(det, [...seq(0.005, 0, 250), ...seq(0.3, 300, 870150)]);
  const ends = events.filter((e) => e.type === "speech-end");
  assert.equal(events[0].type, "speech-start");
  assert.ok(ends.length >= 1, "no speech-end after maxMs of continuous sound");
  const end = ends[0];
  assert.ok(end.firedAt >= 870000, `speech-end before maxMs, at frame ${end.firedAt}`);
  assert.ok(end.firedAt <= 870050, `speech-end late, at frame ${end.firedAt}`);
  assert.equal(end.at, end.firedAt, "at is t of the frame where maxMs ran out");
});

test("calibration takes the minimum, not the mean: a person speaking at once does not raise the threshold", () => {
  const det = createSilenceDetector();
  // calibration: loud speech with one quiet frame (min 0.01, mean about 0.17)
  const cal = feed(det, [
    [0.2, 0],
    [0.2, 50],
    [0.01, 100],
    [0.2, 150],
    [0.2, 200],
    [0.2, 250],
  ]);
  assert.deepEqual(types(cal), []);
  const events = feed(det, [...seq(0.1, 300, 800), ...seq(0.01, 850, 3000)]);
  assert.deepEqual(types(events), ["speech-start", "speech-end"]);
});

test("the threshold is max(startLevel, 3 × noise level)", () => {
  // quiet room 0.001: the threshold is startLevel 0.02
  const a = createSilenceDetector();
  assert.deepEqual(types(feed(a, [...seq(0.001, 0, 250), ...seq(0.018, 300, 2300)])), [], "0.018 < 0.02 started");
  const b = createSilenceDetector();
  assert.deepEqual(types(feed(b, [...seq(0.001, 0, 250), ...seq(0.025, 300, 700)])), ["speech-start"]);
  // noise 0.05: the threshold is 0.15
  const c = createSilenceDetector();
  assert.deepEqual(types(feed(c, [...seq(0.05, 0, 250), ...seq(0.14, 300, 1300)])), [], "0.14 < 0.15 started");
  const d = createSilenceDetector();
  assert.deepEqual(types(feed(d, [...seq(0.05, 0, 250), ...seq(0.16, 300, 700)])), ["speech-start"]);
});

test("the noise level follows quiet frames by the moving average 0.95/0.05", () => {
  const det = createSilenceDetector();
  // calibrated at 0.01 (threshold 0.03); 10 s of 0.029, below the threshold, lifts the noise towards 0.029
  // (threshold about 0.087), so 0.06 is no longer speech
  const drift = feed(det, [...seq(0.01, 0, 250), ...seq(0.029, 300, 10300), ...seq(0.06, 10350, 11300)]);
  assert.deepEqual(types(drift), [], "the noise level did not follow the quiet frames");
  const loud = feed(det, seq(0.2, 11350, 11800));
  assert.deepEqual(types(loud), ["speech-start"]);
});

test("candidate frames shorter than startMs and speech frames do not change the noise level", () => {
  const det = createSilenceDetector();
  // calibrated at 0.01 (threshold 0.03); single 50 ms pulses of 0.5 between quiet frames, for 3 s
  const frames = [...seq(0.01, 0, 250)];
  for (let t = 300; t <= 3300; t += 100) frames.push([0.5, t], [0.01, t + 50]);
  assert.deepEqual(types(feed(det, frames)), [], "a pulse of 50 ms started speech");
  // the threshold is still 0.03: 0.06 is speech; 5 s of loud speech is not ended by its own loudness
  const events = feed(det, [...seq(0.06, 3400, 3800), ...seq(0.5, 3850, 8850)]);
  assert.deepEqual(types(events), ["speech-start"], "speech frames raised the threshold above the speech");
  const end = feed(det, seq(0.01, 8900, 11000));
  assert.deepEqual(types(end), ["speech-end"]);
  assert.equal(end[0].at, 8850);
});

test("after speech-end the detector waits for speech-start again", () => {
  const det = createSilenceDetector();
  const events = feed(det, [
    ...seq(0.005, 0, 450),
    ...seq(0.3, 500, 900),
    ...seq(0.005, 950, 3000),
    ...seq(0.3, 3050, 3500),
    ...seq(0.005, 3550, 5600),
  ]);
  assert.deepEqual(types(events), ["speech-start", "speech-end", "speech-start", "speech-end"]);
  assert.equal(events[1].at, 900);
  assert.equal(events[3].at, 3500);
});

test("reset forgets everything, the noise level and the speech in progress included", () => {
  const det = createSilenceDetector();
  // noise 0.05 (threshold 0.15), then speech in progress
  const before = feed(det, [...seq(0.05, 0, 1000), ...seq(0.3, 1050, 1400)]);
  assert.deepEqual(types(before), ["speech-start"]);
  det.reset();
  // new calibration at 0.005: no speech-end for the forgotten speech
  const quiet = feed(det, seq(0.005, 1450, 4000));
  assert.deepEqual(types(quiet), [], "reset kept the speech in progress");
  // threshold now 0.02, not 0.15: 0.1 is speech
  const events = feed(det, [...seq(0.1, 4050, 4500), ...seq(0.005, 4550, 6600)]);
  assert.deepEqual(types(events), ["speech-start", "speech-end"], "reset kept the old noise level");
  assert.equal(events[1].at, 4500);
});
