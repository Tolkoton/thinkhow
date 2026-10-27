"""The person's turns for the conversation-mode smoke and live check (task 308): Cloud TTS `eu`,
Chirp 3 HD voice Charon (not the replies' Kore), MP3. Text only, no personal data. Run once:
`uv run python tests/fixtures/voice/conversation/make.py`; writes `<lang>-<n>.mp3`, `lines.json` here."""

import base64
import json
from pathlib import Path
from typing import Any

import google.auth
import httpx
from google.auth.transport.requests import Request

HERE = Path(__file__).resolve().parent
LINES = {
    "uk-UA": [
        "Я думаю, чи варто мені переїхати з Києва до Львова разом із моєю невеликою командою розробників.",
        "Давай перший спосіб.",
        "А скільки зараз коштує оренда офісу на десять людей у Львові?",
        "Мені важливо, щоб команда не розбіглася і щоб витрати зросли не більше ніж на "
        "п'ятнадцять відсотків.",
        "Так, досліди це глибше.",
        "Дякую. Що мені варто перевірити першим?",
    ],
    "pl-PL": [
        "Zastanawiam się, czy przenieść moją małą firmę z Warszawy do Krakowa.",
        "Wybieram pierwszy sposób.",
        "Ile teraz kosztuje wynajem biura dla dziesięciu osób w Krakowie?",
        "Zależy mi, żeby zespół został ze mną, a koszty wzrosły najwyżej o piętnaście procent.",
        "Tak, zbadaj to dokładniej.",
        "Dziękuję. Co powinienem sprawdzić najpierw?",
    ],
}


def main() -> None:
    credentials: Any = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])[0]
    credentials.refresh(Request())
    headers = {"Authorization": f"Bearer {credentials.token}"}
    for language, lines in LINES.items():
        for n, text in enumerate(lines, 1):
            body = {
                "input": {"text": text},
                "voice": {"languageCode": language, "name": f"{language}-Chirp3-HD-Charon"},
                "audioConfig": {"audioEncoding": "MP3"},
            }
            url = "https://eu-texttospeech.googleapis.com/v1/text:synthesize"
            r = httpx.post(url, headers=headers, json=body, timeout=60)
            r.raise_for_status()
            (HERE / f"{language}-{n}.mp3").write_bytes(base64.b64decode(r.json()["audioContent"]))
            print(language, n, "ok")
    (HERE / "lines.json").write_text(json.dumps(LINES, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
