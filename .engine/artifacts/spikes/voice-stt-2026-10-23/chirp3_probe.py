from google.api_core.client_options import ClientOptions
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech as cs
c = SpeechClient(client_options=ClientOptions(api_endpoint="eu-speech.googleapis.com"))
cfg = cs.RecognitionConfig(auto_decoding_config=cs.AutoDetectDecodingConfig(), language_codes=["uk-UA"], model="chirp_3")
try:
    r = c.recognize(request=cs.RecognizeRequest(recognizer="projects/pocket-lawyer-431614/locations/eu/recognizers/_", config=cfg, content=b"\x00"*3200))
    print(r)
except Exception as e:
    print(type(e).__name__, str(e)[:400])
