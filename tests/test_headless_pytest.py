"""The ordinary pytest process must never create a native window."""
from __future__ import annotations

import pytest


def test_gui_construction_stops_before_tk_opens_a_window() -> None:
    from tui import backend_tk

    # Importing the game and constructing its App are both harmless.  The
    # first operation that would need a native window is refused before Tk.
    import play_gui
    assert play_gui.Game
    app = backend_tk.App()
    assert app.windows == {}

    assert backend_tk.headless()
    assert not backend_tk.available()
    assert backend_tk._ROOT is None
    with pytest.raises(RuntimeError, match="disabled during automated tests"):
        app.window("hall", "The Hall", 92, 30)
    assert backend_tk._ROOT is None
