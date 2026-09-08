"""HTTPS allowlist, DNS pinning at connect, bounded capture and responsible fetching."""

import hashlib
import ipaddress
import random
import socket
import time
import uuid
import zlib
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpcore
import httpx
from app.storage.db import DB_PATH, CaptureRow, Session
from sqlalchemy import select

UA = "SpesaRadar/0.1 (personal local catalog; no commercial reuse)"
MAX_BYTES = 10 * 1024 * 1024


class FetchError(RuntimeError):
    def __init__(self, code, message, retry_after=0):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


def validate_url(url, allowed):
    p = urlsplit(url)
    if (
        p.scheme != "https"
        or p.hostname not in allowed
        or p.username
        or p.password
        or p.port not in [None, 443]
        or p.fragment
    ):
        raise FetchError("DESTINATION_BLOCKED", "Destinazione non ammessa")
    return p


def public_addresses(host):
    values = list(
        dict.fromkeys(
            x[4][0] for x in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        )
    )
    if not values or any(not ipaddress.ip_address(v).is_global for v in values):
        raise FetchError("DESTINATION_BLOCKED", "Indirizzo di rete non pubblico")
    return values


class PinnedBackend(httpcore.NetworkBackend):
    def __init__(self, allowed):
        self.allowed = allowed
        self.backend = httpcore.SyncBackend()

    def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        if host not in self.allowed or port != 443:
            raise FetchError("DESTINATION_BLOCKED", "Host non ammesso")
        ips = public_addresses(host)
        # Literal IP is passed to connect; TLS retains original hostname via httpcore.
        stream = self.backend.connect_tcp(
            ips[0],
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )
        peer = stream.get_extra_info("server_addr")
        if peer and peer[0] not in ips:
            stream.close()
            raise FetchError("DESTINATION_BLOCKED", "Destinazione effettiva diversa")
        return stream


class ResponseStream(httpx.SyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    def __iter__(self):
        yield from self.stream

    def close(self):
        self.stream.close()


class PinnedTransport(httpx.BaseTransport):
    def __init__(self, allowed):
        self.pool = httpcore.ConnectionPool(
            network_backend=PinnedBackend(allowed), max_connections=1, retries=0
        )

    def handle_request(self, request):
        response = self.pool.handle_request(
            httpcore.Request(
                method=request.method,
                url=httpcore.URL(
                    scheme=request.url.raw_scheme,
                    host=request.url.raw_host,
                    port=request.url.port,
                    target=request.url.raw_path,
                ),
                headers=request.headers.raw,
                content=request.stream,
                extensions=request.extensions,
            )
        )
        return httpx.Response(
            response.status,
            headers=response.headers,
            stream=ResponseStream(response.stream),
            extensions=response.extensions,
        )

    def close(self):
        self.pool.close()


def retry_seconds(value):
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        try:
            return max(0, int(parsedate_to_datetime(value).timestamp() - time.time()))
        except (ValueError, TypeError):
            return 1800


def bounded_body(response, limit=MAX_BYTES, deadline=None):
    encoding = response.headers.get("content-encoding", "identity").lower()
    if encoding not in ["identity", "gzip", "deflate"]:
        raise FetchError("UNSUPPORTED_ENCODING", "Compressione non supportata")
    decoder = (
        zlib.decompressobj(31 if encoding == "gzip" else 15)
        if encoding != "identity"
        else None
    )
    data = bytearray()
    compressed = 0
    for chunk in response.iter_raw():
        if deadline is not None and time.monotonic() >= deadline:
            raise FetchError("BUDGET", "Tempo di raccolta raggiunto")
        compressed += len(chunk)
        if compressed > limit:
            raise FetchError("TOO_LARGE", "Risorsa troppo grande")
        out = decoder.decompress(chunk, limit - len(data) + 1) if decoder else chunk
        data.extend(out)
        if len(data) > limit or (decoder and decoder.unconsumed_tail):
            raise FetchError("TOO_LARGE", "Risorsa decompressa troppo grande")
    if decoder:
        data.extend(decoder.flush(limit - len(data) + 1))
        if len(data) > limit:
            raise FetchError("TOO_LARGE", "Risorsa decompressa troppo grande")
        if not decoder.eof:
            raise FetchError("MALFORMED", "Compressione incompleta")
    return bytes(data)


class Fetcher:
    def __init__(self, manifest, transport=None):
        self.m = manifest
        self.count = 0
        self.cache_hits = 0
        self.start = time.monotonic()
        self.last = {}
        self.robots = {}
        self.client = httpx.Client(
            transport=transport or PinnedTransport(manifest.allowed_domains),
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(30, connect=10),
            headers={
                "User-Agent": UA,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "text/html,application/json,text/plain",
            },
        )

    def close(self):
        self.client.close()

    def request(self, url, headers=None, robots=False):
        for redirects in range(4):
            parsed = validate_url(url, self.m.allowed_domains)
            for attempt in range(3):
                if (
                    self.count >= self.m.max_requests
                    or time.monotonic() - self.start >= self.m.deadline_seconds
                ):
                    raise FetchError("BUDGET", "Limite di raccolta raggiunto")
                delay = max(
                    0,
                    self.m.min_interval_seconds
                    - (time.monotonic() - self.last.get(parsed.hostname, 0)),
                )
                if time.monotonic() - self.start + delay >= self.m.deadline_seconds:
                    raise FetchError("BUDGET", "Tempo di raccolta raggiunto")
                time.sleep(delay)
                self.last[parsed.hostname] = time.monotonic()
                self.count += 1
                try:
                    with self.client.stream(
                        "GET", url, headers=headers or {}
                    ) as response:
                        status = response.status_code
                        if status in [401, 403]:
                            raise FetchError(
                                "BLOCKED_ACCESS", "Accesso alla fonte non consentito"
                            )
                        if status == 429:
                            raise FetchError(
                                "RATE_LIMITED",
                                "La fonte richiede una pausa",
                                retry_seconds(response.headers.get("retry-after")),
                            )
                        if status in [301, 302, 303, 307, 308]:
                            url = urljoin(url, response.headers.get("location", ""))
                            validate_url(url, self.m.allowed_domains)
                            # Release the sole connection before a new host's robots
                            # request. Keeping this stream open deadlocks the pool.
                            response.close()
                            if not robots:
                                self.check_robots(url)
                            break
                        if status >= 500:
                            raise FetchError(
                                "TRANSIENT", "Fonte temporaneamente non raggiungibile"
                            )
                        if status == 304:
                            return url, status, dict(response.headers), b""
                        if robots and status in [404, 410]:
                            return url, status, dict(response.headers), b""
                        if status != 200:
                            raise FetchError(
                                "HTTP_ERROR", "Risorsa ufficiale non disponibile"
                            )
                        data = bounded_body(
                            response, deadline=self.start + self.m.deadline_seconds
                        )
                        if any(
                            x in data[:100000].lower()
                            for x in [
                                b"<title>just a moment",
                                b"<title>access denied",
                                b"cf-chl-",
                            ]
                        ):
                            raise FetchError(
                                "BLOCKED_ACCESS", "Controllo di accesso sulla fonte"
                            )
                        return url, status, dict(response.headers), data
                except (
                    httpcore.NetworkError,
                    httpcore.TimeoutException,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                ) as exc:
                    if attempt == 2:
                        raise FetchError("TIMEOUT", "Fonte non raggiungibile") from exc
                except FetchError as exc:
                    if exc.code != "TRANSIENT" or attempt == 2:
                        raise
                time.sleep(min(2**attempt + random.random(), 4))
            else:
                raise FetchError("TIMEOUT", "Tentativi terminati")
        raise FetchError("REDIRECT_LIMIT", "Troppi reindirizzamenti")

    def check_robots(self, url):
        host = validate_url(url, self.m.allowed_domains).hostname
        if host not in self.robots:
            _, _, _, body = self.request(f"https://{host}/robots.txt", robots=True)
            rp = RobotFileParser()
            rp.parse(body.decode("utf-8", errors="replace").splitlines())
            self.robots[host] = rp
            delay = rp.crawl_delay(UA)
            if delay:
                self.m.min_interval_seconds = max(self.m.min_interval_seconds, delay)
            rate = rp.request_rate(UA)
            if rate:
                self.m.min_interval_seconds = max(
                    self.m.min_interval_seconds, rate.seconds / rate.requests
                )
        if not self.robots[host].can_fetch(UA, url):
            raise FetchError("ROBOTS_BLOCKED", "Raccolta esclusa dalla fonte")

    def fetch(self, url):
        self.check_robots(url)
        with Session() as s:
            previous = s.scalar(
                select(CaptureRow)
                .where(CaptureRow.url == url)
                .order_by(CaptureRow.fetched_at.desc())
                .limit(1)
            )
        headers = {}
        if previous and previous.path and Path(previous.path).is_file():
            if previous.etag:
                headers["If-None-Match"] = previous.etag
            if previous.modified:
                headers["If-Modified-Since"] = previous.modified
        final, status, meta, body = self.request(url, headers)
        if status == 304:
            if not previous or not previous.path or not Path(previous.path).is_file():
                raise FetchError(
                    "CACHE_MISSING", "Capture non disponibile per risposta 304"
                )
            body = Path(previous.path).read_bytes()
            self.cache_hits += 1
        capture_id = uuid.uuid4().hex
        digest = hashlib.sha256(body).hexdigest()
        root = DB_PATH.parent / "captures"
        root.mkdir(exist_ok=True, mode=0o700)
        path = root / (capture_id + ".bin")
        path.write_bytes(body)
        path.chmod(0o600)
        with Session.begin() as s:
            s.add(
                CaptureRow(
                    id=capture_id,
                    url=url,
                    source_id=self.m.source_id,
                    fetched_at=time.time(),
                    sha256=digest,
                    path=str(path),
                    etag=meta.get("etag") or (previous.etag if previous else None),
                    modified=meta.get("last-modified")
                    or (previous.modified if previous else None),
                )
            )
        return body.decode("utf-8", errors="replace"), capture_id, final


def retention():
    with Session.begin() as s:
        rows = list(
            s.scalars(
                select(CaptureRow)
                .where(CaptureRow.path.is_not(None))
                .order_by(CaptureRow.fetched_at.desc())
            )
        )
        size = 0
        for row in rows:
            p = Path(row.path)
            size += p.stat().st_size if p.is_file() else 0
            if size > 500 * 1024 * 1024 or row.fetched_at < time.time() - 7 * 86400:
                p.unlink(missing_ok=True)
                row.path = None
