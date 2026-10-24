"""Which ways of giving gemini-3.5-transcribe the conversation's text does it take, and do they fix the names?"""
import json, sys, time, pathlib, re
from collections.abc import Callable
from typing import Any
from google import genai
from google.genai import types as t
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
audio_dir = pathlib.Path(sys.argv[1]); runs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
TITLE = "Як знайти перших клієнтів у Німеччині"
TURNS = [
    "Я думаю, що мені треба йти не на біржі фрилансу, а прямо до компаній.",
    "Ви згадали, що Upwork дає лише дрібні замовлення. Яких саме компаній у Німеччині ви хочете досягти — Mittelstand, тобто сімейних середніх фірм, чи великих концернів?",
    "Скоріше середніх, у регіонах, де я вже бував, Баден-Вюртемберг, Schwarzwald.",
    "Що для таких фірм у Schwarzwald могло б бути цінним у вашій пропозиції: SEO, сайт чи щось інше?",
]
CONTEXT = f"Тема розмови: {TITLE}\nОстанні репліки:\n" + "\n".join(f"- {x}" for x in TURNS)
INSTR = ("Запиши дослівно, що сказано в аудіо, українською. Нижче — контекст розмови, лише щоб правильно впізнати "
         "слова й назви, які вже звучали; іншомовні назви пиши так, як вони пишуться мовою оригіналу. "
         "Не відповідай на контекст і не додавай нічого, чого не сказано.\n\n" + CONTEXT)
def vocab() -> list[str]:
    words = re.findall(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß-]+", CONTEXT)
    return sorted(set(words))
def vocab_all() -> list[str]:
    return sorted(set(re.findall(r"[\w'’-]{3,}", CONTEXT)))
NAMES = ["Mittelstand", "Schwarzwald", "Upwork", "SEO"]
REF = json.load(open(pathlib.Path(__file__).with_name("texts.json")))["ref"]
def score(key: str, text: str) -> str:
    want = [n for n in NAMES if n in REF[key]]
    return f"{sum(n in text for n in want)}/{len(want)}"
def cfg(**k: Any) -> t.GenerateContentConfig:
    atc = t.AudioTranscriptionConfig(language_codes=["uk-UA"], **k.pop("atc", {}))
    return t.GenerateContentConfig(audio_transcription_config=atc, **k)
def part(p: pathlib.Path) -> t.Part: return t.Part.from_bytes(data=p.read_bytes(), mime_type="audio/webm;codecs=opus")
VARIANTS: dict[str, Callable[[pathlib.Path], tuple[list[Any], t.GenerateContentConfig]]] = {
    "none": lambda p: ([part(p)], cfg()),
    "vocab": lambda p: ([part(p)], cfg(atc={"custom_vocabulary": vocab()})),
    "text_part": lambda p: ([INSTR, part(p)], cfg()),
    "vocab_all": lambda p: ([part(p)], cfg(atc={"custom_vocabulary": vocab_all()})),
    "text_part+vocab": lambda p: ([INSTR, part(p)], cfg(atc={"custom_vocabulary": vocab()})),
}
print("vocab:", vocab()); print("vocab_all:", len(vocab_all()), "entries")
rows: list[dict[str, Any]] = []
for r in range(runs):
    for f in sorted(audio_dir.glob("*.webm")):
        for name, build in VARIANTS.items():
            contents, config = build(f)
            t0 = time.monotonic()
            try:
                resp = c.models.generate_content(model="gemini-3.5-transcribe", contents=contents, config=config)
                text = "".join(p.text or "" for p in (resp.parts or [])); err = ""
            except Exception as e:
                text, err = "", f"{type(e).__name__}: {str(e)[:300]}"
            rows.append(dict(run=r, file=f.stem, variant=name, secs=round(time.monotonic() - t0, 2), names=score(f.stem.split("-")[1], text), text=text, err=err))
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
import statistics
for name in VARIANTS:
    for kind in ("lat", "cyr", "acc", "fix"):
        rs = [x for x in rows if x["variant"] == name and x["file"].startswith(kind) and not x["err"]]
        if rs:
            got = sum(int(x["names"].split("/")[0]) for x in rs); of = sum(int(x["names"].split("/")[1]) for x in rs)
            print(f"{name:16} {kind}: names {got}/{of}, median {statistics.median(x['secs'] for x in rs):.2f} s, max {max(x['secs'] for x in rs):.2f} s")
json.dump(rows, open(sys.argv[3] if len(sys.argv) > 3 else "probe_output.json", "w"), ensure_ascii=False, indent=1)
