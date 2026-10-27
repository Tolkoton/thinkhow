// Contract tests of conversation-resilience: createEarcons(ctx), short tones instead of words (slice tester).
// Written from the contract, not the code. The «~» of the contract is read as a band (Q1): ±8 % for a frequency,
// half to double for a duration.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { SRC_PATH, BAND, makeAudioContext, freq0, peak } from "./cr_page_fakes.mjs";

const require = createRequire(import.meta.url);
const { createEarcons } = require(SRC_PATH);

function fresh() {
  const Ctx = makeAudioContext({});
  const ctx = new Ctx();
  ctx.state = "running";
  return ctx;
}

const started = (ctx) => ctx.oscillators.filter((o) => o.startCalls.length > 0);
const within = (x, [lo, hi], what) => assert.ok(x >= lo && x <= hi, `${what}: ${x} not in [${lo}, ${hi}]`);

// the node reaches the destination of its own context, through a GainNode of that context
function reachesThroughGain(ctx, o) {
  const seen = new Set();
  const walk = (n, viaGain) => {
    if (n === ctx.destination) return viaGain;
    if (!n || seen.has(n)) return false;
    seen.add(n);
    const gain = viaGain || ctx.gains.includes(n);
    return (n.connected || []).some((x) => walk(x, gain));
  };
  return walk(o, false);
}

function span(oscs) {
  const start = Math.min(...oscs.map((o) => o.startCalls[0]));
  for (const o of oscs) assert.ok(o.stopCalls.length > 0, "an oscillator is never stopped");
  const stop = Math.max(...oscs.map((o) => o.stopCalls[o.stopCalls.length - 1]));
  return stop - start;
}

function quiet(ctx, oscs) {
  // a GainNode on the path of the tone is set below 1
  const onPath = new Set();
  const walk = (n) => {
    if (!n || onPath.has(n)) return;
    onPath.add(n);
    for (const x of n.connected || []) walk(x);
  };
  oscs.forEach(walk);
  const gains = ctx.gains.filter((g) => onPath.has(g));
  assert.ok(gains.length > 0, "no GainNode on the path of the tone");
  assert.ok(gains.some((g) => peak(g.gain) < 1), `gains ${gains.map((g) => peak(g.gain))}: none is below 1`);
}

test("listening: one quiet tone of about 880 Hz for about 120 ms through a GainNode of the same context", () => {
  const ctx = fresh();
  createEarcons(ctx).listening();
  const oscs = started(ctx);
  assert.equal(oscs.length, 1, `${oscs.length} oscillators`);
  within(freq0(oscs[0]), BAND.listening, "frequency");
  within(span(oscs), [0.06, 0.24], "duration, s");
  assert.ok(reachesThroughGain(ctx, oscs[0]), "the tone does not reach ctx.destination through a GainNode");
  quiet(ctx, oscs);
});

test("tick: a very quiet tone of about 660 Hz for about 60 ms through a GainNode of the same context", () => {
  const ctx = fresh();
  createEarcons(ctx).tick();
  const oscs = started(ctx);
  assert.equal(oscs.length, 1, `${oscs.length} oscillators`);
  within(freq0(oscs[0]), BAND.tick, "frequency");
  within(span(oscs), [0.03, 0.12], "duration, s");
  assert.ok(reachesThroughGain(ctx, oscs[0]), "the tone does not reach ctx.destination through a GainNode");
  quiet(ctx, oscs);
});

test("error: two tones going down, about 440 then about 330 Hz, about 300 ms together", () => {
  const ctx = fresh();
  createEarcons(ctx).error();
  const oscs = started(ctx);
  assert.ok(oscs.length >= 1, "no oscillator");
  // every frequency the tones take, in the order of their start
  const ordered = [...oscs].sort((a, b) => a.startCalls[0] - b.startCalls[0]);
  const freqs = ordered.flatMap((o) => (o.frequency.events.length ? o.frequency.events.map((e) => e.v) : [440]));
  within(freqs[0], BAND.errorHigh, "first frequency");
  within(freqs[freqs.length - 1], BAND.errorLow, "last frequency");
  within(span(oscs), [0.15, 0.6], "duration, s");
  for (const o of oscs) assert.ok(reachesThroughGain(ctx, o), "a tone does not reach ctx.destination through a GainNode");
});
