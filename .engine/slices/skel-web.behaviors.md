# skel-web — the builder's readings of the tester's open questions (no held test)

- Q4 — «Спробуйте ще раз» is in the HTML always on one's own topic, hidden unless `awaiting_answer`; `showRetry()` unhides it.
- Q5 — `showError` gets the text of the `<p class="error">` fragment (via `DOMParser`/`textContent`), not raw HTML.
- Q6 — NothingToRetry → 409 «Немає репліки, на яку треба відповісти.»
- Q7 — `http_request` keys are flat: `method`, `route`, `status`, `latency_ms`.
- Q8 — each session is a `<section>` with heading «Сесія N»; a closed one adds «(завершено)».
- `app.py` exposes `app` through module `__getattr__` (built on first access from `os.environ`), so importing `build_deps` needs no environment; `uvicorn thinkhow.web.app:app` reads it the same way.
