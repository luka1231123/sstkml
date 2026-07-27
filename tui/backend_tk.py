"""Window backend: a `Screen` in a real operating-system window (D33, spec 9.6).

This is the shipped path. Each `GridWindow` is a genuine OS window with its own
title bar and its own entry in the taskbar, moved and closed on its own, so the
player can put the granary beside the letter that makes a claim about it. That
side-by-side reading is the whole reason D33 paid for OS windows.

Tk is imported lazily and only here. Nothing else in the project may import it,
so the headless suite, `session.replay` and the terminal backend never touch a
display -- which is what lets the interface be tested by asserting cells.

Rendering is a `Text` widget with one tag per (fg, bg) pair actually used. A
font-atlas blit onto a `Canvas` can replace the innards later without anything
above this file noticing; that is the point of the grid being a type.
"""
from __future__ import annotations

import os
import platform
import subprocess

from tui.grid import InteractiveScreen, RGB, Screen, ScreenLike, cells

# One monospace family per platform, first that exists wins. Tk silently
# substitutes an unknown family, and a proportional substitution would shear
# every column in the game, so the fallback chain ends somewhere guaranteed.
FONT_STACK = (
    "Menlo", "DejaVu Sans Mono", "Consolas", "Liberation Mono",
    "Courier New", "TkFixedFont",
)


# The one Tk root this process will ever have.
#
# Creating a root, destroying it, and creating another in the same process
# aborts on macOS Aqua -- SIGTRAP, no traceback, nothing on stderr. That is
# exactly what `main()` used to do: `available()` made a root to test with and
# threw it away, then `App` made a second one to play in. So the root is made
# once, withdrawn, shared by everything, and never destroyed.
_ROOT = None


def _root():
    global _ROOT
    if _ROOT is None:
        import tkinter as tk
        _ROOT = tk.Tk()
        _ROOT.withdraw()
    return _ROOT


def _hex(index: int) -> str:
    return f"#{RGB[index]}"


def _activate_process() -> None:
    """Ask macOS to bring this process to the front. Best effort, never fatal.

    Tk cannot do this for itself: a python launched from a terminal is a
    background application as far as the window server is concerned, so its
    windows open behind whatever is already there.
    """
    if platform.system() != "Darwin":
        return
    try:
        subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to set frontmost of every '
             f"process whose unix id is {os.getpid()} to true"],
            check=False, capture_output=True, timeout=3)
    except Exception:
        pass


def pick_font(root, size: int = 14) -> tuple[str, int]:
    """First family in the stack the toolkit actually has."""
    from tkinter import font as tkfont
    available = {name.lower() for name in tkfont.families(root)}
    for family in FONT_STACK:
        if family.lower() in available or family == "TkFixedFont":
            return family, size
    return "TkFixedFont", size


class GridWindow:
    """One OS window showing one `Screen`.

    `on_key` receives a `tkinter.Event`; `on_close` is called when the player
    closes the window from its own title bar, which every window except the
    hall must survive (D33: closing the hall ends the session, closing anything
    else is free).
    """

    def __init__(self, app, title: str, width: int, height: int,
                 on_key=None, on_close=None, font_size: int = 14) -> None:
        import tkinter as tk

        self.app = app
        self.title = title
        self.width = width
        self.height = height
        self._tags: set[str] = set()
        self.hits = ()
        self.on_key = on_key
        # The last screen painted, kept so the window can be *read* rather than
        # screenshotted (`tools/screens.py live`). One rectangle of tuples per
        # window; it costs nothing and it is the only way to see what a running
        # game is actually showing.
        self.last: Screen | None = None

        # Always a Toplevel, never the interpreter's root. The App holds a
        # withdrawn root of its own, so that closing *any* window -- including
        # the hall -- is an ordinary event the controller decides about, rather
        # than a destruction of the toolkit that happens to end the process.
        self.root = tk.Toplevel(app.root())
        self.root.title(title)
        self.root.configure(bg=_hex(0), padx=8, pady=6)

        family, size = pick_font(self.root, font_size)
        self.text = tk.Text(
            self.root, width=width, height=height,
            font=(family, size), bg=_hex(0), fg=_hex(1),
            borderwidth=0, highlightthickness=0, padx=0, pady=0,
            wrap="none", cursor="arrow", insertwidth=0,
            spacing1=0, spacing2=0, spacing3=0,
        )
        self.text.pack(fill="both", expand=True)
        self.text.configure(state="disabled")

        # Keys are bound on the window, not the widget, so a click anywhere in
        # the window keeps typing working.
        if on_key is not None:
            self.root.bind("<Key>", on_key)
            self.text.bind("<Button-1>", self._click)
            self.text.bind("<Motion>", self._motion)
            self.text.bind(
                "<Leave>",
                lambda _event: self.text.configure(cursor="arrow"))
        self.root.protocol(
            "WM_DELETE_WINDOW", on_close or self.close)

    def _tag(self, fg: int, bg: int) -> str:
        name = f"c{fg}_{bg}"
        if name not in self._tags:
            self.text.tag_configure(name, foreground=_hex(fg), background=_hex(bg))
            self._tags.add(name)
        return name

    @staticmethod
    def _event_for_command(command: str):
        """Return the small Tk-event-shaped value all key handlers expect."""
        state = 0
        if command.startswith("Control-") and len(command) == len("Control-x"):
            keysym = command[-1]
            char, state = chr(ord(keysym) - 96), 4
        elif command in {"Escape", "Return", "Tab", "BackSpace", "space"}:
            char = " " if command == "space" else ""
            keysym = command
        else:
            char = command
            keysym = command
        return type("CommandEvent", (), {
            "char": char, "keysym": keysym, "state": state,
            "command": command})()

    def _cell_at(self, event) -> tuple[int, int]:
        line, column = self.text.index(
            f"@{event.x},{event.y}").split(".", 1)
        return int(column), int(line) - 1

    def _command_at(self, x: int, y: int) -> str | None:
        for hit in reversed(self.hits):
            if hit.enabled and hit.contains(x, y):
                return hit.command
        return None

    def _click(self, event) -> str:
        command = self._command_at(*self._cell_at(event))
        if command == "focus":
            self.root.focus_force()
            return "break"
        if command and self.on_key is not None:
            self.on_key(self._event_for_command(command))
        return "break"

    def _motion(self, event) -> None:
        command = self._command_at(*self._cell_at(event))
        self.text.configure(cursor="hand2" if command else "arrow")

    def paint(self, screen: ScreenLike) -> None:
        """Replace the contents with one screen.

        Runs of identical (fg, bg) are inserted as single spans, so a row of
        ordinary text costs one insert rather than one per cell.
        """
        self.last = cells(screen)
        self.hits = screen.hits if isinstance(screen, InteractiveScreen) else ()
        grid = cells(screen)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for y, row in enumerate(grid):
            run: list[str] = []
            current: tuple[int, int] | None = None
            for glyph, fg, bg in row:
                if (fg, bg) != current:
                    if run:
                        self.text.insert("end", "".join(run), self._tag(*current))
                    run, current = [], (fg, bg)
                run.append(glyph)
            if run and current is not None:
                self.text.insert("end", "".join(run), self._tag(*current))
            if y != len(grid) - 1:
                self.text.insert("end", "\n")
        self.text.configure(state="disabled")

    def focus(self) -> None:
        self.root.lift()
        self.root.focus_force()

    def present(self) -> None:
        """Bring the window to the front, conservatively.

        A Tk program started from a terminal on macOS opens behind the terminal,
        which reads exactly like nothing having happened. `deiconify` + `lift` +
        `focus_force` is the portable, boring way to fix that and is all this
        does by default.

        It used to also toggle `-topmost` and drive `osascript` at System Events
        to make the process frontmost. Both are removed from the default path:
        `-topmost` is a thin, platform-specific corner of Tk, and the osascript
        route needs Accessibility permission for whichever terminal launched the
        game, so it can block for seconds or raise a permission dialog on one
        machine and do nothing on another. Neither is worth a crash on start-up,
        and the game is not important enough to steal focus by force.

        Set `STK_FORCE_FRONT=1` to opt back into the aggressive raise.
        """
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if os.environ.get("STK_FORCE_FRONT") == "1":
            try:
                self.root.attributes("-topmost", True)
                self.root.after(
                    300, lambda: self.root.winfo_exists()
                    and self.root.attributes("-topmost", False))
            except Exception:
                pass
            _activate_process()

    def close(self) -> None:
        """Destroy the window, but never from inside its own event handler.

        Escape is bound on this window and closing is what it does, so the
        naive `destroy()` tears the widget down while Tcl is still dispatching
        an event on it -- undefined behaviour, and on macOS an occasional
        segfault rather than an exception. `after_idle` lets the current event
        finish first.
        """
        if self.root.winfo_exists():
            self.root.after_idle(self.root.destroy)


class App:
    """Owns the Tk main loop and the windows open on it.

    No window is structurally special: they are all Toplevels of a withdrawn
    root. That the hall ends the session when closed is a policy the controller
    states by passing `on_close=quit`, not a consequence of it having been
    created first. Every other window closes freely and must always be
    reachable again from the hall by keyboard (D33).
    """

    def __init__(self) -> None:
        self.tk = None
        self.windows: dict[str, GridWindow] = {}

    def root(self):
        """The hidden interpreter root every window hangs off.

        Withdrawn and never shown, so that no player-visible window is
        structurally special and the game can close its last window without
        taking Tk down. Shared process-wide: see `_root`.
        """
        self.tk = _root()
        return self.tk

    def window(self, key: str, title: str, width: int, height: int,
               **kwargs) -> GridWindow:
        """Open a window, or raise and return the one already open under `key`."""
        existing = self.windows.get(key)
        if existing is not None and existing.root.winfo_exists():
            existing.focus()
            return existing
        window = GridWindow(self, title, width, height, **kwargs)
        self.windows[key] = window
        return window

    def close(self, key: str) -> None:
        window = self.windows.pop(key, None)
        if window is not None:
            window.close()

    def transcript(self) -> str:
        """Everything currently on screen, as text, in the order it was opened.

        The counterpart to asserting cells in the headless suite: this reads a
        window that is genuinely open, so a disagreement between it and
        `tools/screens.py hall` means the controller painted something other
        than what the composer would produce -- which is the only class of bug
        the headless tests structurally cannot see.
        """
        from tui.grid import plain_text

        parts = []
        for key, window in self.windows.items():
            if window.last is None or not window.root.winfo_exists():
                continue
            rule = "─" * max(0, 60 - len(window.title))
            parts.append(f"── {window.title} [{key}] {rule}\n"
                         + plain_text(window.last))
        return "\n\n".join(parts)

    def run(self) -> None:
        if self.tk is None:
            return
        try:
            self.tk.mainloop()
        finally:
            self.shutdown()

    def stop(self) -> None:
        """End the session. Only the hall calls this (D33).

        `quit` and not `destroy`: this is called from inside an event handler,
        and tearing the interpreter down mid-dispatch is how a clean exit turns
        into a segfault. It leaves the main loop; `run` does the destroying
        afterwards, when nothing is on the stack.
        """
        if self.tk is not None:
            self.tk.quit()

    def shutdown(self) -> None:
        """Close this App's windows once the main loop has returned.

        The shared root is deliberately *not* destroyed: another App in the
        same process would then have to make a second one, which is the abort
        this whole arrangement exists to avoid. Tk goes down when the process
        does, with no windows left holding it.
        """
        try:
            for window in list(self.windows.values()):
                if window.root.winfo_exists():
                    window.root.destroy()
        except Exception:
            pass
        finally:
            self.windows.clear()


def diagnose() -> dict:
    """Everything needed to tell a broken install from a broken game."""
    import sys
    report = {
        "interpreter": sys.executable,
        "version": sys.version.split()[0],
        "in_venv": sys.prefix != sys.base_prefix,
        "tkinter": "missing",
        "tk_version": "",
        "display": "no",
    }
    try:
        import tkinter
    except Exception as error:
        report["tkinter"] = f"missing ({type(error).__name__})"
        return report
    report["tkinter"] = "present"
    report["tk_version"] = str(tkinter.TkVersion)
    try:
        _root()                      # made once, kept; never made twice
        report["display"] = "yes"
    except Exception as error:
        report["display"] = f"no ({type(error).__name__}: {error})"
    return report


def available() -> bool:
    """Whether a display and a working Tk are both present.

    Called before choosing a backend so the game falls back to the terminal on
    a headless box rather than dying with a traceback about a display name.
    """
    try:
        import tkinter                                  # noqa: F401
        _root()
        return True
    except Exception:
        return False
