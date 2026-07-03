import os

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.rate_limit import limiter
from app.routers import auth as auth_router
from app.routers import dashboard as dashboard_router
from app.routers import landing as landing_router
from app.routers import periods as periods_router
from app.routers import projects as projects_router
from app.routers import tickets as tickets_router
from app.routers import admin as admin_router

BASE_DIR = os.path.dirname(__file__)

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is required to sign session cookies. "
        "Set it before starting the app -- there is no insecure fallback."
    )

# TestClient/local http dev can opt out via SESSION_COOKIE_SECURE=false; Render serves https only.
COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() != "false"

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=COOKIE_SECURE,
    same_site="lax",
    max_age=60 * 60 * 24 * 7,  # sessions expire after 7 days
)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.include_router(landing_router.router)
app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(periods_router.router)
app.include_router(projects_router.router)
app.include_router(tickets_router.router)
app.include_router(admin_router.router)


@app.exception_handler(StarletteHTTPException)
async def browser_friendly_errors(request: Request, exc: StarletteHTTPException):
    if request.headers.get("hx-request") == "true" and exc.status_code == 401:
        # htmx swallows redirects normales; HX-Redirect fuerza navegacion completa
        return Response(status_code=200, headers={"HX-Redirect": "/login"})
    wants_html = "text/html" in request.headers.get("accept", "")
    if wants_html:
        if exc.status_code == 401:
            return RedirectResponse("/login", status_code=303)
        if exc.status_code in (403, 404):
            return RedirectResponse("/dashboard", status_code=303)
    return await http_exception_handler(request, exc)


@app.get("/health")
def health():
    return {"status": "ok"}

