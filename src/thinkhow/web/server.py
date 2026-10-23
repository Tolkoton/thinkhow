"""The FastAPI application: the login layer, the routes, SSE, one error handler (F1, F2, F3; M3 A4).

The person comes only from the verified identity of the request, never from the address or a form.
"""

import json
import time
import uuid
from collections.abc import Awaitable, Callable, Iterator, MutableMapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from thinkhow import workspace
from thinkhow.access import CurrentUser, current_user
from thinkhow.facilitation import Facilitate
from thinkhow.platform import log
from thinkhow.platform.config import Settings
from thinkhow.platform.identity import FixedIdentity, IapIdentity, IdentityError
from thinkhow.platform.storage import Storage

HERE = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=HERE / "templates")
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


def create_app(deps: Deps) -> FastAPI:
    """Flow: the app → the request log → static files → the routes → the one error handler."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(RequestLog)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    _routes(app, deps)
    _error_handlers(app)
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
        return TEMPLATES.TemplateResponse(request, "home.html", context)

    @app.get("/language", response_class=HTMLResponse)
    def language_page(request: Request, user: User) -> Response:
        context = {"languages": workspace.LANGUAGES, "current": _current_code(deps, user)}
        return TEMPLATES.TemplateResponse(request, "language.html", context)

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
        workspace.language(deps.storage, user)
        view = workspace.open_topic(deps.storage, user, workspace.TopicRef(uid, topic_id), deps.now())
        context = {"view": view, "own": user.id == uid}
        return TEMPLATES.TemplateResponse(request, "topic.html", context)

    @app.post("/topics/{uid}/{topic_id}/reply")
    def reply(user: User, uid: str, topic_id: str, text: Annotated[str, Form()] = "") -> Response:
        ref = workspace.TopicRef(uid, topic_id)
        return _stream(workspace.reply(deps.storage, deps.facilitate, user, ref, text, deps.now()))

    @app.post("/topics/{uid}/{topic_id}/retry")
    def retry(user: User, uid: str, topic_id: str) -> Response:
        ref = workspace.TopicRef(uid, topic_id)
        return _stream(workspace.retry(deps.storage, deps.facilitate, user, ref, deps.now()))

    @app.post("/topics/{uid}/{topic_id}/close")
    def close(user: User, uid: str, topic_id: str) -> Response:
        workspace.close_session(deps.storage, user, workspace.TopicRef(uid, topic_id), deps.now())
        return RedirectResponse(f"/topics/{uid}/{topic_id}", status_code=303)


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


NOT_ACCEPTED = "Запит не прийнято."
MESSAGES: list[tuple[type[Exception], int, str]] = [
    (workspace.TopicNotFound, 404, "Тему не знайдено."),
    (workspace.PendingAnswer, 409, "Спершу дочекайтеся відповіді або натисніть «Спробуйте ще раз»."),
    (workspace.NothingToRetry, 409, "Немає репліки, на яку треба відповісти."),
    (IdentityError, 401, "Потрібно увійти через Google."),
]


def _error_handlers(app: FastAPI) -> None:
    """One place turns errors into a fragment of the page (M3 A4)."""
    for kind, status, text in MESSAGES:
        app.add_exception_handler(kind, _fixed(status, text))
    app.add_exception_handler(workspace.NoLanguage, _no_language)
    app.add_exception_handler(ValueError, _bad_request)
    app.add_exception_handler(RequestValidationError, _bad_request)
    app.add_exception_handler(Exception, _fixed(500, "Щось пішло не так — спробуйте ще раз."))


def _fixed(status: int, text: str) -> Callable[[Request, Exception], Awaitable[Response]]:
    async def handler(request: Request, exc: Exception) -> Response:
        return _fragment(status, text)

    return handler


async def _no_language(request: Request, exc: Exception) -> Response:
    """A page leads to the language choice; any other request gets a fragment it can show (F13 S1 Q5)."""
    if request.method == "GET":
        return RedirectResponse("/language", status_code=303)
    return _fragment(409, "Спершу оберіть мову (сторінка «Мова»).")


async def _bad_request(request: Request, exc: Exception) -> Response:
    path = request.url.path
    if request.method == "POST" and path == "/language":
        return _fragment(400, "Такої мови немає в переліку.")
    if request.method == "POST" and path == "/topics":
        return _fragment(400, "Назва теми порожня.")
    if request.method == "POST" and path.endswith("/reply"):
        return _fragment(400, "Порожню репліку не надіслано.")
    return _fragment(400, NOT_ACCEPTED)


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
