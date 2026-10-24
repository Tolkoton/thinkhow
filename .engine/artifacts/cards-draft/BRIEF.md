# Brief for drafting the ThinkHow cards (task 302, slice S1 cards-library)

You write thinking-model cards for ThinkHow: a thinking assistant that never gives ready answers (it leads the
person to think wider — alternatives, why a plan may fail, missing information, blind spots, emotions — so that
the person decides). Two readers per card:
- the **router** (half `router`): reads the router halves of all 18 cards at once and must tell from what the
  person said which 2–3 cards fit now. It must be able to tell your card from its neighbours — write `when_yes`,
  `when_no`, `signals` so they discriminate (the matrix of research 01 §7(д): primary / fallback / contraindicated
  per intent; contraindications from §7(а) row 10 «emotional state», row 4 reversibility, row 8 options state).
- the **facilitator** (half `facilitator`): an LLM leading the person phase by phase, one question per reply.
  `card_prompt` (src/thinkhow/knowledge/prompt.py) renders it.

## Format — exactly the shape of `cards/pre-mortem.yaml` (read it first; it is the model)
Schema: `src/thinkhow/knowledge/schema.py` (pydantic, extra fields forbidden). Fields:
- `id`: kebab-case, the file name without `.yaml`.
- `title`: Ukrainian, descriptive. **No trademarked names** (research 01 §3.6): never «Kepner-Tregoe», «Cynefin»,
  «WOOP», «GROW™», «Outcome-Driven Innovation», «Six Thinking Hats». Neutral acronyms in common use (SCAMPER, WRAP,
  JTBD) may appear in the title in brackets after a Ukrainian description; attribution to authors in `purpose` is
  fine («за Г. Еттінген»).
- `router`: `needs` (one sentence: what must be known at the start), `when_yes` (2–4 situations), `when_no` (2–4
  situations where the card does NOT fit — say in plain words what the situation is; this is what tells the router
  apart from neighbours), `signals` (3–5 things the person says or describes).
- `facilitator`: `purpose` (what it does and why it works — cite evidence ONLY as research 01 §3.3 / §7(в) / §7(ґ)
  state it, with author and year; never invent a study or a number; if the evidence is weak, say «усталена
  практика» or nothing), `stance`, `needs`, `phases` (3–5; `id` like `phase_1_<snake>` matching `^[a-z0-9_]{1,64}$`;
  `title`; `goal`; `how` — 2–4 items in the style «Як: …», «Правило: …», «Якщо … — …»; optional `skip_if`; `exit` —
  an observable condition), `ending` (what the person leaves with; typical length «Зазвичай N–M реплік; якщо
  розмова тягнеться понад K — час підсумувати»), `traps` (2–3 real traps of this method with recovery, PLUS always
  the last trap named exactly `Не той випадок`, whose text lists when the card does not fit and ends with «— ця
  картка не підходить.»), `pairs_well` («Перед: …. Після: ….» naming other cards of the 18 by their Ukrainian
  titles — this is for the model only).
- Ukrainian throughout, own words (clean-room: no verbatim copying of books). Phrasing of questions natural, not a
  questionnaire. No ready answers: hypotheses only as questions to the person. Nothing for crises (non-goal N3):
  no crisis protocol, no hotline text.
- Use YAML folded scalars `>-` for long text, like pre-mortem.yaml. Header comment: one or two lines on what the
  card is and its source sections in research 01.

## The 18 cards (ids are fixed — other cards' `pairs_well` refer to these titles)
| id | slot (research 01 §7(ґ)) | working Ukrainian title |
|---|---|---|
| first-principles | 1 First Principles | Перші принципи: розібрати до основ і зібрати наново |
| issue-tree | 2 MECE / Issue Trees | Дерево питань: розкласти ситуацію на незалежні гілки |
| complexity-sensemaking | 3 Cynefin Sensemaking | Що це за ситуація: зрозуміла, складна, заплутана чи пожежа |
| five-whys | 4 5 Whys with branching | П'ять «чому» з розгалуженням |
| is-is-not | 5 Is / Is-Not specification | Є / не є: де проблема є, а де її немає |
| wrap-decision | 6 WRAP | Важке рішення: ширше, перевірити, відступити, підготуватися (WRAP) |
| weighted-matrix | 7 Weighted Decision Matrix & Value Clarification | Зважене порівняння варіантів за власними цінностями |
| reversible-doors | 8 One-Way/Two-Way Doors + 10/10/10 | Двері в один чи в обидва боки і 10/10/10 |
| evaporating-cloud | 9 TOC Evaporating Cloud | Хмара, що розвіюється: дилема без гнилого компромісу |
| pre-mortem | 10 Pre-mortem (exists — do not write) | Pre-mortem — «розтин» плану, який ще не почався |
| consider-opposite | 11 Consider-the-Opposite & Steelmanning | Подумати протилежне: найсильніша версія іншої думки |
| socratic-questioning | 12 Socratic Questioning | Сократівські питання: перевірити власне переконання |
| scamper | 13 SCAMPER with Inversion | Сім напрямків змінити те, що є (SCAMPER) |
| mental-contrasting | 14 MCII / WOOP | Бажання, перешкода і план «якщо — то» |
| reflective-cycle | 15 Gibbs Reflective Cycle & Double-Loop | Осмислити досвід і переглянути власне правило |
| goal-to-plan | 16 Backcasting & GROW | Від мети до перших кроків: мета, де я зараз, шляхи, що зроблю |
| jobs-to-be-done | 17 JTBD — Progress & Switch Lens | Яку роботу «наймають» зробити: прогрес клієнта і сили переходу (JTBD) |
| opportunity-tree | 18 OST + Assumption Mapping + RICE | Дерево можливостей, найризикованіше припущення і пріоритети |

Slot 16 is one card that can go forward from today (goal → reality → options → will) or backward from the goal
(milestones back to today) — the facilitator picks the direction in phase 1 by what the person has. Slot 18 is one
pipeline: outcome → opportunities → solutions → the riskiest assumption → the cheapest test; when there are many
options (>6) a short scoring phase (reach, impact, confidence, effort) replaces the tree.

## Material (read the parts for your cards)
`docs/research/01-library.md`: §7(а) dimensions (L374–394), §7(б) schema (L396–507), §7(в) three full cards — 5
Whys L514, Pre-mortem L672, JTBD L827 (adapt their steps, pitfalls, examples into our shorter format), §7(г) the 62
candidates table (L986–1058), §7(ґ) shortlist (L1059–1116), §7(д) matrix and tie rules (L1118–1166), §7(е)
journeys (L1167–1188), §3.3 evidence (L203–235), §3.5 dialogue adaptation (L267–287), §3.6 trademarks (L288–316).

## Check before you finish
For each file: `cd /home/lao/projects/thinkhow && PYTHONPATH=src uv run python -c "import yaml,sys; from thinkhow.knowledge
import Card, card_prompt; c=Card.model_validate(yaml.safe_load(open(sys.argv[1],encoding='utf-8'))); assert
c.id+'.yaml'==sys.argv[1].split('/')[-1]; print(c.id, len(c.facilitator.phases))" <path>` must print the id.
Write only into `.engine/artifacts/cards-draft/`. Touch nothing else.
