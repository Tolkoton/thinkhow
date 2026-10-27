// Contract tests of conversation-resilience, the invariants I1–I4 (slice tester). Written from the contract, not
// the code. The project has no property-based library: the inputs are chosen by hand from each «Domain», and
// every expected value is written by hand.
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

// one turn of the mode: the answer comes in these deltas; returns the texts sent to /speak
async function speakOf(deltas) {
  const p = loadPage();
  p.voice.push(json({ text: "Розкажи" }));
  p.reply.push(reply(...deltas));
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  assert.equal(state(p), "listening", `the answer did not play to its end: ${JSON.stringify(deltas)}`);
  return spokenTexts(p);
}

test("I1: no /speak request carries text of a «Джерела:» line or an http address, for any split into deltas", async () => {
  // sources line in the middle (before the deep part) and at the end, a link and a bare address in the text
  const answer =
    "Ось текст. Див. [ADAC](https://adac.de) далі. Сайт https://x.ua тут." +
    "\n\nДжерела: [ДЖ1](https://a.ua), [ДЖ2](https://b.ua)" +
    "\n\nШукаю: ціни\n- питання" +
    "\n\nЗвіт тут." +
    "\n\nДжерела: [ДЖ3](https://c.ua)";
  const atLiteral = answer.split(/(?=\n)|(?<=Дже)/); // every line break and the middle of «Джерела» start a delta
  const forbidden = /Джерела|ДЖ\d|https?|htt|:\/\/|\.ua|adac\.de|\]\(/;
  for (const deltas of [[answer], chunks(answer, 1), chunks(answer, 3), chunks(answer, 7), atLiteral]) {
    const said = await speakOf(deltas);
    assert.ok(said.length > 0, "nothing was spoken");
    for (const s of said) assert.ok(!forbidden.test(s), `deltas of ${deltas[0].length}: /speak got ${JSON.stringify(s)}`);
  }
});

test("I2: one human turn gets at most one automatic /retry, whatever the failures; the next turn has its own", async () => {
  // failed, then the retry failed too: one /retry, the mode goes off
  const a = loadPage();
  a.voice.push(json({ text: "Привіт" }));
  a.reply.push(failedReply("Поч"));
  a.retry.push(failedReply(), failedReply(), failedReply());
  await tapTalk(a);
  await utter(a);
  await playAll(a);
  assert.equal(retryCalls(a).length, 1);
  assert.equal(state(a), "");
  // network, then not 200: one /retry
  const b = loadPage();
  b.voice.push(json({ text: "Привіт" }));
  b.reply.push(offline());
  b.retry.push(fragment("Помилка сервера.", 500), reply("Зайвий повтор."));
  await tapTalk(b);
  await utter(b);
  await playAll(b);
  assert.equal(retryCalls(b).length, 1);
  assert.equal(state(b), "");
  // the counter is per turn, not per mode: three turns, each fails once and has its own retry
  const c = loadPage();
  c.voice.push(json({ text: "Один" }), json({ text: "Два" }), json({ text: "Три" }));
  c.reply.push(fragment("Збій.", 502), failedReply("Від"), offline());
  c.retry.push(reply("Перша відповідь."), reply("Друга відповідь."), failedReply(), reply("Зайвий повтор."));
  await tapTalk(c);
  await utter(c);
  await playAll(c);
  assert.equal(retryCalls(c).length, 1, "turn 1");
  assert.equal(state(c), "listening", "turn 1");
  await utter(c);
  await playAll(c);
  assert.equal(retryCalls(c).length, 2, "turn 2");
  assert.equal(state(c), "listening", "turn 2");
  await utter(c);
  await playAll(c);
  assert.equal(retryCalls(c).length, 3, "turn 3");
  assert.equal(replyCalls(c).length, 3);
  assert.equal(state(c), "");
});

test("I3: no recognition error (fewer than three in a row) and no voice error turns the mode off", async () => {
  const p = loadPage();
  p.voice.push(
    fragment("Збій.", 502),
    json({ text: "" }),
    json({ text: "Перша" }),
    offline(),
    fragment("Збій.", 503),
    json({ text: "Друга" }),
    json({ text: "" }),
    json({ text: "Третя" }),
  );
  p.reply.push(
    reply("Перше речення. Друге речення. Третє речення."),
    reply("Одне речення. Інше речення."),
    reply("Остання відповідь."),
  );
  const ok = () => new Response(new Uint8Array([1]), { status: 200, headers: { "content-type": "audio/mpeg" } });
  // turn 1: the second sentence 502, the third does not decode; turn 2: both sentences fail (502, network)
  p.speak.push(ok, fragment("Озвучення недоступне.", 502), ok, fragment("Озвучення недоступне.", 502), offline());
  p.decodeFailAt.add(1);
  await tapTalk(p);
  for (let i = 0; i < 8; i++) {
    await utter(p);
    await playAll(p);
    assert.equal(state(p), "listening", `after /voice ${i + 1}`);
  }
  assert.equal(voiceCalls(p).length, 8);
  assert.equal(replyCalls(p).length, 3);
  assert.ok(!p.talk.stateLog.slice(1).includes(""), `the mode went off: ${p.talk.stateLog}`);
  assert.equal(p.reloads, 0);
  // a lawful turn after the refused ones sounds as usual
  assert.equal(spokenTexts(p).at(-1), "Остання відповідь.");
});

test("I4: the voice text only grows by appending, and the pieces sent to /speak give voiceText of the attempt", async () => {
  // (a) voiceText(stableText(a)) is a beginning of voiceText(stableText(a + d)) for every a and continuation
  const answers = [
    "Див. [A](https://a.de) далі. [1] Так. Сайт https://x.ua тут.\n\nДжерела: [ДЖ](https://b.ua)\n\nЗвіт.",
    "Відповідь.\n\nДжерела: [a](https://a), [b](https://b)",
    "Текст [1] без посилання і [дужки] теж.\nНовий рядок http://q.ua кінець.",
    "Див. [ADAC клуб](https://adac.de/x) далі.\n\nДжерела: [a](https://a)\n\nШукаю: ціни\n- питання\n\nЗвіт.\n\nДжерела: [b](https://b)",
  ];
  for (const answer of answers) {
    const cs = Array.from(answer);
    const voices = cs.map((_, i) => voiceText(stableText(cs.slice(0, i).join(""))));
    voices.push(voiceText(stableText(answer)));
    for (let i = 0; i < voices.length; i++) {
      for (let j = i + 1; j < voices.length; j++) {
        assert.ok(
          voices[j].startsWith(voices[i]),
          `${JSON.stringify(cs.slice(0, i).join(""))} → ${JSON.stringify(voices[i])}, but ` +
            `${JSON.stringify(cs.slice(0, j).join(""))} → ${JSON.stringify(voices[j])}`,
        );
      }
    }
  }
  // (b) the pieces sent to /speak, for the answer cut into two deltas at every position
  const answer = answers[0];
  const expected = "Див.Aдалі.[1]Так.Сайттут.Звіт."; // voiceText of the answer, by hand, without spaces
  const cs = Array.from(answer);
  for (let k = 0; k <= cs.length; k++) {
    const said = await speakOf([cs.slice(0, k).join(""), cs.slice(k).join("")]);
    assert.equal(noSpace(said.join(" ")), expected, `cut at ${k}: ${JSON.stringify(said)}`);
  }
  // (c) a retry is an attempt of its own: the cut first attempt adds nothing, the retry gives its voiceText
  const p = loadPage();
  p.voice.push(json({ text: "Розкажи" }));
  p.reply.push(failedReply("Див. [A](htt"));
  p.retry.push(reply("Див. [A](https://a.de) далі. ", "Кінець.\n\nДжерела: [ДЖ](https://b.ua)"));
  await tapTalk(p);
  await utter(p);
  await playAll(p);
  assert.equal(noSpace(spokenTexts(p).join(" ")), "Див.Aдалі.Кінець.");
});
