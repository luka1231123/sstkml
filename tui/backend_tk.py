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

from tui.grid import RGB, Screen

# One monospace family per platform, first that exists wins. Tk silently
# substitutes an unknown family, and a proportional substitution would shear
# every column in the game, so the fallback chain ends somewhere guaranteed.
FONT_STACK = (
    "Menlo", "DejaVu Sans Mono", "Consolas", "Liberation Mono",
    "Courier New", "TkFixedFont",
)


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
        self.width = width
        self.height = height
        self._tags: set[str] = set()

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
        self.root.protocol(
            "WM_DELETE_WINDOW", on_close or self.close)

    def _tag(self, fg: int, bg: int) -> str:
        name = f"c{fg}_{bg}"
        if name not in self._tags:
            self.text.tag_configure(name, foreground=_hex(fg), background=_hex(bg))
            self._tags.add(name)
        return name

    def paint(self, screen: Screen) -> None:
        """Replace the contents with one screen.

        Runs of identical (fg, bg) are inserted as single spans, so a row of
        ordinary text costs one insert rather than one per cell.
        """
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for y, row in enumerate(screen):
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
            if y != len(screen) - 1:
                self.text.insert("end", "\n")
        self.text.configure(state="disabled")

    def focus(self) -> None:
        self.root.lift()
        self.root.focus_force()

    def present(self) -> None:
        """Bring the window to the front, and mean it.

        A Tk program started from a terminal on macOS opens behind the terminal
        and does not take the keyboard, which reads exactly like nothing having
        happened. Raising is therefore three separate things: lift it, hold it
        on top for a moment so the window manager cannot bury it again, and ask
        the operating system to make this process frontmost.
        """
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(300, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()
        _activate_process()

    def close(self) -> None:
        self.root.destroy()


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

        It is withdrawn and never shown: it exists so that no player-visible
        window is structurally special, and so the game can close its last
        window without taking Tk down with it.
        """
        if self.tk is None:
            import tkinter as tk
            self.tk = tk.Tk()
            self.tk.withdraw()
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
        if window is not None and window.root.winfo_exists():
            window.close()

    def run(self) -> None:
        if self.tk is not None:
            self.tk.mainloop()

    def stop(self) -> None:
        """End the session. Only the hall calls this (D33)."""
        if self.tk is not None:
            self.tk.quit()


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
        root = tkinter.Tk()
        root.destroy()
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
        import tkinter
        root = tkinter.Tk()
        root.destroy()
        return True
    except Exception:
        return False
