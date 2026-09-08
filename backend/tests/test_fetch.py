import gzip
import socket

import httpx
import pytest
from app.config import manifests
from app.security.fetch import (
    Fetcher,
    FetchError,
    PinnedBackend,
    bounded_body,
    public_addresses,
    retry_seconds,
    validate_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.lidl.it/",
        "https://www.lidl.it:444/",
        "https://u:p@www.lidl.it/",
        "https://www.lidl.it.evil.invalid/",
        "https://127.0.0.1/",
        "https://[::1]/",
        "https://www.lidl.it/#x",
    ],
)
def test_url_rejected(url):
    with pytest.raises(FetchError):
        validate_url(url, ["www.lidl.it"])


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
    ],
)
def test_nonpublic_dns(monkeypatch, ip):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, (ip, 443))]
    )
    with pytest.raises(FetchError):
        public_addresses("www.lidl.it")


def test_connection_pins_resolved_ip(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(None, None, None, None, ("1.1.1.1", 443))],
    )
    connected = []

    class Stream:
        def get_extra_info(self, k):
            return ("1.1.1.1", 443)

    class Backend:
        def connect_tcp(self, host, port, **kw):
            connected.append(host)
            return Stream()

    backend = PinnedBackend(["www.lidl.it"])
    backend.backend = Backend()
    backend.connect_tcp("www.lidl.it", 443)
    assert connected == ["1.1.1.1"]


def response(status=200, body=b"ok", headers=None):
    return httpx.Response(status, headers=headers, stream=httpx.ByteStream(body))


def test_decompression_bomb():
    r = response(body=gzip.compress(b"x" * 10000), headers={"content-encoding": "gzip"})
    with pytest.raises(FetchError, match="troppo grande"):
        bounded_body(r, limit=100)


@pytest.mark.parametrize(
    "status,code",
    [
        (403, "BLOCKED_ACCESS"),
        (401, "BLOCKED_ACCESS"),
        (429, "RATE_LIMITED"),
        (503, "TRANSIENT"),
    ],
)
def test_status_no_retry_storm(monkeypatch, status, code):
    monkeypatch.setattr("app.security.fetch.time.sleep", lambda _: None)
    calls = []

    def handler(r):
        calls.append(r.url)
        return response(status, headers={"Retry-After": "3600"})

    f = Fetcher(manifests()["lidl-national"], httpx.MockTransport(handler))
    with pytest.raises(FetchError) as exc:
        f.request("https://www.lidl.it/")
    assert exc.value.code == code and len(calls) == (3 if status == 503 else 1)
    if status == 429:
        assert exc.value.retry_after == 3600


def test_redirect_blocked_before_destination(monkeypatch):
    monkeypatch.setattr("app.security.fetch.time.sleep", lambda _: None)
    calls = []

    def handler(r):
        calls.append(str(r.url))
        return response(302, headers={"Location": "http://169.254.169.254/latest/"})

    f = Fetcher(manifests()["lidl-national"], httpx.MockTransport(handler))
    with pytest.raises(FetchError):
        f.request("https://www.lidl.it/")
    assert calls == ["https://www.lidl.it/"]


def test_robots_and_304(monkeypatch):
    monkeypatch.setattr("app.security.fetch.time.sleep", lambda _: None)
    calls = []

    def handler(r):
        calls.append(str(r.url))
        if r.url.path == "/robots.txt":
            return response(body=b"User-agent: *\nDisallow: /private\n")
        if r.headers.get("if-none-match") == "v1":
            return response(304)
        return response(body=b"<html>Product</html>", headers={"etag": "v1"})

    f = Fetcher(manifests()["lidl-national"], httpx.MockTransport(handler))
    first = f.fetch("https://www.lidl.it/")
    second = f.fetch("https://www.lidl.it/")
    assert first[0] == second[0] and first[1] != second[1] and f.cache_hits == 1
    with pytest.raises(FetchError):
        f.fetch("https://www.lidl.it/private")
    assert len(calls) == 3


def test_retry_after_http_date():
    assert retry_seconds("Wed, 31 Dec 2098 23:59:59 GMT") > 3600
