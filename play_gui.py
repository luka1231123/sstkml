"""The windowed game (M11, D33). `python3 play_gui.py [scenario] [seed]`

The hall is a real operating-system window and owns the session; every tablet
opens as another one, with its own title bar, moved and closed on its own. Put
the stores beside the letter that makes a claim about the stores and read both
at once -- that is what the windows are for.

Everything here is a thin shell over the same pieces the terminal game uses:
`advance`, `apply`, `project`, and a composition function per window. No engine
call lives in this file, so the headless path and this one cannot drift.

Falls back to the terminal with a message if there is no working Tk, rather
than dying with a traceback about a display name.
"""
from __future__ import annotations

import sys

if sys.version_info < (3, 12):
    # Apple's /usr/bin/python3 is old enough to lack tomllib, and the failure
    # it produces names a module rather than the mistake. Say the real thing.
    raise SystemExit(
        f"this is python {sys.version.split()[0]} at {sys.executable}.\n"
        "the game needs 3.12 or newer -- /usr/bin/python3 is Apple's and is "
        "too old.\nuse the project's own interpreter:  ./run.sh")

from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from session import new_seed
from tui import document, hall
from tui.grid import Screen

READ_COST = 2

# key -> (window key, title, size, how to compose it from Belief)
TABLETS: dict[str, tuple[str, str, tuple[int, int], object]] = {
    "s": ("stack", "The Stack", (80, 24), document.stack),
    "t": ("stores", "The Stores", (62, 22), document.stores),
    "r": ("roll", "The Roll", (78, 22), document.roll),
    "m": ("muster", "The Muster", (62, 18), document.muster),
}


class Game:
    """World, Belief, the fortnight's hours, and the windows open on them."""

    def __init__(self, scenario: str = "ugarit", seed: int | None = None) -> None:
        from tui.backend_tk import App

        self.seed = new_seed() if seed is None else seed
        seed = self.seed
        self.world = load_scenario(scenario, seed)
        self.world, _ = advance(self.world)
        self.hours = project(self.world)["attention"]
        self.log: list[dict] = []
        self.app = App()
        self.open_letters: dict[str, dict] = {}
        # The pile's display order, held steady across the fortnight so the
        # numbers do not move under the player's finger (see document.order_of).
        self.stack_order: list[str] = document.order_of(project(self.world))

        self.hall_window = self.app.window(
            "hall", f"Say to the King, my lord — seed {seed}", 92, 30,
            on_key=self.on_key, on_close=self.quit)
        self.repaint()
        # A Tk program launched from a terminal opens *behind* the terminal on
        # macOS, which is indistinguishable from nothing having happened.
        self.hall_window.present()

    # --- state ---------------------------------------------------------------

    @property
    def belief(self) -> dict:
        return project(self.world)

    def do(self, action, cost: int = 0) -> bool:
        """Apply an action if the hours are there. Logged the same way the
        headless driver logs it, so a session here saves and replays."""
        if cost > self.hours:
            return False
        self.world, _ = apply(self.world, action)
        self.hours -= cost
        self.log.append({"turn": self.world.date.absolute,
                         "action": A.to_dict(action)})
        self.repaint()
        return True

    def end_fortnight(self) -> None:
        self.world, _ = advance(self.world)
        self.hours = self.belief["attention"]
        self.stack_order = document.order_of(self.belief, self.stack_order)
        self.open_letters.clear()
        for key in [k for k in self.app.windows if k.startswith("letter:")]:
            self.app.close(key)
        self.repaint()

    # --- windows -------------------------------------------------------------

    def compose(self, key: str) -> Screen | None:
        b = self.belief
        if key == "hall":
            return hall.compose(b, 92, 30, hours_left=self.hours)
        if key == "stack":
            return document.stack(b, 80, 24, order=self.stack_order)
        for _, (window_key, _title, (w, h), how) in TABLETS.items():
            if key == window_key:
                return how(b, w, h)
        if key.startswith("letter:"):
            item = self.open_letters.get(key)
            return None if item is None else document.tablet(
                item, house=b.get("house"))
        return None

    def repaint(self) -> None:
        for key, window in list(self.app.windows.items()):
            if not window.root.winfo_exists():
                self.app.windows.pop(key, None)
                continue
            screen = self.compose(key)
            if screen is not None:
                window.paint(screen)

    def open_tablet(self, char: str) -> None:
        window_key, title, (w, h), _how = TABLETS[char]
        window = self.app.window(
            window_key, title, w, h,
            on_key=lambda e, k=window_key: self.on_tablet_key(e, k),
            on_close=lambda k=window_key: self.app.close(k))
        self.repaint()
        window.focus()

    def open_letter(self, item: dict) -> None:
        key = f"letter:{item['id']}"
        self.open_letters[key] = item
        window = self.app.window(
            key, f"Tablet — {item['id']}", 62, 26,
            on_key=lambda e, k=key: self.on_tablet_key(e, k),
            on_close=lambda k=key: self.app.close(k))
        self.repaint()
        window.focus()

    # --- keys ----------------------------------------------------------------

    def on_key(self, event) -> None:
        char = (event.char or "").lower()
        if event.keysym == "space":
            self.end_fortnight()
        elif char in TABLETS:
            self.open_tablet(char)
        elif char == "q":
            self.quit()

    def on_tablet_key(self, event, key: str) -> None:
        """Tablets close on esc, and the stack reads by number.

        Reading costs hours, so the stack is where attention is actually spent
        and the refusal is silent: a king with one hour left simply cannot open
        another tablet, and nothing explains why.
        """
        if event.keysym == "Escape":
            self.app.close(key)
            return
        char = (event.char or "").lower()
        if key == "stack" and char.isdigit() and char != "0":
            index = int(char) - 1
            if not 0 <= index < len(self.stack_order):
                return
            letter_id = self.stack_order[index]
            item = next((i for i in self.belief["stack"] if i["id"] == letter_id),
                        None)
            if item is None:
                return
            if not item["read"] and not self.do(A.ReadLetter(letter_id), READ_COST):
                return                  # no hours; silently, and D19 says so
            self.open_letter(
                next(i for i in self.belief["stack"] if i["id"] == letter_id))
        else:
            self.on_key(event)

    def quit(self) -> None:
        """The hall owns the session; every other window closes freely (D33)."""
        self.app.stop()

    def run(self) -> None:
        self.app.run()


def report(check: dict) -> None:
    print("  interpreter :", check["interpreter"])
    print("  python      :", check["version"],
          "(in a venv)" if check["in_venv"] else "(NOT in a venv)")
    print("  tkinter     :", check["tkinter"],
          f"Tk {check['tk_version']}" if check["tk_version"] else "")
    print("  display     :", check["display"])


def main(argv: list[str]) -> int:
    from tui.backend_tk import available, diagnose

    if "--check" in argv:
        report(diagnose())
        return 0
    if not available():
        check = diagnose()
        print("the window game cannot start on this interpreter.\n")
        report(check)
        print("\nthe usual cause is the wrong python: /usr/bin/python3 is "
              "Apple's and has no Tk\nat all, and homebrew's ships without it "
              "unless python-tk is installed.\n"
              "\n  ./run.sh              use the project's own venv\n"
              "  brew install python-tk@3.14\n"
              "  apt install python3-tk        (debian/ubuntu)\n"
              "\nthe terminal game is unaffected:  ./run.sh --cli")
        return 1
    args = [a for a in argv[1:] if not a.startswith("-")]
    scenario = args[0] if args else "ugarit"
    seed = int(args[1]) if len(args) > 1 else new_seed()
    print(f"seed {seed} — pass it back to play this same world again:\n"
          f"  ./run.sh {scenario} {seed}")
    Game(scenario, seed).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
