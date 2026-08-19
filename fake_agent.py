"""A scripted stand-in for an agent. It is not one, and must not become one.

No model call, no browser, no decisions: it walks a fixed script on a timer so
that the dashboard has something to render while the state vocabulary is being
settled. Everything it "does" is a string. M3 replaces it with a real subprocess
and this file goes away.

Two things about it are worth keeping when that happens:

  - The timer arrives as `schedule(delay_ms, callback)` rather than being
    imported, so this file has no idea Tkinter exists and the UI keeps its rule.
    A subprocess pump has the same shape.
  - Nothing here touches the box's page. The dashboard must never reach through
    `box.page`, and neither may its stand-in, or the seam will not be real when
    it matters.

The script it follows:

    every task    an opening line, then a few trajectory steps
    first task    stops in the middle and asks the user a question, to make the
                  needs-input state reachable without special effort
    "fail"        a prompt containing the word fails instead of finishing -- the
                  only way to see the failed state, and a deliberate cheat
    otherwise     finishes with an answer
"""

from session import DONE, FAILED, NEEDS_INPUT, WORKING

STEP_MS = 900

OPENING = "on it."
QUESTION = "before I go further: which plan should I compare against? I can only pick one."
ANSWER = "done — the Team plan is $20/month and it is the one marked recommended."
FAILURE = "I gave up: the page stopped responding and three retries did not help."


class FakeAgent:
    def __init__(self, session, schedule, on_change):
        self.session = session
        self.schedule = schedule
        self.on_change = on_change
        self._queue = []

    # -- input --------------------------------------------------------------

    def send(self, text):
        """Everything the user types arrives here.

        What it means depends on the state: an answer if the box asked a
        question, a new task if it is not doing one, and nothing at all if it is
        already working -- cancelling and queueing are M4's problem.
        """
        turn = self.session.user_says(text)
        if turn is None:
            return
        if self.session.wants_user:
            self._resume(turn.text)
        elif not self.session.busy:
            self._start(turn.text)
        self.on_change()

    # -- the script ---------------------------------------------------------

    def _start(self, prompt):
        session = self.session
        session.start_task()
        session.state = WORKING
        session.agent_says(OPENING)

        subject = prompt if len(prompt) <= 40 else prompt[:39] + "…"
        script = [
            self._step("opened the start page"),
            self._step(f'searched for "{subject}"'),
        ]
        if "fail" in prompt.lower():
            script += [
                self._step("clicked the first result"),
                self._step("timed out waiting for the page (1/3)"),
                self._step("timed out waiting for the page (3/3)"),
                self._finish(FAILED, FAILURE),
            ]
        elif session.tasks == 1:
            script += [self._ask()]
        else:
            script += [
                self._step("read the results"),
                self._step('clicked "Pricing"'),
                self._finish(DONE, ANSWER),
            ]
        self._run(script)

    def _resume(self, answer):
        session = self.session
        session.state = WORKING
        self._run([
            self._step(f"noted: {answer}"),
            self._step('clicked "Pricing"'),
            self._step("read the page"),
            self._finish(DONE, ANSWER),
        ])

    # -- actions, as thunks the timer runs later ----------------------------

    def _step(self, text):
        return lambda: self.session.step(text)

    def _ask(self):
        def action():
            self.session.state = NEEDS_INPUT
            self.session.agent_says(QUESTION)
        return action

    def _finish(self, state, text):
        def action():
            self.session.state = state
            self.session.agent_says(text)
        return action

    def _run(self, actions):
        # A new task abandons whatever the last one had queued.
        self._queue = list(actions)
        self.schedule(STEP_MS, self._pump)

    def _pump(self):
        if not self._queue:
            return
        self._queue.pop(0)()
        self.on_change()
        if self._queue:
            self.schedule(STEP_MS, self._pump)
