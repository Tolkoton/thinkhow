"""The FastAPI application: the login layer, the routes, SSE, one error handler (F1, F2, F3; M3 A4).

The person comes only from the verified identity of the request, never from the address or a form.
"""

import json
import time
import uuid
from collections.abc import Awaitable, Callable, Iterator, Mapping, MutableMapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from thinkhow import knowledge, workspace
from thinkhow.access import CurrentUser, current_user
from thinkhow.facilitation import Facilitate
from thinkhow.knowledge import Card
from thinkhow.platform import log
from thinkhow.platform.config import Settings
from thinkhow.platform.identity import FixedIdentity, IapIdentity, IdentityError
from thinkhow.platform.speech import Speech, SpeechUnavailable
from thinkhow.platform.storage import Storage
from thinkhow.platform.tts import NoVoice, ScriptedTts, Tts, TtsUnavailable
from thinkhow.web import ui_text
from thinkhow.web.learning import learning_view
from thinkhow.web.method import caption, marks
from thinkhow.web.text import turn_html

HERE = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=HERE / "templates")
TEMPLATES.env.filters["turn_html"] = turn_html
Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
ASGIApp = Callable[
    [Scope, Callable[[], Awaitable[Message]], Callable[[Message], Awaitable[None]]], Awaitable[None]
]


@dataclass(frozen=True)
class Deps:
    storage: Storage
    identity: IapIdentity | FixedIdentity
    settings: Settings
    facilitate: Facilitate
    now: Callable[[], datetime]
    speech: Speech
    tts: Tts = field(default_factory=ScriptedTts)
    cards: Mapping[str, Card] = field(default_factory=dict)


def create_app(deps: Deps) -> FastAPI:
    """Flow: the app → the request log → static files → the routes → the one error handler."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(RequestLog)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    _routes(app, deps)
    _error_handlers(app, deps)
    return app


def _routes(app: FastAPI, deps: Deps) -> None:
    def person(request: Request) -> CurrentUser:
        """The login layer: identity → CurrentUser → profile.json (M3 A4)."""
        user = current_user(deps.identity.identify(request.headers), deps.settings)
        workspace.ensure_profile(deps.storage, user)
        return user

    User = Annotated[CurrentUser, Depends(person)]

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, user: User) -> Response:
        language = workspace.language(deps.storage, user)
        mine = workspace.list_topics(deps.storage, user)
        everyone = _all_topics(deps, user) if user.is_owner else []
        context = {"user": user, "mine": mine, "everyone": everyone, "language": language}
        return _page(request, "home.html", context, ui_text.catalog_name(language.code))

    @app.get("/language", response_class=HTMLResponse)
    def language_page(request: Request, user: User) -> Response:
        current = _current_code(deps, user)
        name = ui_text.catalog_name(current) if current else _browser_catalog(request)
        context = {"languages": workspace.LANGUAGES, "current": current}
        return _page(request, "language.html", context, name)

    @app.post("/language")
    def choose_language(user: User, code: Annotated[str, Form()]) -> Response:
        workspace.set_language(deps.storage, user, code)
        return RedirectResponse("/", status_code=303)

    @app.post("/topics")
    def new_topic(user: User, title: Annotated[str, Form()] = "") -> Response:
        topic_id = workspace.create_topic(deps.storage, user, title, deps.now())
        return RedirectResponse(f"/topics/{user.id}/{topic_id}", status_code=303)

    @app.get("/topics/{uid}/{topic_id}", response_class=HTMLResponse)
    def topic(request: Request, user: User, uid: str, topic_id: str) -> Response:
        name = ui_text.catalog_name(workspace.language(deps.storage, user).code)
        words = ui_text.texts(name)
        view = workspace.open_topic(deps.storage, user, workspace.TopicRef(uid, topic_id), deps.now())
        method = caption(view.routing, view.problem_map.phase_id, deps.cards, words)
        context = {"view": view, "own": user.id == uid, "method": method}
        context["voice"] = user.id == uid and workspace.has_voice(deps.storage, user)
        context["marks"] = marks(view.routing, deps.cards, words)
        context["js_text"] = {key[3:]: text for key, text in words.items() if key.startswith("js_")}
        return _page(request, "topic.html", context, name)

    @app.post("/topics/{uid}/{topic_id}/reply")
    def reply(
        user: User,
        uid: str,
        topic_id: str,
        text: Annotated[str, Form()] = "",
        spoken: Annotated[str, Form()] = "",
    ) -> Response:
        ref = workspace.TopicRef(uid, topic_id)
        events = workspace.reply(deps.storage, deps.facilitate, user, ref, text, deps.now(), spoken == "1")
        return _stream(events)

    @app.post("/topics/{uid}/{topic_id}/retry")
    def retry(user: User, uid: str, topic_id: str, spoken: Annotated[str, Form()] = "") -> Response:
        ref = workspace.TopicRef(uid, topic_id)
        return _stream(workspace.retry(deps.storage, deps.facilitate, user, ref, deps.now(), spoken == "1"))

    @app.post("/topics/{uid}/{topic_id}/delete")
    def delete(user: User, uid: str, topic_id: str) -> Response:
        workspace.delete_topic(deps.storage, user, workspace.TopicRef(uid, topic_id))
        return RedirectResponse("/", status_code=303)

    @app.post("/topics/{uid}/{topic_id}/voice")
    async def voice(request: Request, user: User, uid: str, topic_id: str) -> Response:
        """The recording's raw bytes → text; the model call runs in the thread pool, not on the event loop."""
        audio, mime = await request.body(), request.headers.get("content-type", "")
        ref = workspace.TopicRef(uid, topic_id)
        call = (deps.storage, deps.speech, user, ref, audio, mime)
        text = await run_in_threadpool(workspace.transcribe, *call)
        return JSONResponse({"text": text})

    @app.get("/learning", response_class=HTMLResponse)
    def learning(request: Request, user: User) -> Response:
        _owner_only(user)
        return _page(request, "learning.html", {"view": learning_view(deps.storage)}, LEARNING_LANGUAGE)

    @app.post("/learning/rollback/{rev}")
    def roll_back(user: User, rev: int) -> Response:
        _owner_only(user)
        knowledge.rollback(deps.storage, rev, user.email, deps.now())
        return RedirectResponse("/learning", status_code=303)

    @app.post("/speak")
    async def speak(user: User, text: Annotated[str, Form()]) -> Response:
        """A reply sentence → MP3 in the person's language; the synthesis runs in the thread pool."""
        audio = await run_in_threadpool(workspace.speak, deps.storage, deps.tts, user, text)
        return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


def _owner_only(user: CurrentUser) -> None:
    """The learning page is the owner's (G4): anyone else gets the same 404 as a foreign topic."""
    if not user.is_owner:
        raise workspace.TopicNotFound("the learning page is the owner's")


def _page(request: Request, template: str, context: dict[str, Any], name: str) -> Response:
    """A page in the catalog `name`: its words as `ui`, its language and direction on <html> (task 208)."""
    extra = {"ui": ui_text.texts(name), "lang": name, "dir": ui_text.direction(name)}
    return TEMPLATES.TemplateResponse(request, template, context | extra)


def _browser_catalog(request: Request) -> str:
    return ui_text.from_header(request.headers.get("accept-language"))


def _current_code(deps: Deps, user: CurrentUser) -> str:
    """The chosen code to mark in the list, or "" before the first choice (the language page needs none)."""
    try:
        return workspace.language(deps.storage, user).code
    except workspace.NoLanguage:
        return ""


def _all_topics(deps: Deps, user: CurrentUser) -> list[workspace.TopicSummary]:
    """The owner's list (G4): the one reader of all people, called only for is_owner."""
    now = deps.now()
    refs = workspace.all_topics_for_learning(deps.storage)
    return [workspace.TopicSummary(r, workspace.open_topic(deps.storage, user, r, now).title) for r in refs]


def _stream(events: Iterator[workspace.ReplyEvent]) -> Response:
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(_sse(events), media_type="text/event-stream", headers=headers)


def _sse(events: Iterator[workspace.ReplyEvent]) -> Iterator[str]:
    """Each event: `event:` and one `data:` line of JSON (Q3); any failure mid-stream → `failed Internal`."""
    try:
        for event in events:
            yield _sse_event(event)
    except Exception as exc:
        log.log_event("stream_error", severity="ERROR", error=type(exc).__name__)
        yield _format("failed", {"reason": "Internal"})


def _sse_event(event: workspace.ReplyEvent) -> str:
    if isinstance(event, workspace.Saved):
        return _format("saved", {"turn": event.turn_no})
    if isinstance(event, workspace.Delta):
        return _format("delta", {"text": event.text})
    if isinstance(event, workspace.Answered):
        return _format("answered", {"turn": event.turn_no})
    return _format("failed", {"reason": event.reason})


def _format(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


MESSAGES: list[tuple[type[Exception], int, str]] = [
    (workspace.TopicNotFound, 404, "err_topic_not_found"),
    (workspace.PendingAnswer, 409, "err_pending"),
    (workspace.NothingToRetry, 409, "err_nothing_to_retry"),
    (IdentityError, 401, "err_login"),
    (SpeechUnavailable, 502, "err_not_recognized"),
    (NoVoice, 409, "err_no_voice"),
    (TtsUnavailable, 502, "err_not_voiced"),
]
Handler = Callable[[Request, Exception], Awaitable[Response]]
# The learning page and its rollback speak Ukrainian, as the Knowledge (M3 A5; learning-loop S3 Q6).
LEARNING_LANGUAGE = "uk"
ROLLBACK_MESSAGES: list[tuple[type[Exception], int, str]] = [
    (knowledge.AlreadyRolledBack, 409, "Цю зміну вже відкочено."),
    (knowledge.NotRollbackable, 409, "Цю ревізію не можна відкотити: вона не змінювала нотаток."),
    (knowledge.UnknownRevision, 404, "Такої ревізії немає."),
]


def _error_handlers(app: FastAPI, deps: Deps) -> None:
    """One place turns errors into a fragment of the page (M3 A4), in the person's language (task 208)."""
    for kind, status, key in MESSAGES:
        app.add_exception_handler(kind, _fixed(deps, status, key))
    for kind, status, text in ROLLBACK_MESSAGES:
        app.add_exception_handler(kind, _text_fragment(status, text))
    app.add_exception_handler(workspace.NoLanguage, _no_language(deps))
    bad_request = _bad_request(deps)
    app.add_exception_handler(ValueError, bad_request)
    app.add_exception_handler(RequestValidationError, bad_request)
    app.add_exception_handler(Exception, _fixed(deps, 500, "err_internal"))


def _words(deps: Deps, request: Request) -> Mapping[str, str]:
    """The language the person chose; before a choice, or with no person known, the browser's."""
    try:
        user = current_user(deps.identity.identify(request.headers), deps.settings)
        return ui_text.texts(ui_text.catalog_name(workspace.language(deps.storage, user).code))
    except Exception:  # an error page must not fail on the way to its words
        return ui_text.texts(_browser_catalog(request))


def _fixed(deps: Deps, status: int, key: str) -> Handler:
    async def handler(request: Request, exc: Exception) -> Response:
        return _fragment(status, _words(deps, request)[key])

    return handler


def _text_fragment(status: int, text: str) -> Handler:
    async def handler(request: Request, exc: Exception) -> Response:
        return _fragment(status, text)

    return handler


def _no_language(deps: Deps) -> Handler:
    async def handler(request: Request, exc: Exception) -> Response:
        """A page leads to the language choice; any other request gets a fragment it can show (F13 S1 Q5)."""
        if request.method == "GET":
            return RedirectResponse("/language", status_code=303)
        return _fragment(409, _words(deps, request)["err_choose_language"])

    return handler


def _bad_request(deps: Deps) -> Handler:
    async def handler(request: Request, exc: Exception) -> Response:
        return _fragment(400, _words(deps, request)[_bad_request_key(request)])

    return handler


def _bad_request_key(request: Request) -> str:
    path = request.url.path
    if request.method == "POST" and path == "/language":
        return "err_unknown_language"
    if request.method == "POST" and path == "/topics":
        return "err_empty_title"
    if request.method == "POST" and path.endswith("/voice"):
        return "err_recording_rejected"
    if request.method == "POST" and path == "/speak":
        return "err_speak_rejected"
    if request.method == "POST" and path.endswith("/reply"):
        return "err_empty_reply"
    return "err_not_accepted"


def _fragment(status: int, text: str) -> Response:
    return HTMLResponse(f'<p class="error">{_escape(text)}</p>', status_code=status)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class RequestLog:
    """Pure ASGI: one request id for the request (SSE thread too), one `http_request` line at the end."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Callable[[], Awaitable[Message]],
        send: Callable[[Message], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = log.request_id.set(_request_id(scope))
        started, status = time.monotonic(), [500]

        async def watch(message: Message) -> None:
            if message["type"] == "http.response.start":
                status[0] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, watch)
        finally:
            route = scope.get("route")
            log.log_event(
                "http_request",
                method=scope["method"],
                route=getattr(route, "path", scope["path"]),
                status=status[0],
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            log.request_id.reset(token)


def _request_id(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name == b"x-cloud-trace-context":
            return str(value.decode("latin-1").split("/")[0])
    return uuid.uuid4().hex
