"""Which dashboard to build.

Temporary, and it exists so both toolkits can be run on the same tree while the
Qt port is finished: `MULTIBOX_UI=qt` picks the new one, anything else the old.
Every entry point -- the app, both check suites, the demo -- asks here rather
than importing a package directly, so there is exactly one thing to delete when
`ui/` goes away.

An environment variable rather than a config key or a flag, deliberately: this
is a thing you set while working on the port, not a choice the app offers.
"""

import os

QT = "qt"
DEFAULT = "tk"


def chosen():
    return os.environ.get("MULTIBOX_UI", DEFAULT).strip().lower()


def app_class():
    """The App class for whichever dashboard is selected."""
    if chosen() == QT:
        from ui_qt.app import App
        return App
    from ui.app import App
    return App
