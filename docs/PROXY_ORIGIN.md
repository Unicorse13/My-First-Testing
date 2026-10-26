# Codespaces forwarded-origin fix

## Observed failure

The browser used a private Codespaces HTTPS URL. The application's own diagnostic showed the forwarded request contained `Origin: http://localhost:8000` and `Host: localhost:8000`. The configured public `APP_ORIGIN` matched the browser. Re-entering that address or resetting credentials therefore could not resolve this failure.

Uvicorn enables proxy-header processing by default for trusted loopback connections. An `X-Forwarded-Proto: https` header changes the ASGI request scheme while leaving the rewritten HTTP Origin and Host untouched. The application correctly rejects that inconsistent origin comparison. We reproduced a 403 with these headers against an actual local Uvicorn process before the fix.

This describes the observed Codespaces forwarding path, not a guarantee about headers in every GitHub deployment. Uvicorn's behavior is documented in its [HTTP settings](https://www.uvicorn.org/settings/#http).

## Scoped correction

`scripts/start-demo.sh` passes `--no-proxy-headers` to Uvicorn only when `CODESPACE_NAME` is set. This keeps the HTTP scheme, Host and Origin consistent on the internal proxy-to-application hop. The private browser connection still uses HTTPS. `SESSION_SECURE=true` retains Secure/HttpOnly/SameSite cookies and HSTS; the explicit public origin remains configured, CSRF checks remain required, and unrelated origins remain rejected. No wildcard origin or CORS exception was added. Non-Codespaces startup and production proxy configuration are unchanged.

The application sees the internal proxy address in access logs and IP rate limits in this demo configuration. Keep this port private; this is a single-instance synthetic demonstration, not a production proxy recipe. Production requires its own reviewed proxy/IP trust and public URL configuration.

## Verification

- A real Uvicorn subprocess with default proxy processing returned 403 for the screenshot's request pattern.
- The same request returned 200 with `--no-proxy-headers`, retaining a Secure session cookie. Authenticated permit reads and CSRF-authorized logout succeeded; missing CSRF and an unrelated origin returned 403.
- The actual Codespaces startup script was exercised locally with `CODESPACE_NAME` set. Its process arguments contained the new flag and the same forwarded request logged in successfully.
- Six integration regression tests in `backend/tests/test_codespaces_proxy.py` use Uvicorn's real proxy middleware to cover rejection before the fix, login and scoped data after the fix, successful protected mutations, CSRF rejection, foreign-origin rejection with spoofed forwarding headers, exact public origin support and strict non-demo diagnostics.

These are local reproductions of the observed forwarding behavior. A successful login in the user's hosted Codespace still requires pulling the update and restarting there; local validation is not a claim that the hosted instance has already updated.

## Apply to an existing Codespace

In its terminal:

```bash
git pull --ff-only origin main && bash scripts/restart-demo.sh "$(cat data/public-origin.txt)"
```

After the ready message, refresh the application and select **Enter demo workspace**. This uses the saved public address and the Codespace context; no dependency reinstall, frontend rebuild or container rebuild is needed for this server-only correction.
