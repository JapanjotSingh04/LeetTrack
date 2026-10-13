"""Production-mode behaviour (CORS allowlist, startup validation, docs hidden).

App settings such as CORS are read at import time, so each scenario runs in a
fresh Python process with its own environment.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

PROD_ENV = {
    "APP_ENV": "production",
    "JWT_SECRET": "x" * 48,
    "DB_SSL_CA_PEM": "-----BEGIN CERTIFICATE-----\nplaceholder\n-----END CERTIFICATE-----",
    "CORS_ORIGINS": "https://leettrack-demo.vercel.app",
}


def run(script, **env):
    full = {**os.environ, **PROD_ENV, **env}
    full.pop("PYTEST_CURRENT_TEST", None)
    # conftest's mysql stub is not active in a subprocess, so register it here.
    prelude = textwrap.dedent(f"""
        import sys; sys.path.insert(0, {str(BACKEND / 'tests')!r}); import conftest  # noqa
        sys.path.insert(0, {str(BACKEND)!r})
    """)
    return subprocess.run([sys.executable, "-W", "ignore", "-c", prelude + textwrap.dedent(script)],
                          env=full, capture_output=True, text=True, timeout=60)


def test_production_hides_api_docs_and_schema():
    out = run("""
        import main
        print(main.app.docs_url, main.app.redoc_url, main.app.openapi_url)
    """)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["None", "None", "None"]


def test_production_cors_allows_only_the_deployed_frontend():
    out = run("""
        from fastapi.testclient import TestClient
        import main
        with TestClient(main.app) as c:
            ok = c.options("/api/auth/login", headers={"Origin": "https://leettrack-demo.vercel.app",
                "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
            bad = c.options("/api/auth/login", headers={"Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
            local = c.options("/api/auth/login", headers={"Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
            print(ok.headers.get("access-control-allow-origin"), ok.headers.get("access-control-allow-credentials"))
            print(bad.headers.get("access-control-allow-origin"))
            print(local.headers.get("access-control-allow-origin"))
    """)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.strip().splitlines()
    assert lines[0] == "https://leettrack-demo.vercel.app true"
    assert lines[1] == "None" and lines[2] == "None"


def test_production_refuses_wildcard_or_localhost_cors():
    for bad in ("*", "http://localhost:5173", ""):
        out = run("""
            from fastapi.testclient import TestClient
            import main
            with TestClient(main.app):
                pass
        """, CORS_ORIGINS=bad)
        assert out.returncode != 0, f"started with CORS_ORIGINS={bad!r}"
        assert "CORS_ORIGINS" in out.stderr


def test_production_refuses_missing_secret_or_tls():
    out = run("""
        from fastapi.testclient import TestClient
        import main
        with TestClient(main.app):
            pass
    """, JWT_SECRET="short")
    assert out.returncode != 0 and "JWT_SECRET" in out.stderr
    out = run("""
        from fastapi.testclient import TestClient
        import main
        with TestClient(main.app):
            pass
    """, DB_SSL_CA_PEM="", DB_SSL_CA="")
    assert out.returncode != 0 and "DB_SSL_CA" in out.stderr


def test_production_cookies_are_secure_and_httponly():
    out = run("""
        import auth
        print(auth.cookie_options()["secure"], auth.cookie_options()["httponly"], auth.csrf_cookie_options()["httponly"])
    """)
    assert out.stdout.split() == ["True", "True", "False"]
