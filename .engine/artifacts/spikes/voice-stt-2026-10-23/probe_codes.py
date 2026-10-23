import sys
from google import genai
from google.genai import types as t
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
data = open(sys.argv[1], "rb").read()
for code in ["xx-XX", "uk-UA", "rup-BG", "ceb", "cmn-Hans-CN"]:
    try:
        r = c.models.generate_content(model="gemini-3.5-transcribe", contents=[t.Part.from_bytes(data=data, mime_type="audio/webm;codecs=opus")],
            config=t.GenerateContentConfig(audio_transcription_config=t.AudioTranscriptionConfig(language_codes=[code])))
        print(code, "OK", "".join(p.text or "" for p in (r.parts or []))[:60])
    except Exception as e:
        print(code, "ERR", type(e).__name__, str(e)[:160])
