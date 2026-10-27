// Contract tests of conversation-resilience: voiceText and stableText, the text for the voice (slice tester).
// Written from the contract, not the code; every expected value is written by hand.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { SRC_PATH, collapse } from "./cr_page_fakes.mjs";

const require = createRequire(import.meta.url);
const { voiceText, stableText } = require(SRC_PATH);

test("voiceText drops the sources line at the end of the answer", () => {
  assert.equal(voiceText("Відповідь.\n\nДжерела: [a](https://a.ua), [b](https://b.ua)"), "Відповідь.");
});

test("voiceText drops a sources line in the middle up to the next blank line and keeps what follows", () => {
  const answer =
    "Відповідь.\n\nДжерела: [a](https://a.ua)\n\nШукаю: ціни\n- питання\n\nЗвіт.\n\nДжерела: [b](https://b.ua)";
  assert.equal(voiceText(answer), "Відповідь.\n\nШукаю: ціни\n- питання\n\nЗвіт.");
});

test("voiceText turns every Markdown link into its name, whatever the address", () => {
  assert.equal(voiceText("Див. [ADAC](https://adac.de) далі."), "Див. ADAC далі.");
  assert.equal(voiceText("Порівняй [перше](/local/path) і [друге](mailto:x@y.ua)."), "Порівняй перше і друге.");
});

test("voiceText drops a bare http address up to the space", () => {
  const got = voiceText("див. https://adac.de/x?y=1 далі.");
  assert.equal(collapse(got), "див. далі.");
  assert.ok(!got.includes("http") && !got.includes("adac"), JSON.stringify(got));
});

test("stableText cuts the unfinished word: everything after the last space or line break", () => {
  assert.equal(stableText("Привіт, ти зна"), "Привіт, ти ");
  assert.equal(stableText("див. htt"), "див. ");
  assert.equal(stableText("див. https://adac.de"), "див. ");
  assert.equal(stableText("Перше речення. "), "Перше речення. ");
  assert.equal(stableText(""), "");
});

test("stableText holds an unclosed link: a [ without ] after it, or ]( without its closing )", () => {
  assert.equal(stableText("Див. [ADAC клуб "), "Див. ");
  assert.equal(stableText("Див. [ADAC](https://adac.de далі "), "Див. ");
  assert.equal(stableText("Див. [ADAC](https://adac.de) далі "), "Див. [ADAC](https://adac.de) далі ");
});

test("stableText does not hold [1] without a ( after it", () => {
  assert.equal(stableText("[1] Перше. "), "[1] Перше. ");
  assert.equal(stableText("Текст [дужки] далі "), "Текст [дужки] далі ");
});

test("stableText cuts a beginning of the sources literal standing at the very end", () => {
  // a space before the line break, so that no word is left at the end after the cut (Q2)
  assert.equal(stableText("Ось текст. \n"), "Ось текст. ");
  assert.equal(stableText("Ось текст. \n\n"), "Ось текст. ");
  assert.equal(stableText("Ось текст. \n\nДж"), "Ось текст. ");
});

test("stableText cuts an open sources line at the end from its literal", () => {
  assert.equal(stableText("Ось текст. \n\nДжерела: [a](https://a.ua), [b](https://b.ua)"), "Ось текст. ");
  assert.equal(stableText("Ось текст. \n\nДжерела: [a](https://a.ua), "), "Ось текст. ");
  // a closed sources line in the middle stays in the stable text
  assert.equal(
    stableText("Відповідь.\n\nДжерела: [a](https://a.ua)\n\nШукаю: ціни "),
    "Відповідь.\n\nДжерела: [a](https://a.ua)\n\nШукаю: ціни ",
  );
});

test("stableText applies its cuts round and round until the text stops getting shorter", () => {
  // the word «Звіт» goes, then the blank line, then the sources line that became open
  assert.equal(stableText("Ось відповідь. \n\nДжерела: [a](https://a.ua)\n\nЗвіт"), "Ось відповідь. ");
  // the word goes, then the unclosed link
  assert.equal(stableText("Див. [ADAC клуб](https://a"), "Див. ");
});
