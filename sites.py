"""The pages this repo ships, and the two ways a box reaches them.

There are exactly two: a `file://` URL, which is what an ordinary run uses and
which needs nothing running, and a local HTTP server, which is what `demo.py`
uses because the address bar is on camera. `file:///C:/Users/.../tickets.html`
reads as a file someone opened; `127.0.0.1:8137/tickets` reads as a website, and
the difference matters for exactly one thing -- a recording -- so the server
lives behind a call the demo makes and the app never does.

The pages are hand-written HTML and CSS with no build step and no binary assets,
for the same reason the app's icon is a painted `QIcon` rather than a `.ico`:
there is not one compiled artefact in this repo and this is not worth being the
first.

`start.html` is the app's own, and is what `config.json` points a new box at. The
Pinion Ops pages under `sites/pinion/` are an invented company's internal tools,
and they exist because a demo of a browser fleet needs pages whose content does
not move between takes -- "the top story on Hacker News" cannot be narrated in
advance. They are deliberately blocky: a tile renders a 1440px window at roughly
a third of that, so what survives is headings, colour and table shape, never body
text.

**The server runs on a thread, and that is not a hole in the single-threaded
rule.** It serves static files out of one directory and touches neither Qt nor
Playwright nor a Session. Nothing in the app imports it -- `serve` has one caller
and that caller is `demo.py`.
"""

import socket
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import quote
from urllib.request import pathname2url

# Relative `start_url` values in `config.json` are resolved against the repo, so
# the config reads `sites/start.html` rather than a bare filename -- one look
# tells you where the page is.
ROOT = Path(__file__).parent
SITES_DIR = ROOT / "sites"

# What a box opens when it has nothing else to open. Named here rather than only
# in `config.json`, because `smoke.py` needs to know which page it is checking.
START_PAGE = "sites/start.html"


def resolve(value, root=ROOT):
    """A configured `start_url` as a URL a browser can open.

    An absolute URL is returned untouched -- someone who configured
    `https://intranet/` meant it. A relative path is one of ours, resolved
    against the repo and handed back as a `file://` URL, so the shipped default
    needs no server, no port and no network.
    """
    value = (value or "").strip()
    if not value:
        return ""
    if "://" in value or value.startswith("about:"):
        return value
    path = (Path(root) / value).resolve()
    return "file:" + pathname2url(str(path))


def for_box(url, name):
    """The same page, told which box it is showing.

    Eight tiles of one start page are one picture repeated; eight tiles of one
    start page that each say their own bird's name are eight. Only ever called
    for a page of ours -- `config['bundled_start']` says so -- because appending
    a query to a URL somebody else configured is not ours to do.
    """
    if not url or not name:
        return url
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}box={quote(name)}"


class _Handler(SimpleHTTPRequestHandler):
    """Static files, extensionless paths, and no logging.

    Extensionless because the address bar is the reason this server exists at
    all: `/tickets` is a page on a site and `/tickets.html` is a file in a
    folder. Anything that does not resolve falls through to the base class and
    404s, which is what makes `/deploys/482` an honest failure for a box to hit
    rather than a staged one.

    Silent because the base class logs every request to stderr, and the console
    during a take is the beat sheet.
    """

    def translate_path(self, path):
        resolved = super().translate_path(path)
        candidate = Path(resolved)
        if not candidate.exists() and not candidate.suffix:
            with_suffix = candidate.with_suffix(".html")
            if with_suffix.is_file():
                return str(with_suffix)
        return resolved

    def log_message(self, *args):
        pass


def serve(root=SITES_DIR, host="127.0.0.1"):
    """Serve `root` on a free port. Returns `(base_url, stop)`.

    The thread is a daemon and `stop` is idempotent, so a demo that dies
    mid-take does not leave a listener behind.
    """
    handler = partial(_Handler, directory=str(root))
    server = ThreadingHTTPServer((host, 0), handler)
    Thread(target=server.serve_forever, daemon=True).start()

    stopped = []

    def stop():
        if stopped:
            return
        stopped.append(True)
        server.shutdown()
        server.server_close()

    return f"http://{host}:{server.server_port}", stop


def reachable(url, timeout=4.0):
    """Can this machine open a socket to that host at all?

    Here rather than in `demo.py` because it is a question about a site, and the
    demo asks it of both the local server and the real ones.
    """
    from urllib.parse import urlparse

    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return True
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        with socket.create_connection((parts.hostname, port), timeout):
            return True
    except OSError:
        return False
