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

import os
import sys
from pathlib import Path

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
from ai import librarian
from tui import (altar, archive, composer, counsel, document, hall,
                 help as help_page, render, worldmap)
from tui.grid import Screen

READ_COST = 2
REPLY_COST = 2
OMEN_COST = 2
SEARCH_COST = 1

# Where `STK_DUMP=1` writes what the windows are showing, for `tools/screens.py
# live`. A running game is otherwise unreadable from outside without a camera.
DUMP = Path(__file__).parent / "saves" / "screens.txt"

# key -> (window key, title, size, how to compose it from Belief)
TABLETS: dict[str, tuple[str, str, tuple[int, int], object]] = {
    "s": ("stack", "The Stack", (80, 24), document.stack),
    "t": ("stores", "The Stores", (62, 22), document.stores),
    "r": ("roll", "The Roll", (78, 22), document.roll),
    "m": ("muster", "The Muster", (62, 18), document.muster),
    "o": ("oaths", "The Oaths", (76, 28), document.oaths),
    "l": ("land", "The Land", (70, 24), document.land),
    "h": ("house", "The House", (70, 26), document.house),
    "?": ("help", "Help", (74, 44),
          lambda b, w=74, h=44: help_page.compose(w, h)),
}

# The windows that hold a conversation: they own their own keys, because most
# of them take typing and none of them can afford to fall through to the hall's
# door list. key -> (window key, title, size, which handler)
ROOMS: dict[str, tuple[str, str, tuple[int, int], str]] = {
    "w": ("world", "The Known World", (86, 30), "on_tablet_key"),
    "c": ("counsel", "Counsel", (80, 32), "on_counsel_key"),
    "v": ("altar", "The Altar", (78, 32), "on_altar_key"),
    "a": ("archive", "The Tablet House", (84, 32), "on_archive_key"),
}

# The hall advertises every door and marks the ones that are not built (D33:
# never strand the player). The two lists must not drift, so the controller
# reads the hall's rather than keeping a second one. The desk is reached from a
# letter rather than from a key of its own, so it is listed by hand.
assert {target for _k, _l, target in hall.DOORS if target in hall.BUILT} == (
    {window_key for window_key, _t, _s, _how in TABLETS.values()}
    | {window_key for window_key, _t, _s, _h in ROOMS.values()} | {"desk"})


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
        self.events: list[str] = []
        # The windows that hold a conversation rather than a record. All of it
        # is session state: none of it is a fact about the kingdom, so none of
        # it is logged and a replay is unaffected.
        self.desk: dict | None = None
        self.counsel_said: list[tuple[str, str]] = []
        self.altar_readings: list[str] = []
        self.altar_question = "harvest"
        self.altar_offering: tuple[str, int] | None = None
        self.archive_query = ""
        self.archive_hits: list[dict] = []
        self.archive_summary = ""
        self.archive_typing = False
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
        self.world, events = advance(self.world)
        self.hours = self.belief["attention"]
        self.stack_order = document.order_of(self.belief, self.stack_order)
        self.open_letters.clear()
        for key in [k for k in self.app.windows if k.startswith("letter:")]:
            self.app.close(key)
        # The fortnight gets its own window rather than a silent redraw. It is
        # the only moment in the game the player does not control, and it
        # should feel like one.
        self.events = render.events_lines(events, self.world.court)
        window = self.app.window(
            "fortnight", "The fortnight turns", 66, 18,
            on_key=lambda e: self.on_tablet_key(e, "fortnight"),
            on_close=lambda: self.app.close("fortnight"))
        self.repaint()
        window.focus()

    # --- windows -------------------------------------------------------------

    def compose(self, key: str) -> Screen | None:
        b = self.belief
        if key == "hall":
            return hall.compose(b, 92, 30, hours_left=self.hours)
        if key == "stack":
            return document.stack(b, 80, 24, order=self.stack_order)
        if key == "fortnight":
            return document.fortnight(b, self.events, 66, 18)
        if key == "world":
            return worldmap.compose(b, 86, 30)
        if key == "counsel":
            return counsel.compose(b, self.counsel_said, self.hours, 80, 32)
        if key == "altar":
            return altar.compose(b, self.altar_readings, self.altar_question,
                                 self.altar_offering, 78, 32)
        if key == "archive":
            return archive.compose(b, self.archive_query, self.archive_hits,
                                   self.archive_summary, self.archive_typing,
                                   84, 32)
        if key == "desk" and self.desk is not None:
            item = next((i for i in b["stack"]
                         if i["id"] == self.desk["letter_id"]), None)
            if item is not None:
                return composer.compose(
                    item, self.desk["draft"], self.desk["intent"],
                    self.desk["dictating"], house=b.get("house"),
                    width=84, height=30)
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
        if os.environ.get("STK_DUMP") == "1":
            self.dump()

    def dump(self) -> None:
        """Write every open window to `saves/screens.txt`, as text.

        Best effort: a game that cannot write its debug file should still be
        playable, so nothing here is allowed to interrupt a repaint.
        """
        try:
            DUMP.parent.mkdir(parents=True, exist_ok=True)
            b = self.belief
            head = (f"seed {self.seed} · turn {self.world.date.absolute} · "
                    f"{self.hours} of {b['attention']} hours left\n\n")
            DUMP.write_text(head + self.app.transcript() + "\n")
        except Exception:
            pass

    def open_tablet(self, char: str) -> None:
        window_key, title, (w, h), _how = TABLETS[char]
        window = self.app.window(
            window_key, title, w, h,
            on_key=lambda e, k=window_key: self.on_tablet_key(e, k),
            on_close=lambda k=window_key: self.app.close(k))
        self.repaint()
        window.focus()

    def open_room(self, char: str) -> None:
        """A conversation window. It binds its own handler and never shares."""
        window_key, title, (w, h), handler = ROOMS[char]
        window = self.app.window(
            window_key, title, w, h, on_key=getattr(self, handler)
            if handler != "on_tablet_key"
            else (lambda e, k=window_key: self.on_tablet_key(e, k)),
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

    # --- the desk ------------------------------------------------------------

    def open_desk(self, letter_id: str) -> None:
        """Answer a letter. The tablet is not committed until it is sealed."""
        item = next((i for i in self.belief["stack"] if i["id"] == letter_id),
                    None)
        if item is None or self.hours < REPLY_COST:
            return                       # silently, as everywhere (D19)
        self.desk = {
            "letter_id": letter_id,
            "intent": composer.INTENTS[0],
            "dictating": False,
            "dictated": False,
            "buffer": "",
            "draft": composer.formulary(
                item["sender"], composer.INTENTS[0], self.seed,
                self.world.date.absolute),
        }
        window = self.app.window(
            "desk", f"The Desk — to {render.actor_name(item['sender'])}",
            84, 30,
            on_key=self.on_desk_key,
            on_close=lambda: self.app.close("desk"))
        self.repaint()
        window.focus()

    def _regrade(self) -> None:
        """Recompose the draft from whatever the desk is currently holding."""
        item = next(i for i in self.belief["stack"]
                    if i["id"] == self.desk["letter_id"])
        # Once the king has taken the stylus the tablet is his. Finishing
        # dictation used to fall back to the formulary, which silently threw
        # away everything he had just said.
        if self.desk["dictating"] or self.desk["dictated"]:
            self.desk["draft"] = composer.dictated(
                self.desk["buffer"], item["sender"])
        else:
            self.desk["draft"] = composer.formulary(
                item["sender"], self.desk["intent"], self.seed,
                self.world.date.absolute)

    def on_desk_key(self, event) -> None:
        """The one window that takes typing, so it owns every key it sees.

        Nothing here falls through to `on_key`: a king who types `q` into a
        letter means the letter q, and a controller that quits instead has lost
        the tablet he was writing.
        """
        desk = self.desk
        if desk is None:
            return
        if event.keysym == "Escape":
            self.desk = None
            self.app.close("desk")
            return
        if desk["dictating"]:
            if event.keysym in ("BackSpace", "Delete"):
                desk["buffer"] = desk["buffer"][:-1]
            elif event.keysym == "Return":
                desk["buffer"] += "\n"
            elif event.state & 4 and event.keysym in ("d", "D"):
                desk["dictating"] = False       # ctrl-d: done dictating
                desk["dictated"] = True
            elif event.char and event.char.isprintable():
                desk["buffer"] += event.char
            else:
                return
            self._regrade()
            self.repaint()
            return

        char = (event.char or "").lower()
        if event.keysym == "Tab":
            order = composer.INTENTS
            desk["intent"] = order[
                (order.index(desk["intent"]) + 1) % len(order)]
            # Changing what you mean asks the scribe for a fresh draft, and
            # that discards a dictation. It is the one destructive key here,
            # which is why it is the one that is easy to reach and hard to hit
            # by accident.
            desk["dictated"] = False
            self._regrade()
        elif char == "d":
            desk["dictating"] = True
            desk["dictated"] = True
            desk["buffer"] = desk["draft"].text
            self._regrade()
        elif event.keysym == "Return":
            draft = desk["draft"]
            sealed = self.do(A.DictateReply(
                desk["letter_id"], desk["intent"], draft.text, draft.profile,
                draft.score.total, draft.score.violations), REPLY_COST)
            if sealed:
                self.desk = None
                self.app.close("desk")
                self.hall_window.focus()
            return
        else:
            return
        self.repaint()

    # --- counsel, the altar, the tablet house --------------------------------

    def ask_counsel(self, topic: str, question: str) -> None:
        """An hour for an answer he gives from memory.

        No engine action: a conversation changes nothing in the world, and the
        hours are session state (attention is derived — see `hall.compose`). So
        nothing goes in the log and a replay is unaffected.
        """
        if self.hours < counsel.ASK_COST:
            return
        self.hours -= counsel.ASK_COST
        self.counsel_said.append(("king", question))
        self.counsel_said.append(("scribe", counsel.answer(
            self.belief, topic, self.seed, self.world.date.absolute)))
        self.repaint()

    def on_counsel_key(self, event) -> None:
        if event.keysym == "Escape":
            self.app.close("counsel")
            return
        char = event.char or ""
        for key, question, topic in counsel.QUESTIONS:
            if char == key:
                self.ask_counsel(topic, question)
                return

    def on_altar_key(self, event) -> None:
        if event.keysym == "Escape":
            self.app.close("altar")
            return
        char = (event.char or "").lower()
        for key, _label, topic in altar.QUESTIONS:
            if char == key:
                self.altar_question = topic
                self.repaint()
                return
        for key, good, quantity in altar.OFFERINGS:
            if char == key:
                self.altar_offering = (good, quantity)
                self.repaint()
                return
        if event.keysym == "Return":
            good, quantity = self.altar_offering or ("", 0)
            events = []
            if self.hours >= OMEN_COST:
                before = self.world
                self.world, events = apply(self.world, A.ConsultDiviner(
                    self.altar_question, "", good, quantity))
                if self.world is not before:
                    self.hours -= OMEN_COST
                    self.log.append(
                        {"turn": self.world.date.absolute,
                         "action": A.to_dict(A.ConsultDiviner(
                             self.altar_question, "", good, quantity))})
            taken = next((e for e in events
                          if isinstance(e, A.OmenTaken)), None)
            if taken is not None:
                self.altar_readings.append(
                    f"He reads the liver and says: {taken.reported}.")
            self.repaint()

    def on_archive_key(self, event) -> None:
        if event.keysym == "Escape":
            if self.archive_typing:
                self.archive_typing = False
                self.repaint()
                return
            self.app.close("archive")
            return
        if self.archive_typing:
            if event.keysym in ("BackSpace", "Delete"):
                self.archive_query = self.archive_query[:-1]
            elif event.keysym == "Return":
                self.archive_typing = False
                self.search_archive()
                return
            elif event.char and event.char.isprintable():
                self.archive_query += event.char
            else:
                return
            self.repaint()
            return
        if (event.char or "") == "/":
            self.archive_typing = True
            self.archive_query = ""
            self.repaint()
        elif event.keysym == "Return":
            self.search_archive()

    def search_archive(self) -> None:
        """One hour per query (spec 6.17), and the hour is the mechanic."""
        query = self.archive_query.strip().lower()
        if not query or not self.do(A.SearchArchive(query), SEARCH_COST):
            self.repaint()
            return
        hits = self.belief.get("archive_index", {}).get("hits", {}).get(query, [])
        self.archive_hits = hits
        self.archive_summary = librarian.fallback_summary(query, hits)
        self.repaint()

    # --- keys ----------------------------------------------------------------

    def on_key(self, event) -> None:
        char = (event.char or "").lower()
        if event.keysym == "space":
            self.end_fortnight()
        elif char in TABLETS:
            self.open_tablet(char)
        elif char in ROOMS:
            self.open_room(char)
        elif char == "d":
            # The desk without a letter chosen answers the oldest thing on the
            # pile, which is what a king with a stack in front of him does.
            read = [item for item in self.belief["stack"] if item["read"]]
            if read:
                self.open_desk(read[0]["id"])
        elif char == "\\":
            # Read the windows out loud. Not a game verb: it costs no hours,
            # changes nothing, and is how a player reports what he was looking
            # at when something went wrong.
            self.dump()
            print(self.app.transcript(), flush=True)
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
        if key == "fortnight" and event.keysym == "space":
            # Space in this window means "I have read it", not "again".
            self.app.close(key)
            self.hall_window.focus()
            return
        char = (event.char or "").lower()
        if key.startswith("letter:") and char == "a":
            # Answer the tablet you are looking at. The desk opens beside it,
            # so the claim being answered stays on screen while it is answered.
            self.open_desk(key.split(":", 1)[1])
            return
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
