import json, sys, wave, time
from google import genai
from google.genai import types as t
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="global")
texts = json.load(open(sys.argv[1])); out = sys.argv[2]
for lang, items in texts.items():
    for i, text in enumerate(items):
        r = c.models.generate_content(model="gemini-2.5-flash-tts", contents=f"Read aloud naturally, at a calm conversational pace: {text}",
            config=t.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=t.SpeechConfig(voice_config=t.VoiceConfig(prebuilt_voice_config=t.PrebuiltVoiceConfig(voice_name="Kore")))))
        pcm = r.candidates[0].content.parts[0].inline_data.data
        with wave.open(f"{out}/{lang}{i}.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
        print(lang, i, len(pcm)/48000, "s")
