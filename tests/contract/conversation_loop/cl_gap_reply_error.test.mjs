// Overseer test gap (PASS 20261027T101838Z-1d20fb, board 717): with the mode on, /reply answers non-200 with a
// <p class="error"> fragment. Builder test beside the sealed cl_talk.test.mjs; fakes in cl_page_fakes.mjs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPage, utter, state, tapTalk, json, fragment, retryCalls } from "./cl_page_fakes.mjs";

test("/reply 409 in the mode: its text in #error, the mode off, no reload, #mic and #send enabled", async () => {
  const p = loadPage();
  p.voice.push(json({ text: "Привіт" }));
  p.reply.push(fragment("Спершу дочекайтеся відповіді.", 409));
  await tapTalk(p);
  assert.equal(p.byId.mic.disabled, true, "the mode did not disable #mic");
  assert.equal(p.byId.send.disabled, true, "the mode did not disable #send");
  await utter(p);
  assert.equal(retryCalls(p).length, 0, "409 was retried");
  assert.equal(p.byId.error.textContent, "Спершу дочекайтеся відповіді.");
  assert.equal(state(p), "");
  assert.equal(p.reloads, 0, "the page reloaded");
  assert.equal(p.byId.mic.disabled, false, "#mic");
  assert.equal(p.byId.send.disabled, false, "#send");
});
