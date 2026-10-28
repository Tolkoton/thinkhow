# 718 — slice conversation-loop: третя суперечка про contract tests

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: testing-parked-conversation-loop

## Що сталося
Два кола суперечки між builder-ом і tester-ом не розв'язали slice conversation-loop: round 1: tests/contract/conversation_loop/test_cl_*.py (all 7 wrappers: detector, split, talk, invariants, disputed_q1_comma, disputed_q2_words, disputed_q4_enable) — test_wrong | round 2: tests/contract/conversation_loop/test_cloop_catchup_smoke.py::test_smoke_fails_when_live_holds_no_person_turns — test_wrong; tests/contract/conversation_loop/test_cloop_catchup_disputed_q3_artifact.py::test_smoke_writes_its_output_to_the_artifact — test_right. Третє коло не проводиться: slice відкладено, робота йде далі з наступним. Обидва кола стоять у .engine/testing/ledger.md.

- Записано: 2026-10-27T12:38:47Z, hook testing.py

## Що зробити
Це питання до власника, не робота для агента. Коли власник відповість, задача повернеться в чергу: виконай відповідь, запиши її у звіт і закрий задачу.

## Готово, коли
Власник відповів, і відповідь виконано.

## Питання до власника
1. Хто правий у суперечці про тести slice-а conversation-loop — тест, код чи slice contract слід уточнити?
   Контекст (дописав агент задачі 308, 2026-10-27): третя суперечка — не про помилку. Три запечатані тести
   conversation-loop (режим розмови, частина 1) перевіряють старе правило «будь-яка помилка → режим вимикається»:
   `test_cl_talk.py::test_error_with_a_fragment_shows_its_text_and_stops`,
   `test_cl_talk.py::test_error_without_a_fragment_shows_the_stop_text_and_stops`,
   `test_cl_disputed_q4_enable.py::test_controls_enabled_again_after_an_error_stop`. Наступний slice
   conversation-resilience (його контракт запечатано) свідомо це змінює: розпізнавання не вдалося — сигнал і знову
   слухати; відповідь не вдалася — один автоматичний повтор; речення не озвучилось — пропуск. Перші два кола суперечки
   цього slice-а були про інше (збіг імен файлів тестів, дописаний тест), тож на це, справжнє, кола вже не лишилось.
   Варіанти: А — тести застаріли: свіжий tester переписує ці три тести під правило conversation-resilience (решту їхніх
   перевірок лишає). Б — лишити старе правило: прибрати зміни conversation-resilience, режим знову вимикається від
   будь-якої помилки. Порада: А — так режим не вимагає дотику після однієї невдалої репліки в машині (AC1), а все,
   що ці тести ще перевіряють (текст помилки, закритий звук, без перезавантаження, кнопки знову доступні), лишається.
   Відповідь: А. Записано Claude зі слів власника, 2026-10-27, сесія thinkhow-desk, у задачі 308 (питання 1: «Те саме питання
   стоїть у задачі 718 — відповісти досить тут»): «Режим розмови. Так, я згоден, що А хай буде.» Виконано в задачі 308,
   2026-10-28: свіжий slice-tester переписав три тести (`.engine/testing/ledger.md`, conversation-resilience, round 1).
