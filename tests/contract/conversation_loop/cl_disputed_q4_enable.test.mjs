// Disputed (Q4): «#mic, #send, поле — disabled, поки режим увімкнено» read as: once the mode is off without a
// reload (an error), they are enabled again. Not sealed until Q4.
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPage, utter, state, tapTalk, fragment } from "./cl_page_fakes.mjs";

test("after the mode stopped on an error #mic, #send and the field are enabled again", async () => {
  const p = loadPage();
  p.voice.push(fragment("Не вдалося розпізнати — спробуйте ще раз.", 502));
  await tapTalk(p);
  assert.equal(p.byId.send.disabled, true, "the mode did not disable #send");
  await utter(p);
  assert.equal(state(p), "");
  assert.equal(p.byId.mic.disabled, false, "#mic");
  assert.equal(p.byId.send.disabled, false, "#send");
  assert.equal(p.field.disabled, false, "the field");
});
