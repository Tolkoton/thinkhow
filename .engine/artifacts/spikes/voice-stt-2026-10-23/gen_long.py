import json, sys
from google import genai
from google.genai import types as t
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
paras = []
topics = ["переїзд до іншої країни заради роботи", "відкриття власної справи", "вступ до магістратури у 35 років", "продаж квартири і купівля будинку за містом", "зміна професії з юриста на програміста", "запрошення в стартап на меншу зарплату", "догляд за літніми батьками і кар'єра"]
for i, tp in enumerate(topics * 2):
    r = c.models.generate_content(model="gemini-3.5-flash", contents=f"Напиши монолог людини українською (приблизно 140 слів, розмовно, від першої особи, без заголовків, без списків, один абзац), яка вголос розмірковує про рішення: {tp}. Варіант {i}. Лише текст монологу.")
    paras.append(r.text.strip().replace("\n", " ")); print(i, len(paras[-1].split()), flush=True)
json.dump({"uk": paras}, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
