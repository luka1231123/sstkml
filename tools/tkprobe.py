#!/usr/bin/env python3
"""Find which Tk operation kills the process. Run it from a real terminal.

    ./run.sh --probe

The game traps (SIGTRAP) when launched from Terminal.app but not from a
non-interactive shell, because Tk on macOS only becomes a full Aqua
application -- menu bar, activation, window server session -- in the first
case. That makes the failure invisible to anything running headless, so this
walks up to the game one operation at a time, each in its own process, and
reports the first step that does not come back.

Each step performs every step before it, so the first failure is the culprit.
"""
from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

STEPS = [
    "import tkinter",
    "Tk() then destroy",
    "Tk(), destroy, then Tk() again",
    "Tk() withdrawn, held open",
    "a Toplevel of a withdrawn root",
    "title and background colour",
    "query the font families",
    "a Text widget in the chosen font",
    "insert text with colour tags",
    "deiconify, lift, focus_force",
    "one turn of the real event loop",
    "the whole game, briefly",
    "the real entry point: available() then the game",
]


def perform(upto: int) -> None:
    """Do steps 1..upto in this process. Anything that traps, traps here."""
    import tkinter as tk                                    # 1

    if upto == 1:
        return
    if upto == 2:
        root = tk.Tk()
        root.destroy()
        return

    if upto == 3:
        # The bug this probe was written to find: a second root in the same
        # process after the first was destroyed. `main()` used to do exactly
        # this -- available() made one and threw it away, App made another.
        root = tk.Tk()
        root.destroy()
        root = tk.Tk()
        root.destroy()
        return

    root = tk.Tk()                                          # 4
    root.withdraw()
    if upto == 4:
        root.destroy()
        return

    window = tk.Toplevel(root)                              # 5
    if upto >= 6:                                           # 6
        window.title("probe")
        window.configure(bg="#16110d", padx=8, pady=6)

    family = "TkFixedFont"
    if upto >= 7:                                           # 7
        from tui.backend_tk import pick_font
        family, _size = pick_font(window, 14)

    text = None
    if upto >= 8:                                           # 8
        text = tk.Text(window, width=60, height=12, font=(family, 14),
                       bg="#16110d", fg="#d8c4a0", borderwidth=0,
                       highlightthickness=0, wrap="none")
        text.pack(fill="both", expand=True)

    if upto >= 9 and text is not None:                      # 9
        text.tag_configure("a", foreground="#e8a33d", background="#16110d")
        text.insert("end", "SAY TO THE KING, MY LORD\n", "a")
        text.insert("end", "granary  4,120 parisu\n")
        text.configure(state="disabled")

    if upto >= 10:                                          # 10
        window.deiconify()
        window.lift()
        window.focus_force()

    if upto >= 11:                                          # 11
        root.after(400, root.quit)
        root.mainloop()

    root.destroy()

    if upto >= 12:                                          # 12
        import play_gui
        game = play_gui.Game("ugarit", 8814402919)
        for _ in range(3):
            game.end_fortnight()
        game.on_key(type("K", (), {"char": "s", "keysym": "s"})())
        game.app.tk.after(800, game.app.stop)
        game.run()

    if upto >= 13:                                          # 13
        # What `./run.sh` actually does, in order. This is the step that used
        # to trap: available() made a root and destroyed it, then the game
        # made another. Steps 1-12 all missed it because none of them called
        # available() first.
        import play_gui
        from tui.backend_tk import available
        assert available()
        game = play_gui.Game("ugarit", 8814402919)
        game.app.tk.after(500, game.app.stop)
        game.run()


def _why(code: int) -> str:
    if code == 0:
        return "ok"
    if code < 0:
        name = signal.Signals(-code).name
        return f"KILLED by {name}"
    return f"exited {code}"


def main(argv: list[str]) -> int:
    if len(argv) > 2 and argv[1] == "--step":
        perform(int(argv[2]))
        print("ok")
        return 0

    print(f"probing with {sys.executable}\n")
    first_bad = None
    for number, label in enumerate(STEPS, start=1):
        done = subprocess.run(
            [sys.executable, __file__, "--step", str(number)],
            capture_output=True, text=True, cwd=str(ROOT))
        verdict = _why(done.returncode)
        print(f"  {number:>2}. {label:<38} {verdict}")
        if done.returncode != 0:
            first_bad = (number, label, done)
            break

    if first_bad is None:
        print("\nevery step survived. the crash is somewhere this does not "
              "reach\n-- say what you pressed before it died.")
        return 0

    number, label, done = first_bad
    print(f"\nit dies at step {number}: {label}")
    tail = (done.stderr or done.stdout or "").strip().splitlines()
    if tail:
        print("\n".join("    " + line for line in tail[-12:]))
    else:
        print("    no output at all, which means Tk aborted rather than raised.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
