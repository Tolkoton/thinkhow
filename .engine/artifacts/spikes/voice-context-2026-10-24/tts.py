"""Synthetic Ukrainian speech with German/English names (Gemini TTS, Vertex global; text only, no personal data).

`spoken_lat` — the names written in Latin script, so the voice says them as in their own language;
`spoken_cyr` — the names spelt the way a Ukrainian speaker says them, to stand in for an accented voice;
`spoken_acc` — spelt the way the model misheard the owner (task 304: «Меттлі-Штанд»), a heavier accent.
"""
import json, sys, wave, pathlib
from google import genai
from google.genai import types as t
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="global")
texts = json.load(open(sys.argv[1])); out = pathlib.Path(sys.argv[2]); out.mkdir(exist_ok=True)
for kind in sys.argv[3:] or ("spoken_lat", "spoken_cyr"):
    for key, text in texts[kind].items():
        r = c.models.generate_content(model="gemini-2.5-flash-tts",
            contents=f"Read aloud in Ukrainian, naturally, at a calm conversational pace. Say exactly this sentence once, nothing else: {text}",
            config=t.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=t.SpeechConfig(voice_config=t.VoiceConfig(prebuilt_voice_config=t.PrebuiltVoiceConfig(voice_name="Kore")))))
        blob = r.parts[0].inline_data if r.parts else None
        assert blob is not None and blob.data is not None
        pcm = blob.data
        name = f"{kind.split('_')[1]}-{key}"
        with wave.open(str(out / f"{name}.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
        print(name, len(pcm) / 48000, "s")
