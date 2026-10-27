// Catch-up contract tests of conversation-resilience, the invariants I1–I4 (slice tester). Written from the
// contract, not the code, on inputs of their own (not those of cr_invariants.test.mjs), chosen by hand from each
// «Domain»; every expected value is written by hand. The page fakes are the slice's sealed cr_page_fakes.mjs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import {
  SRC_PATH,
  loadPage,
  utter,
  state,
  voiceCalls,
  replyCalls,
  retryCalls,
  spokenTexts,
  playAll,
  tapTalk,
  json,
  fragment,
  offline,
  reply,
  failedReply,
  audioOk,
  noSpace,
} from "./cr_page_fakes.mjs";

const require = createRequire(import.meta.url);
const { voiceText, stableText } = require(SRC_PATH);

const chunks = (text, n) => {
  const cs = Array.from(text);
  const out = [];
  for (let i = 0; i < cs.length; i += n) out.push(cs.slice(i, i + n).join(""));
  return out;
};

async function turn(deltas, { failFirst = null } = {}) {
  const p = loadPage();
  p.voice.push(json({ text: "Розкажи" }));
  if (failFirst) {
    p.reply.push(failedReply(...failFirst));
    p.retry.push(reply(...deltas));
  } else {
    p.reply.push(reply(...deltas));
  }
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  assert.equal(state(p), "listening", `the answer did not play to its end: ${JSON.stringify(deltas)}`);
  return p;
}

// the texts sent to /speak after the page's /retry call (the retry's own attempt)
function spokenAfterRetry(p) {
  const at = p.calls.findIndex((c) => c.url.endsWith("/retry"));
  assert.ok(at >= 0, "no /retry was sent");
  const after = p.calls.slice(at + 1).filter((c) => c.url.endsWith("/speak"));
  const all = spokenTexts(p);
  return all.slice(all.length - after.length);
}

test("catch-up I1: no /speak text holds a «Джерела:» line or an http address, links with spaces, http:// and a retry", async () => {
  const answer =
    "Огляд [клуб ADAC](https://adac.de) і [ще](http://h.ua/p) тут. Адреса https://s.ua/x?y=2 вказана." +
    "\n\nДжерела: [ДЖ1](https://a.ua)" +
    "\n\nШукаю: ціни." +
    "\n\nЗвіт [з](https://r.ua)." +
    "\n\nДжерела: [ДЖ2](https://c.ua), [ДЖ3](https://d.ua)";
  const forbidden = /Джерела|ДЖ\d|https?|htt|:\/\/|\.ua|adac\.de|\]\(/;
  const splits = [
    [answer],
    chunks(answer, 2),
    chunks(answer, 5),
    answer.split(/(?<=\()|(?=\n)/), // after every «(» and before every line break
    answer.split(/(?<=\nД)|(?<=\nДж)|(?<=\nДже)|(?<=Джерела)|(?<=Джерела:)/), // inside every literal
  ];
  for (const deltas of splits) {
    const said = spokenTexts(await turn(deltas));
    assert.ok(said.some((s) => s.includes("Огляд")), `nothing of the text was spoken: ${JSON.stringify(said)}`);
    for (const s of said) assert.ok(!forbidden.test(s), `/speak got ${JSON.stringify(s)}`);
  }
  // the first attempt is cut inside its sources line; the retry carries the whole answer
  const p = await turn(chunks(answer, 4), { failFirst: ["Огляд тут.", "\n\nДжерела: [ДЖ1](htt"] });
  for (const s of spokenTexts(p)) assert.ok(!forbidden.test(s), `/speak got ${JSON.stringify(s)}`);
});

test("catch-up I2: at most one automatic /retry per human turn, a 409, a retry that worked, and a new start after off", async () => {
  // 409 is a failure of the reply too: at most one retry (here none)
  const a = loadPage();
  a.voice.push(json({ text: "Привіт" }));
  a.reply.push(fragment("Спершу дочекайтеся відповіді.", 409));
  a.retry.push(reply("Зайвий повтор."));
  await tapTalk(a);
  await utter(a);
  await playAll(a);
  assert.ok(retryCalls(a).length <= 1, `409: ${retryCalls(a).length} retries`);
  // turn 1: failed → the retry works; turn 2: ok; turn 3: 503 → the retry fails over the network → off
  const b = loadPage();
  b.voice.push(json({ text: "Один" }), json({ text: "Два" }), json({ text: "Три" }), json({ text: "Чотири" }));
  b.reply.push(failedReply("Поча"), reply("Друга відповідь."), fragment("Збій.", 503), reply("Четверта."));
  b.retry.push(reply("Перша відповідь."), offline(), reply("Зайвий повтор."), reply("Зайвий повтор."));
  await tapTalk(b);
  await utter(b);
  await playAll(b);
  assert.equal(retryCalls(b).length, 1, "turn 1");
  assert.equal(state(b), "listening", "turn 1");
  await utter(b);
  await playAll(b);
  assert.equal(retryCalls(b).length, 1, "turn 2 needed no retry");
  await utter(b);
  await playAll(b);
  assert.equal(retryCalls(b).length, 2, "turn 3: one retry of its own");
  assert.equal(state(b), "", "turn 3: the retry failed, the mode is off");
  // a new start after the mode went off: the next turn has its own one retry
  b.reply.push(failedReply(), reply("Зайве."));
  await tapTalk(b);
  await utter(b);
  await playAll(b);
  assert.ok(retryCalls(b).length <= 3, `after the new start: ${retryCalls(b).length} retries in all`);
  assert.ok(!spokenTexts(b).includes("Зайвий повтор."), `a second retry of one turn was answered: ${spokenTexts(b)}`);
});

test("catch-up I3: recognition errors (400, network, empty, 504) fewer than three in a row and every voice error keep the mode on", async () => {
  const p = loadPage();
  p.voice.push(
    fragment("Помилка запиту.", 400),
    offline(),
    json({ text: "Раз" }),
    json({ text: "" }),
    fragment("Збій.", 504),
    json({ text: "Два" }),
    offline(),
    offline(),
    json({ text: "Три" }),
  );
  p.reply.push(
    reply("Перше речення. Друге речення. Третє речення."),
    reply("Коротко."),
    reply("Добре. Ясно."),
  );
  // turn 1: every sentence fails — 502, then decodeAudioData refuses, then the network
  p.speak.push(fragment("Озвучення недоступне.", 502), audioOk(), offline());
  p.decodeFailAt.add(0);
  await tapTalk(p);
  for (let i = 0; i < 9; i++) {
    await utter(p);
    await playAll(p);
    assert.equal(state(p), "listening", `after /voice ${i + 1}`);
  }
  assert.equal(voiceCalls(p).length, 9);
  assert.equal(replyCalls(p).length, 3);
  assert.ok(!p.talk.stateLog.slice(1).includes(""), `the mode went off: ${p.talk.stateLog}`);
  assert.equal(spokenTexts(p).at(-1), "Ясно.");
});

function growsOnlyByAppending() {
  const answers = [
    "Рядок.\nДжерела кажуть так. [a] (b) не посилання. Див. [один два](https://x.ua/a_b) і http://y.ua далі.",
    "Текст.\n\nДж",
    "Ціна [1] зросла. Дані [звіт ADAC](https://adac.de/a?b=1) кажуть так. Сайт http://q.ua є." +
      "\n\nДжерела: [x](https://x.ua)\n\nШукаю: ціни.\n\nПідсумок.\n\nДжерела: [y](https://y.ua)",
  ];
  for (const answer of answers) {
    const cs = Array.from(answer);
    const voices = cs.map((_, i) => voiceText(stableText(cs.slice(0, i).join(""))));
    voices.push(voiceText(stableText(answer)));
    for (let i = 0; i + 1 < voices.length; i++) {
      assert.ok(
        voices[i + 1].startsWith(voices[i]),
        `${JSON.stringify(cs.slice(0, i).join(""))} → ${JSON.stringify(voices[i])}, then ` +
          `${JSON.stringify(cs.slice(0, i + 1).join(""))} → ${JSON.stringify(voices[i + 1])}`,
      );
    }
  }
}

test("catch-up I4: the voice text grows only by appending, and the pieces sent to /speak give voiceText of the attempt", async () => {
  growsOnlyByAppending();
  const answer =
    "Ціна [1] зросла. Дані [звіт ADAC](https://adac.de/a?b=1) кажуть так. Сайт http://q.ua є." +
    "\n\nДжерела: [x](https://x.ua)\n\nШукаю: ціни.\n\nПідсумок.\n\nДжерела: [y](https://y.ua)";
  const expected = "Ціна[1]зросла.ДанізвітADACкажутьтак.Сайтє.Шукаю:ціни.Підсумок."; // by hand, no spaces
  const cs = Array.from(answer);
  for (let k = 0; k <= cs.length; k++) {
    const said = spokenTexts(await turn([cs.slice(0, k).join(""), cs.slice(k).join("")]));
    assert.equal(noSpace(said.join(" ")), expected, `cut at ${k}: ${JSON.stringify(said)}`);
  }
  const p = await turn(chunks(answer, 3), { failFirst: ["Ціна [1] зросла. Дані [звіт AD"] });
  assert.equal(noSpace(spokenAfterRetry(p).join(" ")), expected);
});
