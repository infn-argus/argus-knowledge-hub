#!/usr/bin/env python3
"""Send a facility's Olog entries to ARGUS Knowledge Hub, once a day.

Reads the entries written in the last LOOKBACK_DAYS (default 2) from the facility's Olog and sends them, with
their files, to ARGUS (POST /v1/logbook/olog/entries). ARGUS keeps one Logbook Entry document per entry; an
entry sent again unchanged is left alone and an edited one becomes a new revision, so overlapping runs and
retries are safe. `--all` sends every entry, for the first run.

Standard library only: it runs in a plain python image with nothing to install.

Settings (environment, or the matching --option):
  OLOG_URL           the Olog service, e.g. http://olog.btf.svc:8080/Olog
  OLOG_USERNAME      optional, if the Olog search needs a sign-in
  OLOG_PASSWORD
  ARGUS_URL          the ARGUS API, e.g. https://argus-hub-api.example.org
  ARGUS_TOKEN        a robot token of the facility's workspace (the "Daily logbook upload" preset)
  ARGUS_FACILITY     the logbook's name in ARGUS, e.g. btf
  OLOG_ENTRY_URL     optional: where a person opens an entry, with {id}, e.g. https://btf-webolog.example.org/logs/{id}
  LOOKBACK_DAYS      how far back to look (default 2: a missed night is caught by the next)
  ARGUS_BATCH        entries per request (default 100)

Proxies are taken from HTTPS_PROXY / HTTP_PROXY / NO_PROXY.
Exit status: 0 when everything was sent, 1 when something failed (the job is retried by Kubernetes).
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

PAGE = 200
USER_AGENT = "olog-to-argus/1.0"


class Failure(RuntimeError):
    pass


def _request(method, url, *, headers=None, body=None, timeout=60, attempts=4):
    """An HTTP request, retried on network errors and 5xx/429 with back-off. Returns (status, bytes, headers)."""
    headers = {"User-Agent": USER_AGENT, **(headers or {})}
    last = None
    for attempt in range(attempts):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            payload = e.read()
            if e.code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                last = f"{e.code} {payload[:200]!r}"
            else:
                return e.code, payload, dict(e.headers or {})
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = str(e)
            if attempt == attempts - 1:
                raise Failure(f"{method} {url}: {last}") from e
        time.sleep(2 ** attempt)
    raise Failure(f"{method} {url}: {last}")


class Olog:
    def __init__(self, url, username=None, password=None):
        self.url = url.rstrip("/")
        self.headers = {"Accept": "application/json"}
        if username:
            token = base64.b64encode(f"{username}:{password or ''}".encode()).decode()
            self.headers["Authorization"] = f"Basic {token}"

    def entries(self, start):
        """Every entry created since `start` (an Olog time: "2 days", or "1970-01-01 00:00:00"), oldest first,
        page by page."""
        offset = 0
        while True:
            query = urllib.parse.urlencode({"start": start, "end": "now", "from": offset, "size": PAGE,
                                            "sort": "up"})
            status, body, _ = _request("GET", f"{self.url}/logs/search?{query}", headers=self.headers)
            if status == 404:                                   # an Olog before /logs/search
                status, body, _ = _request("GET", f"{self.url}/logs?{query}", headers=self.headers)
            if status != 200:
                raise Failure(f"Olog answered {status}: {body[:300]!r}")
            data = json.loads(body or b"[]")
            page = data.get("logs", []) if isinstance(data, dict) else data
            hits = data.get("hitCount") if isinstance(data, dict) else None
            yield from page
            offset += len(page)
            if not page or len(page) < PAGE or (hits is not None and offset >= hits):
                return

    def attachment(self, entry_id, attachment):
        """An entry's file: by name under the entry, or by its id."""
        name = attachment.get("filename") or attachment.get("id")
        tried = []
        for path in (f"/logs/attachments/{entry_id}/{urllib.parse.quote(str(name))}",
                     f"/attachment/{urllib.parse.quote(str(attachment.get('id') or name))}"):
            url = self.url + path
            status, body, headers = _request("GET", url, headers={k: v for k, v in self.headers.items()
                                                                if k != "Accept"}, timeout=300)
            if status == 200:
                return body, headers.get("Content-Type") or "application/octet-stream", url
            tried.append(f"{path} → {status}")
        raise Failure(f"file {name} of entry {entry_id}: " + "; ".join(tried))


class Argus:
    def __init__(self, url, token):
        self.url = url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def send(self, facility, entries, entry_url):
        body = json.dumps({"facility": facility, "entry_url": entry_url, "entries": entries}).encode()
        status, payload, _ = _request("POST", f"{self.url}/v1/logbook/olog/entries", body=body, timeout=300,
                                      headers={**self.headers, "Content-Type": "application/json"})
        if status != 200:
            raise Failure(f"ARGUS answered {status}: {payload[:500]!r}")
        return json.loads(payload)

    def attach(self, facility, entry_id, attachment_id, filename, content, content_type, source_url):
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in (("attachment_id", attachment_id), ("source_url", source_url or "")):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        safe = filename.replace('"', "'")
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{safe}"\r\n'
                     f"Content-Type: {content_type}\r\n\r\n".encode() + content + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        url = (f"{self.url}/v1/logbook/olog/entries/{urllib.parse.quote(facility)}/"
               f"{urllib.parse.quote(str(entry_id))}/attachments")
        status, payload, _ = _request("POST", url, body=b"".join(parts), timeout=300,
                                      headers={**self.headers, "Content-Type": f"multipart/form-data; boundary={boundary}"})
        if status not in (200, 201):
            raise Failure(f"ARGUS refused file {filename} of entry {entry_id}: {status} {payload[:300]!r}")


def run(olog, argus, facility, start, entry_url=None, batch_size=100, log=print):
    totals = {"created": 0, "updated": 0, "unchanged": 0, "rejected": 0, "files": 0, "failures": 0}
    batch = []

    def flush():
        if not batch:
            return
        answer = argus.send(facility, batch, entry_url)
        for k, v in (answer.get("counts") or {}).items():
            totals[k] = totals.get(k, 0) + v
        by_id = {str(e.get("id")): e for e in batch}
        for result in answer.get("entries", []):
            if result.get("status") == "rejected":
                log(f"entry {result.get('id')} refused: {result.get('error')}")
                continue
            entry = by_id.get(str(result.get("id")), {})
            files = {str(a.get("id") or a.get("filename")): a for a in entry.get("attachments") or []}
            for needed in result.get("attachments_needed") or []:
                try:
                    content, ctype, url = olog.attachment(result["id"], files.get(needed["id"], needed))
                    argus.attach(facility, result["id"], needed["id"], needed["filename"], content, ctype, url)
                    totals["files"] += 1
                except Failure as e:
                    totals["failures"] += 1
                    log(f"warning: {e}")
        batch.clear()

    for entry in olog.entries(start):
        batch.append(entry)
        if len(batch) >= batch_size:
            flush()
    flush()
    return totals


def main(argv=None):
    env = os.environ.get
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--olog-url", default=env("OLOG_URL"))
    p.add_argument("--olog-username", default=env("OLOG_USERNAME"))
    p.add_argument("--olog-password", default=env("OLOG_PASSWORD"))
    p.add_argument("--argus-url", default=env("ARGUS_URL"))
    p.add_argument("--argus-token", default=env("ARGUS_TOKEN"))
    p.add_argument("--facility", default=env("ARGUS_FACILITY"))
    p.add_argument("--entry-url", default=env("OLOG_ENTRY_URL") or None)
    p.add_argument("--lookback-days", type=int, default=int(env("LOOKBACK_DAYS") or 2))
    p.add_argument("--batch", type=int, default=int(env("ARGUS_BATCH") or 100))
    p.add_argument("--all", action="store_true", default=(env("OLOG_ALL") or "").lower() in ("1", "true", "yes"),
                   help="send every entry, not only the last days (the first run)")
    a = p.parse_args(argv)
    missing = [n for n, v in (("OLOG_URL", a.olog_url), ("ARGUS_URL", a.argus_url), ("ARGUS_TOKEN", a.argus_token),
                              ("ARGUS_FACILITY", a.facility)) if not v]
    if missing:
        p.error("missing " + ", ".join(missing))
    start = "1970-01-01 00:00:00" if a.all else f"{a.lookback_days} days"
    print(f"olog-to-argus: {a.facility}: entries since {start} from {a.olog_url} to {a.argus_url}", flush=True)
    try:
        totals = run(Olog(a.olog_url, a.olog_username, a.olog_password), Argus(a.argus_url, a.argus_token),
                     a.facility, start, a.entry_url, a.batch)
    except Failure as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print("olog-to-argus: " + ", ".join(f"{k} {v}" for k, v in totals.items()), flush=True)
    return 1 if totals["failures"] or totals["rejected"] else 0


if __name__ == "__main__":
    sys.exit(main())
