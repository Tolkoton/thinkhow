import sys, time
from thinkhow.platform.config import Settings
from thinkhow.platform import llm as model
from thinkhow.facilitation.steps import recognize_step, RECOGNIZER
from thinkhow.facilitation.types import DeepConsent
from thinkhow.facilitation import deep
from google import genai
s = Settings()
client = genai.Client(vertexai=True, project=s.project, location=s.location)
llm = model.VertexLlm(client, s.model, s.llm_timeout_s, 1)
steps = [
 ("Поговорити з керівником про навантаження", "Як вийшов крок і чи стало ясніше, що далі?", "Поговорив, він погодився зняти один проєкт. Тепер ясніше."),
 ("Записати три варіанти переїзду", "Як вийшов цей крок?", "Не встиг, був зайнятий. Але думаю про другий варіант."),
 ("Порахувати бюджет на місяць", "Чи вдалося порахувати? Чи стало ясніше?", "Вийшло зовсім не те, що я думала — витрат більше на 30%, тепер не знаю що робити."),
 ("Спитати сестру про допомогу з дітьми", "Як пройшла розмова?", "А можна про інше? Мене зараз хвилює робота."),
 ("Пройтись і подумати про вибір", "Як вийшло?", "Так, частково. Прогулянка допомогла, але рішення ще нема."),
 ("Make a list of pros and cons", "How did the step go?", "It worked, the list made it obvious I should stay."),
]
for st,q,t in steps:
    a=time.monotonic(); r=recognize_step(st,q,t,llm); print("StepOutcome", round(time.monotonic()-a,1), r.outcome, r.clearer, flush=True)
system = deep.RULES["Згода"]
answers = ["Так, давай", "Ні, не треба", "Так, але додай ще про ціни в Польщі", "А що ти думаєш про мого шефа?", "ок", "Давай, тільки коротко"]
for t in answers:
    contents=[model.Turn("user","Хочу зрозуміти, чи варто переїжджати до Кракова з двома дітьми."),
              model.Turn("model","Можу дослідити це глибше: подивлюсь вартість життя, школи і ринок праці в Кракові. Шукати?"),
              model.Turn("user",t)]
    a=time.monotonic(); c=llm.generate_json(system, contents, DeepConsent, None); print("DeepConsent", round(time.monotonic()-a,1), c.answer, flush=True)
