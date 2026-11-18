# Spike: the real Gemini Deep Research agent (task 314, 2026-11-18)

Script: `spike.py` (plan / go / get), `max_probe.py`. Raw answers: `run*-*.json`, logs `run*-*.log`, the full
report of run 1 joined from its parts: `run1-report.md` (images dropped from the JSON, 2 PNG charts).

## 1. Route
- **Vertex `global`** (`genai.Client(vertexai=True, project=pocket-lawyer-431614, location="global")`, the owner's
  gcloud credentials on this server): `interactions.create` accepted the call, after 103.3 s the interaction ended
  `status=failed`, `errors=[{"code": "api_error", "message": "Internal error encountered."}]`, usage empty. One
  attempt; Google does not document the agent on Vertex. Not taken.
- **Gemini API with a key** (`genai.Client()`, `GEMINI_API_KEY` from this server's environment): works — runs 1 and 2
  below. In Secret Manager of `pocket-lawyer-431614` there is a secret named `gemini-api-key` (listed by name only,
  its value not read); the Cloud Run service `thinkhow` does not have it today.

## 2. Measurements (`deep-research-preview-04-2026`, google-genai 2.32.0)
| Run | What | Time | Usage |
|---|---|---|---|
| run1-plan | `collaborative_planning=true`, question in Ukrainian, no language line | 22.6 s | in 177, out 308, thought 1 644 |
| run1-report | `previous_interaction_id`=run1-plan, «Так, план підходить, запускай.» | 434.9 s | in 516 422 (cached 5 538), out 32 564, thought 30 366, tool-use 50 468, `google_search` 18 |
| run2-plan | conversation + question + «Мова людини: українська (uk). План … пиши цією мовою.» | 23.0 s | in 202, out 407, thought 1 887 |

Price of run1-report by the Gemini 3.1 Pro list rates (aistudio.google.com/docs/pricing, read 2026-11-18: input
$2/M up to 200k a prompt, $4/M over; output with thinking $12/M up to 200k, $18/M over; cached $0.20/M; Search
$14 per 1 000 queries after 5 000 free a month; Deep Research «model inference is charged at standard Gemini list
rates … Search Grounding retrieved tokens excluded»): input 510 884 × $2–4/M = $1.02–2.04; output+thought 62 930 ×
$12–18/M = $0.76–1.13; search 18 × $0.014 = $0.25 (0 while under the free 5 000); total **≈ $1.8–3.4**, the plan
≈ $0.03. The bill itself is not visible from here.

## 3. Behaviour
- The plan comes as text: `**Title:** … **Input:** <the whole input echoed> **Research Plan:** (1) … (n) …`. With the
  language line the plan is in Ukrainian (run 2); without it, in English (run 1). Shown to a person: the part after
  `**Research Plan:**`.
- `output_text` is only the LAST text part. The report is the text parts of all `model_output` steps joined
  (run 1: 3 parts, 35 959 characters, `#`-headings and Markdown tables). Between them two PNG charts
  (`visualization` defaults to `auto`); `visualization: "off"` exists in `DeepResearchAgentConfig`.
- Sources: `[cite: N]` marks in the text and at the end a numbered list `N. [domain](https://vertexaisearch.cloud.google.com/grounding-api-redirect/…)`
  (46 links, all distinct); the same URLs as `url_citation` annotations (164 on the first part). The redirect links
  resolve with `platform.links.resolve_link` (3 links, 0.73 s, real addresses: niss.gov.ua, djinni.co).
  No Search suggestions HTML comes back.
- **The plan binds the agent:** `deep-research-max-preview-04-2026` with `previous_interaction_id` of a plan made by
  the standard agent → `400 invalid_request: Previous interaction … belongs to a different agent` (`max-probe.log`).
  So the version is chosen before the plan.
- `interactions.get(id)` of a stored interaction works from a new process (the `get` loop of every run is one):
  the research lives at Google, not in our process; Google keeps it 7 days.
- **A change refines the plan** (`change_probe.py`, `run2-change.*`): `previous_interaction_id`=run2-plan,
  `collaborative_planning=true`, `visualization="off"`, input «Не треба про культуру споживання кави, додай
  орієнтовну оренду приміщення в центрі.» → 20.4 s, `completed`, a new plan in Ukrainian without the culture step and
  with the rent step; `visualization="off"` accepted (whether it stops images on a full run — not run).
- **Max does not plan** (`max_spike.py`, `max-spike.log`, text `max-spike-plan-step.md`):
  `deep-research-max-preview-04-2026` with `collaborative_planning=true`, `visualization="off"` on q2 ran the whole
  research instead of a plan — 458.4 s, `completed`, a full report without `**Research Plan:**`. Usage not saved (the
  script was stopped in its next step; that step's interaction — a change to the report — was left running at Google,
  its id not printed). The cost of this probe ≈ one Max run, $3–7 by Google's estimate.
- **Max starts fresh with the plan in its input** (`max_fresh_probe.py`, `max-fresh-probe.log`): no
  `previous_interaction_id`, input = the q2 brief + `[Approved research plan]` + the plan of run2-change +
  «The plan is approved. Run the research by it.», `collaborative_planning=false` → `in_progress` after 15 s;
  cancelled → `cancelled`, usage `null`.
- **Unknown id:** `get("v1_bogus")` → `BadRequestError`, `status_code` 400 («Invalid interaction name»); a well-formed id
  that does not exist → `NotFoundError`, `status_code` 404, `code` None («Requested entity was not found.»).
