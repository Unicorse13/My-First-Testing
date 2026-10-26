"""Same-origin ASGI application. Explicit demo mode is opt-in."""
import hmac
import logging
import os
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import core, workflows
from .core import Input
from .db import connect, initialize
from .security import (audit, current_user, demo_mode, hash_password, new_session,
                       public_user, token_hash, verify_password)

logger = logging.getLogger('permitsnj.security')


@asynccontextmanager
async def lifespan(app):
    initialize()
    if not demo_mode():
        with connect() as db:
            if db.execute("SELECT 1 FROM users WHERE email LIKE '%@demo.permitsnj.test' LIMIT 1").fetchone():
                raise RuntimeError('Refusing non-demo startup with published demo accounts. Use a clean database and provision real accounts securely.')
    yield


app = FastAPI(title='PermitsNJ demonstration API', version='0.1.0', lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[x.strip() for x in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',') if x.strip()])

# Single-instance limiter: production multi-instance deployment requires a shared store.
_attempts = defaultdict(deque)
_limiter_lock = threading.Lock()


def limited(key, limit, seconds):
    stamp = time.monotonic()
    with _limiter_lock:
        queue = _attempts[key]
        while queue and queue[0] <= stamp - seconds:
            queue.popleft()
        if len(queue) >= limit:
            return True
        queue.append(stamp)
        # Bound memory even when requests arrive from many addresses.
        if len(_attempts) > 10000:
            stale = [k for k, v in _attempts.items() if not v or v[-1] < stamp - 900]
            for k in stale:
                del _attempts[k]
    return False


@app.middleware('http')
async def security_controls(request: Request, call_next):
    if request.url.path.startswith('/api/'):
        peer = request.client.host if request.client else 'unknown'
        if limited(('all', peer), 600, 60):
            return JSONResponse({'detail': 'Too many requests. Please try again shortly.'}, status_code=429, headers={'Retry-After': '60'})
        size = request.headers.get('content-length')
        if size and (not size.isdigit() or int(size) > 65536):
            return JSONResponse({'detail': 'Request body is too large.'}, status_code=413)
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            # Count streamed bytes too; Content-Length alone is not a security boundary.
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 65536:
                    return JSONResponse({'detail': 'Request body is too large.'}, status_code=413)
            request._body = bytes(raw)
            origin = request.headers.get('origin')
            allowed = os.getenv('APP_ORIGIN', '').rstrip('/')
            same_origin = not origin or urlsplit(origin).netloc == request.headers.get('host') and urlsplit(origin).scheme == request.url.scheme
            if origin and not same_origin and origin.rstrip('/') != allowed:
                logger.warning('Rejected cross-origin mutation path=%s', request.url.path)
                return JSONResponse({'detail': 'Cross-origin requests are not allowed.'}, status_code=403)
            if request.url.path != '/api/auth/login':
                try:
                    user = current_user(request)
                except HTTPException as exc:
                    return JSONResponse({'detail': exc.detail}, status_code=exc.status_code)
                csrf = request.headers.get('x-csrf-token', '')
                if not csrf or not hmac.compare_digest(csrf, user['csrf_token']):
                    logger.warning('Rejected CSRF mutation user=%s path=%s', user['id'], request.url.path)
                    return JSONResponse({'detail': 'Security token is missing or expired. Refresh and try again.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    if os.getenv('SESSION_SECURE', 'true').lower() == 'true':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Avoid echoing passwords or arbitrary submitted fields in validation errors.
    errors = '; '.join(f'{".".join(str(x) for x in e["loc"][1:])}: {e["msg"]}' for e in exc.errors())
    return JSONResponse({'detail': errors or 'Invalid request.'}, status_code=422)


@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error(request, exc):
    logger.warning('Integrity constraint rejected request path=%s', request.url.path)
    return JSONResponse({'detail': 'This change conflicts with an existing record or integrity rule.'}, status_code=409)


@app.exception_handler(sqlite3.OperationalError)
async def database_error(request, exc):
    logger.error('Database operation failed path=%s type=%s', request.url.path, type(exc).__name__)
    return JSONResponse({'detail': 'Database unavailable. Please retry shortly.'}, status_code=503)


class Login(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


@app.get('/api/health')
def health():
    with connect() as db:
        db.execute('SELECT 1').fetchone()
    return {'status': 'ok', 'demo': demo_mode()}


@app.post('/api/auth/login')
def login(body: Login, request: Request, response: Response):
    peer = request.client.host if request.client else 'unknown'
    if limited(('login', peer), 20, 300) or limited(('account', body.email.lower()), 15, 300):
        raise HTTPException(429, 'Too many sign-in attempts. Try again in five minutes.')
    with connect() as db:
        user = db.execute('SELECT * FROM users WHERE lower(email)=?', (body.email.lower(),)).fetchone()
        # Equal-cost comparison even for nonexistent accounts.
        if not verify_password(body.password, user['password_hash'] if user else _dummy_hash):
            logger.warning('Sign-in rejected peer=%s', peer)
            raise HTTPException(401, 'Email or password is incorrect.')
        token, csrf = new_session(db, user)
        audit(db, dict(user), 'user', user['id'], 'signed_in', {})
    response.set_cookie('permits_session', token, httponly=True,
                        secure=os.getenv('SESSION_SECURE', 'true').lower() == 'true',
                        samesite='lax', max_age=28800, path='/')
    return {'user': public_user(user), 'csrf_token': csrf, 'demo': demo_mode()}


_dummy_hash = hash_password('timing-only-' + os.urandom(16).hex())


@app.get('/api/auth/me')
def me(user=Depends(current_user)):
    return {'user': public_user(user), 'csrf_token': user['csrf_token'], 'demo': demo_mode()}


@app.post('/api/auth/logout')
def logout(request: Request, response: Response, user=Depends(current_user)):
    with connect() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(request.cookies.get('permits_session', '')),))
        audit(db, user, 'user', user['id'], 'signed_out', {})
    response.delete_cookie('permits_session', path='/', secure=os.getenv('SESSION_SECURE', 'true').lower() == 'true', httponly=True, samesite='lax')
    return {'message': 'Signed out.'}


app.include_router(core.router, prefix='/api')
app.include_router(workflows.router, prefix='/api')
from .reference import router as reference_router
app.include_router(reference_router, prefix='/api')

# API 404s must never fall through to the frontend.
@app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'])
def api_not_found(path):
    raise HTTPException(404, 'API endpoint not found.')


static_dir = Path(__file__).resolve().parent.parent / 'frontend' / 'dist'
if static_dir.is_dir():
    app.mount('/', StaticFiles(directory=str(static_dir), html=True), name='frontend')
