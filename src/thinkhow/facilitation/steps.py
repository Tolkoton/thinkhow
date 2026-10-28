"""The result of a chosen step, recognized from the person's answer to the question about it (S6).

One model call: did the person answer, how did the step go, is it clearer what to do next, what they said in a
few of their own words. Does NOT store anything (workspace does) and does NOT ask anything.
"""

from thinkhow.facilitation.types import StepOutcome
from thinkhow.platform import llm as model

RECOGNIZER = """Ти читаєш одну репліку людини в ThinkHow. Перед нею ThinkHow спитав, як вийшов крок, який
людина обрала минулого разу, і чи стало їй ясніше, що робити далі. Людина могла відповісти, а могла писати
про інше.
- answered — чи відповіла людина про цей крок (хоча б про одне з двох питань);
- outcome — як вийшов крок: worked (вийшло), not_worked (не вийшло), unexpected (вийшло інакше, ніж думали);
  null, якщо про це не сказано;
- clearer — чи стало ясніше, що робити далі: yes, partly, no; null, якщо про це не сказано;
- said — одним-двома реченнями, що людина сказала про крок, її словами і мовою її репліки; порожньо, якщо не
  відповіла."""


def recognize_step(step: str, question: str, text: str, llm: model.Llm) -> StepOutcome:
    """One generate_json over the step, the question asked and the person's answer."""
    turn = f"Обраний крок: {step}\nПитання ThinkHow: {question}\nРепліка людини: {text}"
    return llm.generate_json(RECOGNIZER, [model.Turn("user", turn)], StepOutcome, None)
