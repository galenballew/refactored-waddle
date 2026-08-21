"""One box's agent, in its own process.

    python agent_host.py <box-name> [--cdp http://127.0.0.1:PORT]

Given a CDP endpoint it drives that box's real browser: it opens pages, reads
them, takes screenshots and clicks links, and everything it reports is something
that actually happened. Given no endpoint it falls back to a scripted stand-in
that invents all of it, which is what `smoke.py` runs against so the fast checks
need no browser.

**There is still no model here.** What to do next is decided by a fixed script,
not by anything that thinks: find a URL in what the user said, go there, look at
it, click the first link. That is the whole intelligence. Replacing this file's
`BrowserAgent` with a Claude Agent SDK loop is the last milestone, and nothing
outside this file should have to change for it.

The protocol is one JSON object per line.

    in    {"type": "input",  "text": "..."}
          {"type": "cancel"}

    out   {"type": "task"}                     a new task started; clear the trajectory
          {"type": "state", "value": "working"}
          {"type": "say",   "text": "..."}     a turn in the chat
          {"type": "step",  "text": "..."}     a line of trajectory
          {"type": "url",   "value": "..."}    where the page is now

The loop polls rather than blocks: it drains stdin, runs one queued action if one
is due, and sleeps a hundredth of a second. Cancel is therefore noticed between
actions, not during one -- a `goto` that is already waiting on a slow page will
finish first. `pipes.py` reports a broken pipe as distinct from an empty one, and
that is this process's only signal that the dashboard has gone.

Perception is a separate path from the dashboard's tiles, and has to be: DWM
composites those on the GPU and never hands Python any pixels, so an agent that
wants to see a page takes its own `page.screenshot()`. That is what `_shoot`
exists to prove.

AVIARY_STEP_MS paces the stand-in only. Real work takes as long as it takes.
"""

import base64
import json
import os
import re
import struct
import sys
import tempfile
import time
from pathlib import Path

import pipes
from session import DONE, FAILED, IDLE, NEEDS_INPUT, WORKING

POLL_S = 0.01
STEP_S = int(os.environ.get("AVIARY_STEP_MS", "900")) / 1000.0
NAV_TIMEOUT_MS = 20000
CLICK_TIMEOUT_MS = 5000

# http://…, file:///…, or a bare domain with a dot in it.
URL_PATTERN = re.compile(
    r"(?:https?://|file:///)\S+|\b[\w-]+(?:\.[\w-]+)+(?:/\S*)?", re.IGNORECASE
)

ASK_FOR_URL = "which page should I open? give me a URL and I will go and look."


def emit(kind, **fields):
    sys.stdout.write(json.dumps({"type": kind, **fields}) + "\n")
    sys.stdout.flush()


def find_url(text):
    """The first thing in the text that looks like somewhere to go."""
    match = URL_PATTERN.search(text or "")
    if not match:
        return None
    url = match.group(0).rstrip(".,;:!?)\"'")
    if "://" in url:
        return url
    return "https://" + url


def png_size(data):
    """Width and height straight out of a PNG header -- no image library here."""
    try:
        return struct.unpack(">II", data[16:24])
    except struct.error:
        return (0, 0)


class Agent:
    """The state machine, and a queue of things to do spaced out in time.

    A queue rather than a straight line of calls, so that between any two actions
    the loop is free to notice a cancel. Subclasses decide what goes in it.
    """

    pace = 0.0

    def __init__(self, name):
        self.name = name
        self.state = IDLE
        self.tasks = 0
        self.queue = []
        self.due = 0.0

    # -- input --------------------------------------------------------------

    def on_input(self, text):
        if self.state == WORKING:
            return  # the dashboard does not send these; do not invent a queue
        if self.state == NEEDS_INPUT:
            self.set_state(WORKING)
            self.resume(text)
        else:
            self.tasks += 1
            emit("task")
            self.set_state(WORKING)
            self.start(text)

    def on_cancel(self):
        """Stop now. Whatever is already in flight finishes first -- a browser
        call cannot be interrupted from here -- but nothing else runs."""
        if self.state not in (WORKING, NEEDS_INPUT):
            return
        self.queue.clear()
        self.step("stopped by you")
        self.set_state(IDLE)
        self.say("stopped.")

    # -- the clock ----------------------------------------------------------

    def tick(self, now):
        if not self.queue or now < self.due:
            return
        action = self.queue.pop(0)
        try:
            action()
        except Exception as exc:  # a dead page, a timeout, a missing element
            self.fail(exc)
        self.due = now + self.pace

    def run(self, actions):
        self.queue = list(actions)
        self.due = time.monotonic() + self.pace

    def fail(self, exc):
        self.queue.clear()
        detail = str(exc).strip().splitlines()[0][:200] or exc.__class__.__name__
        self.set_state(FAILED)
        self.say(f"I gave up: {detail}")

    # -- saying it ----------------------------------------------------------

    def set_state(self, value):
        self.state = value
        emit("state", value=value)

    def say(self, text):
        emit("say", text=text)

    def step(self, text):
        emit("step", text=text)

    def report_url(self):
        """Tell the dashboard where the page is. Nothing to say without a page,
        so the stand-in never does."""

    def close(self):
        pass

    # -- for subclasses -----------------------------------------------------

    def start(self, prompt):
        raise NotImplementedError

    def resume(self, answer):
        raise NotImplementedError


class BrowserAgent(Agent):
    """Drives a real browser over CDP, following a fixed script.

    It connects as an ordinary CDP client and takes the page the box already has,
    rather than opening one of its own: the box *is* that window, and a second
    tab would be invisible in the dashboard's mirror.
    """

    def __init__(self, name, endpoint):
        super().__init__(name)
        self.endpoint = endpoint
        self._playwright = None
        self._browser = None
        self._page = None

    # -- the script ---------------------------------------------------------

    def start(self, prompt):
        self.say("on it.")
        self.run([lambda: self._plan(prompt)])

    def resume(self, answer):
        self.run([lambda: self._plan(answer)])

    def _plan(self, text):
        """Decide, mechanically, what this task means: a URL to open, the page
        that is already there, or a question back."""
        page = self._connect()
        url = find_url(text)
        if url:
            self.queue.extend([lambda: self._goto(url)] + self._look())
        elif page.url and not page.url.startswith("about:"):
            self.step(f"working with the page already open: {page.url}")
            self.queue.extend(self._look())
        else:
            self.set_state(NEEDS_INPUT)
            self.say(ASK_FOR_URL)

    def _look(self):
        return [self._shoot, self._describe, self._click_first_link, self._finish]

    # -- the browser --------------------------------------------------------

    def _connect(self):
        if self._page is not None:
            return self._page
        # Imported here, not at the top: the stand-in path must not pay for
        # Playwright, and `smoke.py` runs children with no browser at all.
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.connect_over_cdp(self.endpoint)
        self._page = self._existing_page()
        self.step(f"connected over CDP to {self.endpoint}")
        self.report_url()
        return self._page

    def _existing_page(self):
        """Take the page the box already has, wherever CDP files it.

        Attaching over CDP does not group targets the way the launching process
        sees them: the box's page can turn up in any of the contexts, and
        `contexts[0]` is often empty. Taking `contexts[0].pages[0]` therefore
        misses it and falls through to opening a new one -- which is a *second*
        window, invisible in the dashboard's mirror, quietly driven while the
        tile shows an unchanged page. Search every context first.
        """
        for context in self._browser.contexts:
            if context.pages:
                return context.pages[0]
        # Nothing open at all. Should not happen -- a box is launched with a page
        # -- so say it rather than silently opening a window nobody can see.
        self.step("the box had no page open; opening one")
        context = (self._browser.contexts[0] if self._browser.contexts
                   else self._browser.new_context())
        return context.new_page()

    def report_url(self):
        """Where the page actually is.

        The dashboard cannot see this for itself. The `page.url` its own
        Playwright holds does not update for navigations made by another CDP
        client, and this process is exactly that -- so without this the caption
        under a tile would still read about:blank while the tile plainly shows
        something else.
        """
        if self._page is not None:
            emit("url", value=self._page.url)

    def _goto(self, url):
        self.step(f"goto {url}")
        self._page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        self.step(f"landed on {self._page.url}")
        self.report_url()

    def _shoot(self):
        """Take a real screenshot. Not shown anywhere yet -- what it proves is
        that an agent here can see, which the dashboard's tiles cannot give it."""
        data = self._page.screenshot()
        width, height = png_size(data)
        path = Path(tempfile.gettempdir()) / f"aviary-{self.name}.png"
        path.write_bytes(data)
        self.step(f"screenshot {width}x{height}, {len(data) // 1024} KB")

    def _describe(self):
        title = (self._page.title() or "").strip()
        links = self._page.locator("a[href]").count()
        self.step(f'title "{title}"' if title else "the page has no title")
        self.step(f"{links} link{'' if links == 1 else 's'} on the page")
        self._title = title
        self._links = links

    def _click_first_link(self):
        if not getattr(self, "_links", 0):
            self.step("no links to click")
            return
        link = self._page.locator("a[href]").first
        label = (link.text_content() or "").strip().replace("\n", " ")[:40]
        before = self._page.url
        link.click(timeout=CLICK_TIMEOUT_MS)
        self._page.wait_for_load_state("domcontentloaded", timeout=NAV_TIMEOUT_MS)
        after = self._page.url
        if after == before:
            self.step(f'clicked "{label}" — the page did not change')
        else:
            self.step(f'clicked "{label}" → {after}')
            self.report_url()

    def _finish(self):
        title = getattr(self, "_title", "")
        where = self._page.url
        self.set_state(DONE)
        self.say(f'done — "{title}" at {where}' if title else f"done — {where}")

    def close(self):
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None


MODEL = os.environ.get("AVIARY_MODEL", "claude-opus-5")
MAX_TURNS = 12          # a runaway loop is a runaway bill
MAX_OUTPUT_TOKENS = 8000
PAGE_TEXT_CHARS = 4000
SHOT_QUALITY = 60       # JPEG: a page screenshot is sent to the model every time

# Both go through `fail`, which keeps the first line and 200 characters, so they
# are one line each. Neither names config.json: the paid path is a flag, and a
# config key has never been able to turn it on or off.
NO_CREDENTIALS = (
    "no API credentials — set ANTHROPIC_API_KEY (or run `ant auth login`) and "
    "restart, or drop --agent claude to run the scripted agent instead"
)
BAD_CREDENTIALS = "the API rejected those credentials — check ANTHROPIC_API_KEY"

SYSTEM = """You are driving one Chromium window on someone's desktop. It is called
{name}, and it is one of several windows they are watching side by side.

You have one page and it is the one they can see. Do not open tabs or windows.
Work on the page you have.

Use the tools to look before you act: read_page tells you the text and the links,
screenshot shows you what it looks like. Prefer read_page when you need facts and
screenshot when the layout matters.

If the task is ambiguous, or you need something only they know, call ask_user and
stop. Do not guess at a URL they did not give you.

When you are finished, reply with a short plain answer -- one or two sentences,
what they asked for, no preamble. They are watching several of these at once."""

TOOLS = [
    {
        "name": "goto",
        "description": "Navigate this window to a URL.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Full URL."}},
            "required": ["url"],
        },
    },
    {
        "name": "read_page",
        "description": "Read the current page: title, address, visible text, links.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "click",
        "description": "Click a link or button by its visible text.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Visible text."}},
            "required": ["text"],
        },
    },
    {
        "name": "screenshot",
        "description": "Look at the page as an image.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ask_user",
        "description": ("Stop and ask the person a question. Use when the task is "
                        "ambiguous or needs something only they know."),
        "input_schema": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
]


class ModelAgent(BrowserAgent):
    """A Claude loop with a browser on the end of it. The only thinking in here.

    One queued action is one model turn, which keeps the shape the rest of this
    file has: the loop can notice a cancel between turns. It cannot notice one
    *during* a turn -- a model call blocks this process for as long as it takes,
    and there is nothing useful to do about that here.

    The conversation is kept whole, `response.content` appended unchanged, because
    thinking blocks have to go back exactly as they came.
    """

    def __init__(self, name, endpoint):
        super().__init__(name, endpoint)
        self._client = None
        self._sdk = None           # the anthropic module, for its exception types
        self.messages = []
        self.turns = 0
        self.spent = [0, 0]        # input, output tokens this task
        self._pending_ask = None   # tool_use id waiting on the user
        self._pending_results = []

    # -- the loop -----------------------------------------------------------

    def start(self, prompt):
        self.messages = [{"role": "user", "content": prompt}]
        self.turns = 0
        self.spent = [0, 0]
        self.run([self._turn])

    def resume(self, answer):
        """The user answered. If a tool asked the question, the answer is that
        tool's result -- every tool call in a turn has to be answered together,
        so the others have been waiting here for it."""
        if self._pending_ask is not None:
            self._pending_results.append({
                "type": "tool_result",
                "tool_use_id": self._pending_ask,
                "content": answer,
            })
            self.messages.append({"role": "user", "content": self._pending_results})
            self._pending_ask = None
            self._pending_results = []
        else:
            self.messages.append({"role": "user", "content": answer})
        self.run([self._turn])

    def _client_or_fail(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "the anthropic package is not installed in this environment"
            )
        # Zero-arg, and deliberately unchecked. The SDK resolves credentials
        # from five places -- ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN,
        # ANTHROPIC_PROFILE, workload federation, and the profile `ant auth
        # login` leaves on disk -- and only the first two ever land on an
        # attribute we could read here. Testing those two told anyone using the
        # other three that they had no credentials, while holding a client that
        # worked. Only the request knows, so `_turn` asks it.
        self._sdk = anthropic
        self._client = anthropic.Anthropic()
        return self._client

    def _turn(self):
        self.turns += 1
        if self.turns > MAX_TURNS:
            self.set_state(FAILED)
            self.say(f"I stopped after {MAX_TURNS} steps without finishing.")
            return

        client = self._client_or_fail()
        self._connect()  # so the first tool call is not also the first connection
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=SYSTEM.format(name=self.name),
                tools=TOOLS,
                thinking={"type": "adaptive"},
                messages=self.messages,
            )
        except self._sdk.AuthenticationError as exc:
            raise RuntimeError(BAD_CREDENTIALS) from exc
        except TypeError as exc:
            # What the SDK raises when it found nothing to authenticate with.
            # Narrow, because a TypeError from anywhere else is a bug in here
            # and must not be dressed up as a missing key.
            if "authentication method" not in str(exc):
                raise
            raise RuntimeError(NO_CREDENTIALS) from exc
        self.spent[0] += response.usage.input_tokens
        self.spent[1] += response.usage.output_tokens
        self.messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text" and block.text.strip():
                self.say(block.text.strip())

        calls = [block for block in response.content if block.type == "tool_use"]
        if not calls:
            self._report_cost()
            self.set_state(DONE)
            return

        results = []
        for call in calls:
            if call.name == "ask_user":
                question = (call.input or {}).get("question", "").strip()
                self._pending_ask = call.id
                self._pending_results = results
                self.step("asked you a question")
                self.set_state(NEEDS_INPUT)
                self.say(question or "I need something from you to carry on.")
                return
            results.append(self._use(call))

        self.messages.append({"role": "user", "content": results})
        self.queue.append(self._turn)

    def _report_cost(self):
        self.step(f"{self.turns} model turns, "
                  f"{self.spent[0]:,} in / {self.spent[1]:,} out tokens")

    # -- the tools ----------------------------------------------------------

    def _use(self, call):
        """Run one tool. A failure is a result, not the end of the task: the
        model can read the error and try something else."""
        try:
            content = self._dispatch(call.name, call.input or {})
            return {"type": "tool_result", "tool_use_id": call.id, "content": content}
        except Exception as exc:
            detail = str(exc).strip().splitlines()[0][:200] or exc.__class__.__name__
            self.step(f"{call.name} failed: {detail}")
            return {
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": f"Error: {detail}",
                "is_error": True,
            }

    def _dispatch(self, name, args):
        page = self._connect()
        if name == "goto":
            url = args.get("url", "")
            self._goto(url)
            return f"Now at {page.url}, titled {page.title()!r}."
        if name == "read_page":
            return self._read(page)
        if name == "click":
            return self._click(page, args.get("text", ""))
        if name == "screenshot":
            return self._look(page)
        return f"Error: there is no tool called {name}."

    def _read(self, page):
        self.step("read the page")
        text = (page.inner_text("body") or "").strip()
        clipped = text[:PAGE_TEXT_CHARS]
        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.slice(0, 40).map(e => (e.innerText || '').trim() "
            "+ ' -> ' + e.href).filter(s => s.length > 4)",
        )
        more = "" if len(text) <= PAGE_TEXT_CHARS else "\n[text truncated]"
        return (f"Title: {page.title()}\nURL: {page.url}\n\n{clipped}{more}\n\n"
                f"Links:\n" + "\n".join(links))

    def _click(self, page, text):
        if not text:
            return "Error: click needs the visible text of something to click."
        self.step(f'clicked "{text}"')
        before = page.url
        page.get_by_text(text, exact=False).first.click(timeout=CLICK_TIMEOUT_MS)
        page.wait_for_load_state("domcontentloaded", timeout=NAV_TIMEOUT_MS)
        if page.url != before:
            self.report_url()
            return f"Clicked. The page went to {page.url}, titled {page.title()!r}."
        return f"Clicked. Still on {page.url}, titled {page.title()!r}."

    def _look(self, page):
        """A screenshot, as an image the model can actually see. This is the
        perception path the dashboard's tiles cannot provide: DWM composites
        those on the GPU and never hands Python a pixel."""
        data = page.screenshot(type="jpeg", quality=SHOT_QUALITY)
        self.step(f"screenshot, {len(data) // 1024} KB")
        return [{
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(data).decode("ascii"),
            },
        }]


class StandInAgent(Agent):
    """No browser to drive, so it makes everything up on a timer.

    This is what ran before there was CDP, kept because the fast checks want a
    child with no browser behind it. It is a placeholder; do not make it cleverer.
    """

    pace = STEP_S

    OPENING = "on it."
    QUESTION = ("before I go further: which plan should I compare against? "
                "I can only pick one.")
    ANSWER = "done — the Team plan is $20/month and it is the one marked recommended."
    FAILURE = "I gave up: the page stopped responding and three retries did not help."

    def start(self, prompt):
        self.say(self.OPENING)
        subject = prompt if len(prompt) <= 40 else prompt[:39] + "…"
        actions = [
            lambda: self.step("opened the start page"),
            lambda: self.step(f'searched for "{subject}"'),
        ]
        if "fail" in prompt.lower():
            actions += [
                lambda: self.step("clicked the first result"),
                lambda: self.step("timed out waiting for the page (1/3)"),
                lambda: self.step("timed out waiting for the page (3/3)"),
                lambda: self._finish(FAILED, self.FAILURE),
            ]
        elif self.tasks == 1:
            actions += [self._ask]
        else:
            actions += [
                lambda: self.step("read the results"),
                lambda: self.step('clicked "Pricing"'),
                lambda: self._finish(DONE, self.ANSWER),
            ]
        self.run(actions)

    def resume(self, answer):
        self.run([
            lambda: self.step(f"noted: {answer}"),
            lambda: self.step('clicked "Pricing"'),
            lambda: self.step("read the page"),
            lambda: self._finish(DONE, self.ANSWER),
        ])

    def _ask(self):
        self.set_state(NEEDS_INPUT)
        self.say(self.QUESTION)

    def _finish(self, state, text):
        self.set_state(state)
        self.say(text)


def _option(argv, flag):
    if flag in argv:
        index = argv.index(flag)
        if index + 1 < len(argv):
            return argv[index + 1]
    return None


def build(argv):
    """Pick the agent: a model if asked for and there is a browser to drive, the
    script if not, and the stand-in when there is no browser at all."""
    name = argv[1] if len(argv) > 1 else "box"
    endpoint = _option(argv, "--cdp")
    kind = _option(argv, "--agent") or "script"
    if not endpoint:
        return StandInAgent(name)
    if kind == "claude":
        return ModelAgent(name, endpoint)
    return BrowserAgent(name, endpoint)


def main():
    reader = pipes.LineReader(sys.stdin.buffer)
    agent = build(sys.argv)
    try:
        while True:
            for line in reader.lines():
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                kind = message.get("type")
                if kind == "input":
                    text = (message.get("text") or "").strip()
                    if text:
                        agent.on_input(text)
                elif kind == "cancel":
                    agent.on_cancel()
            if reader.closed:
                return 0  # the dashboard is gone
            agent.tick(time.monotonic())
            time.sleep(POLL_S)
    finally:
        # Playwright's driver is a child of this process; leaving without
        # stopping it would leave a node.exe behind every time.
        agent.close()


if __name__ == "__main__":
    sys.exit(main())
