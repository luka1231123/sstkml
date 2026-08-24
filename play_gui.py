"""The windowed game. `python3 play_gui.py [chosen_alu] [seed]`

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
import queue
import sys
import threading
from pathlib import Path

if sys.version_info < (3, 12):
    # Apple's /usr/bin/python3 is old enough to lack tomllib, and the failure
    # it produces names a module rather than the mistake. Say the real thing.
    raise SystemExit(
        f"this is python {sys.version.split()[0]} at {sys.executable}.\n"
        "the game needs 3.12 or newer -- /usr/bin/python3 is Apple's and is "
        "too old.\nuse the project's own interpreter:  ./run.sh")

import affordances
import registry
from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from session import load_session, new_seed, save as save_session
from ai import (commitments, composer as ai_composer, counsel as ai_counsel,
                help_agent, librarian, parser as ai_parser,
                voicer as ai_voicer)
from tui import advice, collection, palace
from tui import object as object_page
from tui import ledgers as ledger_page
from tui import inbox as inbox_page
from tui import plague as plague_page
from tui import trade as trade_page
from tui import orders as orders_page
from tui import works as works_page
from tui import (altar, archive, atlas, alu, command as command_page,
                 composer, counsel, desktop, document, hall,
                 help as help_page, render, style, switcher, worldmap)
import manual
import palette as command_palette
from tui.grid import InteractiveScreen, Screen

# Costs are the registry's, never this file's. These two names survive only
# because both screens must quote the price *before* building the action --
# the Desk warns that answering needs two hours while the draft is still
# empty, and the Altar deducts for a consultation it performs itself rather
# than through `do`. Everything else lets `do` ask the registry (spec 19).
REPLY_COST = registry.BY_ID["dictate_reply"].cost
OMEN_COST = registry.BY_ID["consult_diviner"].cost

# Where `STK_DUMP=1` writes what the windows are showing, for `tools/screens.py
# live`. A running game is otherwise unreadable from outside without a camera.
DUMP = Path(__file__).parent / "saves" / "screens.txt"

# key -> (window key, title, how to compose it from Belief). Sizes are not
# here: they belong to `tui.desktop`, which states one default and one minimum
# per window and is the only place either number appears (UI/UX spec 6).
TABLETS: dict[str, tuple[str, str, object]] = {
    "s": ("stack", "The Scribes' Room", inbox_page.compose),
}

# The workbenches. They were tablets -- read and closed, with every order they
# described given through Counsel -- and are now workbenches with their own key
# handler, like the Alu (UI/UX spec 15, phase 4).
LEDGERS: dict[str, tuple[str, str, str]] = {
    "t": ("stores", "The Storehouse", "on_storehouse_key"),
    "m": ("muster", "The Muster — Levy and Spear", "on_muster_key"),
}

# The windows that hold a conversation: they own their own keys, because most
# of them take typing and none of them can afford to fall through to the hall's
# door list. key -> (window key, title, size, which handler)
ROOMS: dict[str, tuple[str, str, str]] = {
    "w": ("world", "The Known World", "on_world_key"),
    "v": ("altar", "The Shrine", "on_altar_key"),
    "y": ("alu", "The Alu", "on_alu_key"),
    "j": ("palace", "The Court", "on_palace_key"),
    "x": ("trade", "Trade", "on_trade_key"),
}

# The hall advertises every door and marks the ones that are not built (D33:
# never strand the player). The two lists must not drift, so the controller
# reads the hall's rather than keeping a second one. Writing and archive search
# are stations inside the Scribes' Room; labour and land are stations inside
# the Storehouse; Orders is a station inside the Alu, Counsel inside the
# Court, Oaths inside the Shrine, and Sickness inside the World, so none of
# those are top-level windows.
assert {target for _k, _l, target in hall.DOORS if target in hall.BUILT} == (
    {window_key for window_key, _t, _how in TABLETS.values()}
    | {window_key for window_key, _t, _h in LEDGERS.values()}
    | {window_key for window_key, _t, _h in ROOMS.values()})


# Windows that manage the game rather than the kingdom. An order given while
# one of these has focus belongs to the window underneath it, so they are never
# the target of an outcome (UI/UX spec 5, "utilities").
UTILITIES = frozenset({"help", "switcher", "palette"})


def _key(action_id: str) -> str:
    """The key that gives this order, from the registry and nowhere else.

    The handlers used to spell their letters out, which meant a mnemonic could
    be changed in the registry and documented in the manual while the window
    went on listening for the old one.
    """
    return ledger_page.key_for(action_id)


def _window_notice(window_key: str) -> property:
    """A `*_notice` attribute backed by the one outcome table.

    The controller grew a separate notice string per screen, each rendered by
    exactly one composer and cleared by hand in several places. They are one
    thing -- what came of the last order in that window -- so they are stored
    once and these properties keep the readable old names at the call sites.
    """

    def get(self) -> style.Notice:
        return self.notices.get(window_key, style.Notice(""))

    def set(self, message) -> None:
        if message:
            self.notices[window_key] = style.Notice(
                message, getattr(message, "kind", "info"))
        else:
            self.notices.pop(window_key, None)

    return property(get, set)


class Game:
    """World, Belief, the fortnight's hours, and the windows open on them."""

    inbox_notice = _window_notice("stack")
    plague_notice = _window_notice("plague")
    alu_notice = _window_notice("alu")
    altar_notice = _window_notice("altar")
    switcher_notice = _window_notice("switcher")

    def __init__(self, chosen_alu: str = "seat", seed: int | None = None) -> None:
        from tui.backend_tk import App

        self.seed = new_seed() if seed is None else seed
        seed = self.seed
        self.chosen_alu = chosen_alu
        self.save_path = Path(__file__).parent / "saves" / chosen_alu / "autosave.json"
        self.session_notice = ""
        self.load_armed = False
        self.world = load_campaign(chosen_alu, seed)
        self.world, _ = advance(self.world)
        self.hours = project(self.world)["attention"]
        self.log: list[dict] = []
        # Presentation is remembered between runs; the world is not. A broken
        # settings file yields defaults rather than refusing to start.
        self.settings_path = Path(__file__).parent / "saves" / "settings.json"
        self.prefs = desktop.Preferences.load(self.settings_path)
        self.app = App(self.prefs)
        # Language is part of the shipped court, not an optional embellishment.
        # `main()` verifies the small local model before constructing the game;
        # constructing Game directly remains useful to the Tk probe and
        # headless controller tests, and still creates the same shared client.
        from ai.client import OllamaClient
        self.client = OllamaClient(None, f"saves/{chosen_alu}/ai_cache")
        self.voicer = ai_voicer.Voicer(self.client, seed)
        self._model_results: queue.SimpleQueue = queue.SimpleQueue()
        self._model_jobs = 0
        self.open_letters: dict[str, dict] = {}
        self.focused_objects: dict[str, dict] = {}
        self.focus_scroll: dict[str, int] = {}
        self.events: list[str] = []
        # The windows that hold a conversation rather than a record. All of it
        # is session state: none of it is a fact about the kingdom, so none of
        # it is logged and a replay is unaffected.
        self.desk: dict | None = None
        self.desk_drafts: dict[str, dict] = {}
        self.works_pick = ""          # a work in hand, awaiting [x]
        self.works_plan_pick = ""     # a plan read before [Enter] commissions it
        self.inbox_pick = ""
        self.inbox_filter = "all"
        self.inbox_scroll = 0
        self.inbox_body_scroll = 0
        self.inbox_pane = "rack"
        self.inbox_notice = ""
        delegate_people = [
            person for person in project(self.world).get(
                "house", {}).get("members", [])
            if person["alive"] and person["id"] != self.world.court.ruler
            and person["location"] == self.world.court.seat
        ]
        self.inbox_delegate_pick = (
            delegate_people[0]["id"] if delegate_people else "")
        relations = project(self.world).get("relations", [])
        plague_places = sorted({
            relation["place"] for relation in relations
            if relation.get("place") and relation["place"] != self.world.court.seat
        })
        self.plague_pick = plague_places[0] if plague_places else ""
        self.plague_scroll = 0
        self.plague_notice = ""
        self.alu_notice = ""
        self.world_place_pick = self.world.court.seat
        self.world_route_scroll = 0
        self.world_all_routes = False
        # How much ground one character stands for. One setting for the whole
        # window rather than one per place, so walking the shore at a given
        # magnification keeps it.
        self.world_wide = 3
        # Where the window is looking, in cells of the authored map. None means
        # "wherever the selected place is", which is what it goes back to the
        # moment another place is chosen: panning is for looking around, and
        # choosing a place is for going somewhere.
        self.world_focus: tuple[int, int] | None = None
        # Which of the map's layers is on top. The shape of the world first:
        # it is the one that answers "where am I looking".
        self.world_layer = worldmap.LAYERS[0]
        self.counsel_said: list[tuple[str, str]] = []
        self.counsel_typed = ""
        self.counsel_typing = False
        self.counsel_pending: dict | None = None
        # Help is a book, not a conversation: a search line, a chosen topic,
        # and the screen it was opened from (UI/UX spec 11).
        self.help_query = ""
        self.help_pick = ""
        self.help_screen = "hall"
        self.altar_readings: list[str] = []
        self.altar_question = "harvest"
        self.altar_offering: tuple[str, int] | None = None
        altar_people = [
            person for person in project(self.world).get(
                "house", {}).get("members", [])
            if person["alive"]
        ]
        self.altar_subject = altar_people[0]["id"] if altar_people else ""
        self.altar_notice = ""
        self.archive_query = ""
        self.archive_hits: list[dict] = []
        self.archive_summary = ""
        self.archive_summary_source = ""
        self.archive_generation = 0
        self.archive_typing = False
        self.archive_open_ref = ""
        self.archive_pick = ""
        self.archive_documents: dict[str, dict] = {}
        self.archive_document_scroll: dict[str, int] = {}
        # The pile's display order, held steady across the fortnight so the
        # numbers do not move under the player's finger (see document.order_of).
        self.stack_order: list[str] = document.order_of(project(self.world))
        self.voicer.schedule(project(self.world)["stack"],
                             self.world.date.absolute)

        self.switcher_pick = ""
        self.switcher_notice = ""
        # The command palette. Session state: a line, and what has been typed
        # before it. Neither is a fact about the kingdom, so neither is saved.
        self.command_line = ""
        self.command_history: list[str] = []
        self.command_recall = 0
        self.pending_action: tuple[object, int, str] | None = None
        self.app.desktop_bindings = self._desktop_bindings()

        hall_width, hall_height = desktop.default_size("hall")
        self.hall_window = self.app.window(
            "hall", f"Say to the King, my lord — seed {seed}",
            hall_width, hall_height,
            on_key=self.on_key, on_close=self.quit,
            on_resize=self.on_resize)
        self.repaint()
        # A Tk program launched from a terminal opens *behind* the terminal on
        # macOS, which is indistinguishable from nothing having happened.
        self.hall_window.present()

    # --- state ---------------------------------------------------------------

    def _run_model(self, work, done) -> None:
        """Run the court's language work away from Tk and return on its loop."""
        self._model_jobs += 1
        if self._model_jobs == 1:
            self.app.root().after(20, self._poll_model_results)

        def worker() -> None:
            try:
                result = work()
                error = None
            except Exception as caught:  # model failure is a UI result, not a crash
                result, error = None, caught
            self._model_results.put((done, result, error))

        threading.Thread(
            target=worker, name="stk-model", daemon=True).start()

    def _poll_model_results(self) -> None:
        while True:
            try:
                done, result, error = self._model_results.get_nowait()
            except queue.Empty:
                break
            self._model_jobs = max(0, self._model_jobs - 1)
            done(result, error)
        if self._model_jobs:
            self.app.root().after(20, self._poll_model_results)

    @property
    def belief(self) -> dict:
        return project(self.world)

    def _language_belief(self, belief: dict) -> dict:
        """Attach cached model voices without changing projected facts."""
        voicer = self.__dict__.get("voicer")
        if voicer is None:
            return belief
        stack = []
        for item in belief.get("stack", []):
            body, source = voicer.body(item)
            # A foreign court's answer is kept the first time it is read out.
            # Everything else the scribes voice can be voiced again; an answer
            # cannot, because replay may not ask a model for it (spec 2.6, 5.3),
            # and the words are recorded through the log like any other change.
            if source == "model" and str(item.get("topic", "")).startswith(
                    "reply_"):
                self._record_reply_text(item["id"], body)
            voiced = dict(item)
            voiced["body"] = body
            voiced["body_source"] = source
            stack.append(voiced)
        enriched = dict(belief)
        enriched["stack"] = stack
        return enriched

    def _record_reply_text(self, letter_id: str, text: str) -> None:
        """Keep an accepted reading of an answer, through the action log.

        Costs no attention and raises nothing: it is a record of what was read,
        not an order, and a projection pass is the wrong place to refuse the
        player anything. A second reading of the same tablet is discarded by the
        reducer, so this is safe to call on every redraw.
        """
        action = A.RecordReplyText(letter_id, text)
        try:
            world, _ = apply(self.world, action)
        except (ValueError, TypeError, KeyError):
            return
        if world is self.world:
            return
        self.world = world
        self.log.append({"turn": self.world.date.absolute,
                         "action": A.to_dict(action)})

    @staticmethod
    def _outbox_belief(belief: dict) -> dict:
        """Put physical dispatch marks into the Outbox's compact glance lines."""
        outbox = []
        for item in belief.get("outbox", []):
            shown = dict(item)
            facts = dict(item.get("facts") or {})
            terms = list(item.get("terms") or ())
            path = list(item.get("path") or ())
            if terms:
                facts["terms"] = composer.terms_summary(terms)
            if path:
                facts["route"] = " > ".join(
                    str(place).replace("_", " ") for place in path)
            handling = " · ".join(
                str(item.get(field) or "").replace("_", " ")
                for field in ("scribe_id", "seal", "courier_id")
                if item.get(field))
            if handling:
                facts["scribe seal courier"] = handling
            shown["facts"] = facts
            outbox.append(shown)
        if not outbox:
            return belief
        enriched = dict(belief)
        enriched["outbox"] = outbox
        return enriched

    # --- outcomes -------------------------------------------------------------

    @property
    def notices(self) -> dict:
        """Window key -> the outcome of the last order given in that window.

        Created on first use rather than in `__init__`, because the headless
        tests drive the controller through `Game.__new__` and set only the few
        attributes the path under test reads. Feedback is exactly the thing
        those tests assert on, so it must not depend on a constructor they
        deliberately skip.
        """
        table = self.__dict__.get("_notices")
        if table is None:
            table = self.__dict__["_notices"] = {}
        return table

    # How far each paged list has been scrolled. Presentation only: no scroll
    # position is a fact about the kingdom, so none of it is saved or logged.
    SCROLLS = ("archive_scroll", "works_scroll", "works_plan_scroll",
               "alu_scroll")

    def scroll_of(self, name: str) -> int:
        return int(getattr(self, name, 0) or 0)

    def scrolled(self, name: str, total: int, room: int, by: int) -> bool:
        """Move a list by `by` rows, clamped. True when anything moved.

        Clamped against the collection rather than allowed to run off it: a
        list scrolled past its end shows an empty rectangle, which reads as a
        list that has lost its contents.
        """
        was = self.scroll_of(name)
        now = max(0, min(was + by, max(0, total - room)))
        setattr(self, name, now)
        return now != was

    STEPS = {"Up": -1, "Down": 1, "Prior": -8, "Next": 8,
             "Home": -1_000_000, "End": 1_000_000}

    def active_window(self) -> str:
        """The window the order was given in, which is where it must answer.

        Utilities are skipped: pressing a key in Help or the palette is still
        an order given *from* the screen underneath, and reporting the result
        into a window that is about to close would lose it.
        """
        app = getattr(self, "app", None)
        if app is None:                 # headless: the Hall is the only record
            return "hall"
        for key in app.live():
            if key not in UTILITIES:
                return key
        return "hall"

    def notify(self, message: str, kind: str = registry.SUCCESS,
               window: str | None = None) -> None:
        """Post one outcome to the window that caused it, and to the Hall.

        Both, deliberately. The initiating window is where the player is
        looking and is the specification's requirement (spec 21, "show
        success/refusal in the initiating window"); the Hall is the session's
        record, and a player who has since moved on can still find out what
        happened to the last thing they ordered.
        """
        line = style.Notice(message, kind)
        target = self.active_window() if window is None else window
        self.notices[target] = line
        self.notices["hall"] = line

    def notice_for(self, key: str) -> style.Notice:
        return self.notices.get(key, style.Notice(""))

    def clear_notice(self, key: str) -> None:
        self.notices.pop(key, None)

    @property
    def session_notice(self) -> str:
        """The Hall's line. A property so the whole controller keeps one path.

        Every `self.session_notice = ...` in this file used to be a private
        string that only the Hall rendered. They now all route through
        `notify`, which means an assignment made anywhere lands in the window
        the player is actually in as well.
        """
        return self.notices.get("hall", style.Notice(""))

    @session_notice.setter
    def session_notice(self, message: str) -> None:
        if message:
            self.notify(message, getattr(message, "kind", "info"))
        else:
            self.notices.pop("hall", None)

    def do(self, action, cost: int | None = None,
           window: str | None = None, confirmed: bool = False
           ) -> registry.ActionResult:
        """Apply an action if the hours are there. Logged the same way the
        headless driver logs it, so a session here saves and replays.

        `cost` defaults to the registry's, which is the product contract and
        the same number the typed path charges. Passing one explicitly is for
        the rare case where a screen genuinely charges something else; it is
        not a place to restate a constant that already exists (UI/UX spec 19).

        Returns an `ActionResult` rather than a bare bool, so that a refusal
        carries *why* -- the missing hours, the engine's own complaint -- to
        whichever surface asked. It is still truthy on success, so the existing
        `if self.do(...)` callers read the same.
        """
        descriptor = registry.describe(action)
        action_id = descriptor.id if descriptor else ""
        if cost is None:
            cost = registry.cost_of(action)
        target = self.active_window() if window is None else window
        if descriptor and descriptor.confirm and not confirmed:
            self.pending_action = (action, cost, target)
            unit = "hour" if cost == 1 else "hours"
            result = registry.ActionResult(
                registry.PREVIEW, action_id,
                f"{self._describe_order(action)} — {cost} {unit}. "
                "Enter confirms; Escape cancels.", cost, self.hours)
            self.notify(result.message, result.status, window=target)
            self.repaint()
            return result
        if cost > self.hours:
            unit = "hour" if cost == 1 else "hours"
            result = registry.ActionResult(
                registry.REFUSAL, action_id,
                f"That requires {cost} {unit}; {self.hours} remain.",
                cost, self.hours, missing="attention")
        else:
            try:
                self.world, _ = apply(self.world, action)
            except (ValueError, TypeError, KeyError) as error:
                result = registry.ActionResult(
                    registry.REFUSAL, action_id,
                    f"That order was refused: {error}.",
                    cost, self.hours, missing=str(error))
            else:
                self.hours -= cost
                self.log.append({"turn": self.world.date.absolute,
                                 "action": A.to_dict(action)})
                self.load_armed = False
                result = registry.ActionResult(
                    registry.SUCCESS, action_id,
                    "Entered: " + self._describe_order(action) + ".",
                    cost, self.hours)
        self.notify(result.message, result.status, window=target)
        self.repaint()
        return result

    def confirm_pending(self) -> bool:
        pending = getattr(self, "pending_action", None)
        if pending is None:
            return False
        self.pending_action = None
        action, cost, window = pending
        result = self.do(action, cost, window, confirmed=True)
        if result and isinstance(action, A.DispatchLetter):
            desk = self.desk or {}
            draft_key = str(desk.get("draft_key") or desk.get("letter_id")
                            or f"new:{desk.get('recipient', '')}")
            self.__dict__.setdefault("desk_drafts", {}).pop(draft_key, None)
            self.desk = None
            self.repaint()
        return True

    def cancel_pending(self) -> bool:
        pending = getattr(self, "pending_action", None)
        if pending is None:
            return False
        self.pending_action = None
        self.notify("Order cancelled.", registry.PREVIEW, window=pending[2])
        self.repaint()
        return True

    def save_current(self, automatic: bool = False) -> bool:
        """Atomically save the replayable campaign at its current turn."""
        try:
            save_session(
                self.save_path, self.seed, self.chosen_alu,
                self.world.date.absolute, self.log, self.world,
                hours_left=self.hours)
        except (OSError, ValueError, TypeError) as error:
            self.session_notice = f"The campaign could not be saved: {error}."
            self.repaint()
            return False
        self.load_armed = False
        try:
            shown_path = self.save_path.relative_to(Path(__file__).parent)
        except ValueError:
            shown_path = self.save_path
        self.session_notice = (
            "Autosaved." if automatic else
            f"Saved to {shown_path}.")
        self.repaint()
        return True

    def load_current(self) -> bool:
        """Reload the autosave only after the caller has confirmed the choice."""
        try:
            world, data = load_session(self.save_path)
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.load_armed = False
            self.session_notice = f"The campaign could not be loaded: {error}."
            self.repaint()
            return False
        self.world = world
        self.seed = int(data["seed"])
        self.chosen_alu = str(data["chosen_alu"])
        self.log = list(data["log"])
        saved_hours = data.get("hours_left")
        attention = self.belief["attention"]
        if saved_hours is None:
            self.hours = attention
        elif not isinstance(saved_hours, int) or not 0 <= saved_hours <= attention:
            self.load_armed = False
            self.session_notice = (
                "The campaign could not be loaded: invalid saved attention.")
            self.repaint()
            return False
        else:
            self.hours = saved_hours
        # Drafts and confirmations describe the world that was on screen, not
        # the one just loaded. None may leak forward from the abandoned state.
        self.__dict__.pop("_ledger_state", None)
        self.pending_action = None
        self.command_line = ""
        self.events = []
        self.desk = None
        self.desk_drafts.clear()
        self.counsel_pending = None
        self.open_letters.clear()
        self.archive_documents.clear()
        self.archive_document_scroll.clear()
        self.stack_order = document.order_of(self.belief)
        if "voicer" in self.__dict__:
            self.voicer = ai_voicer.Voicer(self.client, self.seed)
            self.voicer.schedule(self.belief["stack"],
                                 self.world.date.absolute)
        self.inbox_pick = ""
        self.inbox_scroll = 0
        self.inbox_body_scroll = 0
        self.inbox_pane = "rack"
        self.inbox_filter = "all"
        self.archive_open_ref = ""
        self.inbox_notice = ""
        self.alu_notice = ""
        self.plague_notice = ""
        self.plague_scroll = 0
        delegate_people = [
            person for person in self.belief.get("house", {}).get(
                "members", [])
            if person["alive"] and person["id"] != self.world.court.ruler
            and person["location"] == self.world.court.seat
        ]
        self.inbox_delegate_pick = (
            delegate_people[0]["id"] if delegate_people else "")
        self.load_armed = False
        for key in [
                key for key in self.app.windows
                if key.startswith(("letter:", "archive:")) or key == "desk"]:
            self.app.close(key)
        self.session_notice = (
            f"Loaded turn {self.world.date.absolute} from the verified autosave.")
        self.repaint()
        return True

    def end_fortnight(self) -> None:
        if self.world.ended:
            self.session_notice = self.world.end_reason
            self.repaint()
            return
        if self.counsel_pending is not None:
            self.counsel_pending = None
            self.counsel_said.append((
                "scribe",
                "The unconfirmed draft lapsed when the fortnight ended."))
        self.world, events = advance(self.world)
        self.hours = self.belief["attention"]
        self.inbox_notice = ""
        self.alu_notice = ""
        self.plague_notice = ""
        self.stack_order = document.order_of(self.belief, self.stack_order)
        if "voicer" in self.__dict__:
            self.voicer.schedule(self.belief["stack"],
                                 self.world.date.absolute)
        self.open_letters.clear()
        for key in [k for k in self.app.windows if k.startswith("letter:")]:
            self.app.close(key)
        # The fortnight gets its own window rather than a silent redraw. It is
        # the only moment in the game the player does not control, and it
        # should feel like one.
        self.events = render.events_lines(events, self.world.court)
        self.save_current(automatic=True)
        window = self.app.window(
            "fortnight", "The fortnight turns", 66, 18,
            on_key=lambda e: self.on_tablet_key(e, "fortnight"),
            on_close=lambda: self.app.close("fortnight"))
        self.repaint()
        window.focus()

    # --- windows -------------------------------------------------------------

    def _size(self, key: str) -> tuple[int, int]:
        """The cells a window actually has, or the size it would open at.

        Composers are pure functions of Belief *and size*, so recomposing at
        the live capacity is the whole of the responsive behaviour: the window
        says how much room there is, the screen is built to fit it, and nothing
        is ever scaled or clipped (UI/UX spec 6).
        """
        app = getattr(self, "app", None)
        window = None if app is None else app.windows.get(key)
        if window is not None and window.root.winfo_exists():
            return window.width, window.height
        return desktop.default_size(key)

    def compose(self, key: str) -> Screen | None:
        b = self._outbox_belief(self._language_belief(self.belief))
        width, height = self._size(key)
        # Every screen is handed the outcome of the last order given in it.
        # One lookup rather than a differently-named attribute per window.
        notice = self.notice_for(key)
        if key == "hall":
            return hall.compose(
                b, width, height, hours_left=self.hours, notice=notice)
        if key == "stack":
            if getattr(self, "desk", None) is not None:
                item = self._desk_item()
                if item is not None:
                    path = tuple(self.desk.get("path") or ())
                    return composer.compose(
                        item, self.desk["draft"], self.desk["intent"],
                        self.desk["dictating"], house=b.get("house"),
                        width=width, height=height,
                        composing=self.desk.get("composing", False),
                        notice=notice,
                        cursor_index=self.desk.get("cursor"),
                        source_scroll=self.desk.get("source_scroll", 0),
                        terms=tuple(self.desk.get("terms", ())),
                        blocks=self.desk.get("blocks"),
                        block_focus=self.desk.get("block_focus", "matter"),
                        matter=self.desk.get("matter", ""),
                        advisor_undo="advisor_origin" in self.desk,
                        term_builder=self.desk.get("term_builder"),
                        term_focus=self.desk.get("term_focus", "kind"),
                        block_order=self.desk.get("block_order"),
                        block_edits=self.desk.get("block_edits"),
                        bound=self._desk_bound(),
                        seal_data={
                            "scribe": self.desk.get("scribe_id", "yabninu"),
                            "courier": self.desk.get("courier_id", "iliya"),
                            "route": " > ".join(path),
                            "travel_time": worldmap.path_legs(b, path),
                        })
            if getattr(self, "inbox_filter", "all") == "records":
                opened = next(
                    (hit for hit in self.archive_hits
                     if str(hit.get("ref", "")) == getattr(
                         self, "archive_open_ref", "")),
                    None)
                if opened is not None:
                    return archive.tablet(
                        opened, b, width, height,
                        scroll=self.archive_document_scroll.get(
                            "embedded", 0),
                        embedded=True)
                return archive.compose(
                    b, self.archive_query, self.archive_hits,
                    self.archive_summary, self.archive_typing,
                    width, height, notice=notice,
                    scroll=self.scroll_of("archive_scroll"),
                    embedded=True, selected=getattr(self, "archive_pick", ""))
            return inbox_page.compose(
                b, width, height, self.stack_order, self.inbox_pick,
                self.inbox_filter, self.inbox_scroll, self.hours,
                self.inbox_delegate_pick, notice=notice,
                body_scroll=getattr(self, "inbox_body_scroll", 0),
                focus=getattr(self, "inbox_pane", "rack"))
        if key == "switcher":
            return switcher.compose(
                self.switcher_entries(), self.switcher_pick, width, height,
                notice=notice)
        if key == "fortnight":
            return document.fortnight(b, self.events, width, height)
        if key == "world":
            return worldmap.compose(
                b, width, height, self.world_route_scroll,
                self.world_place_pick, notice=notice, wide=self.world_wide,
                layer=self.world_layer, focus=self.world_focus,
                all_routes=getattr(self, "world_all_routes", False))
        if key == "trade":
            return trade_page.compose(b, width, height, notice=notice,
                                      view=getattr(self, "trade_view", trade_page.VIEWS[0]),
                                      selected=getattr(self, "trade_pick", ""),
                                      scroll=getattr(self, "trade_scroll", 0),
                                      due_draft=self.ledger_state["dues"]
                                      .setdefault("rates", {}).get("harbour"))
        if key == "alu":
            return alu.compose(b, None, width, height, notice=notice,
                                scroll=self.scroll_of("alu_scroll"),
                                view=getattr(self, "alu_view", alu.VIEWS[0]),
                                selected=getattr(self, "alu_pick", ""))
        if key == "works":
            return works_page.compose(
                b, self.works_pick, width, height, notice=notice,
                scroll=self.scroll_of("works_scroll"),
                plan_scroll=self.scroll_of("works_plan_scroll"),
                selected_plan=getattr(self, "works_plan_pick", ""))
        if key == "palace":
            state = self.palace_state
            return palace.compose(
                b, view=state["view"], selected=self.palace_pick(),
                scroll=state["scroll"], hours=self.hours,
                choosing=state["choosing"], person=state["person"],
                amount=state["amount"], good=state["good"],
                notice=notice, width=width, height=height)
        if key == "plague":
            return plague_page.compose(
                b, self.plague_pick, width, height,
                scroll=getattr(self, "plague_scroll", 0), notice=notice)
        if key.startswith("institution:"):
            inst = next((i for i in b.get("institutions", [])
                         if i["id"] == key.split(":", 1)[1]), None)
            if inst is not None:
                return alu.detail(b, inst, inst.get("history"), width, height)
        if key.startswith("focus:"):
            item = self.focused_objects.get(key)
            kind = key.split(":", 2)[1]
            return object_page.compose(
                item, width, height, kind, self.focus_scroll.get(key, 0)) if item else None
        if key == "counsel":
            suggestions = [
                concern.order_prompt or concern.suggestion
                for concern in advice.concerns(b, 3)
                if concern.destination == "counsel"
            ]
            return counsel.compose(b, self.counsel_said, self.hours,
                                   self.counsel_typed, self.counsel_typing,
                                   width, height, suggestions,
                                   (self.counsel_pending["descriptions"]
                                    if self.counsel_pending else None))
        if key == "palette":
            return command_page.compose(
                self.command_line,
                command_palette.parse(self.command_line, b),
                self.hours, width, height,
                tuple(self.command_history), notice=notice)
        if key == "help":
            return help_page.compose(
                width, height, self.help_query, self.help_pick,
                self.help_screen)
        if key == "altar":
            shrine_view = getattr(self, "shrine_view", "rites")
            if shrine_view == "oaths":
                state = self.ledger_state["oaths"]
                return ledger_page.oaths(
                    b, selected=state["pick"], scroll=state["scroll"],
                    amount=state["amount"], notice=notice, hours=self.hours,
                    width=width, height=height,
                    views=tuple((name, name.title()) for name in altar.VIEWS),
                    view="oaths")
            if shrine_view == "obligations":
                state = self.ledger_state["oaths"]
                return ledger_page.obligations(
                    b, selected=state["pick"], scroll=state["scroll"],
                    notice=notice, hours=self.hours, width=width, height=height)
            return altar.compose(b, self.altar_readings, self.altar_question,
                                 self.altar_offering, width, height,
                                 subject=self.altar_subject,
                                 notice=self.altar_notice,
                                 view=shrine_view)
        if key == "archive":
            return archive.compose(b, self.archive_query, self.archive_hits,
                                   self.archive_summary, self.archive_typing,
                                   width, height, notice=notice,
                                   scroll=self.scroll_of("archive_scroll"),
                                   selected=getattr(self, "archive_pick", ""))
        if key.startswith("archive:"):
            item = self.archive_documents.get(key)
            return None if item is None else archive.tablet(
                item, b, scroll=self.archive_document_scroll.get(key, 0))
        if key == "orders":
            state = self.orders_state
            return orders_page.compose(
                b, self.log, self.world.date.absolute, self.hours,
                view=state["view"], selected=state["pick"],
                scroll=state["scroll"], notice=notice,
                width=width, height=height)
        if key in ({w for w, _t, _h in LEDGERS.values()}
                   | {"roll", "land", "oaths"}):
            return self.compose_ledger(key, b, width, height, notice)
        for _, (window_key, _title, how) in TABLETS.items():
            if key == window_key:
                return how(b, width, height)
        if key.startswith("letter:"):
            item = self.open_letters.get(key)
            return None if item is None else document.tablet(
                item, body=item.get("body"), house=b.get("house"))
        return None

    # --- the desktop ---------------------------------------------------------

    def _desktop_bindings(self) -> dict:
        """Keys that manage windows rather than the kingdom (UI/UX spec 6).

        Bound on every window. `Command` is listed beside `Control` because a
        Mac player will reach for it first and Tk does not treat them as the
        same modifier.
        """
        def bind(handler):
            def wrapped(_event=None):
                handler()
                return "break"
            return wrapped

        def pending(handler):
            def wrapped(_event=None):
                return "break" if handler() else None
            return wrapped

        def guarded(handler):
            def wrapped(_event=None):
                active = self.active_window()
                typing = ((active == "stack" and self.desk and self.desk.get("dictating"))
                          or (active == "counsel" and self.counsel_typing)
                          or (active in {"stack", "archive"} and self.archive_typing)
                          or active == "palette")
                if typing:
                    return None
                handler()
                return "break"
            return wrapped

        bindings = {
            "<colon>": guarded(self.open_palette),
            "<grave>": guarded(self.open_palette),
            "<question>": guarded(self.open_help),
            "<Return>": pending(self.confirm_pending),
            "<Escape>": pending(self.cancel_pending),
            "<Control-Tab>": bind(self.cycle_windows),
            "<Control-Shift-Tab>": bind(lambda: self.cycle_windows(True)),
        }
        for modifier in ("Control", "Command"):
            bindings[f"<{modifier}-h>"] = bind(self.raise_hall)
            bindings[f"<{modifier}-g>"] = bind(self.open_switcher)
            bindings[f"<{modifier}-s>"] = bind(self.save_current)
            bindings[f"<{modifier}-o>"] = bind(self.request_load)
            bindings[f"<{modifier}-Shift-t>"] = bind(self.tile_windows)
            bindings[f"<{modifier}-Shift-c>"] = bind(self.cascade_windows)
            # Shift makes the keysym uppercase, so the lowercase spelling of a
            # shifted letter never matches on some Tk builds. Bind both, plus
            # the plain Control-R that most players will try first.
            for sequence in (f"<{modifier}-Shift-R>", f"<{modifier}-Shift-r>",
                             f"<{modifier}-R>", f"<{modifier}-r>"):
                bindings[sequence] = bind(self.reset_window_sizes)
            bindings[f"<{modifier}-plus>"] = bind(lambda: self.zoom(1))
            # The unshifted key on most layouts is `=`, and a player pressing
            # it means "bigger" whatever the keycap says.
            bindings[f"<{modifier}-equal>"] = bind(lambda: self.zoom(1))
            bindings[f"<{modifier}-minus>"] = bind(lambda: self.zoom(-1))
            bindings[f"<{modifier}-Key-0>"] = bind(self.reset_zoom)
            bindings[f"<{modifier}-Tab>"] = bind(self.cycle_windows)
            bindings[f"<{modifier}-Shift-Tab>"] = bind(lambda: self.cycle_windows(True))
        return bindings

    def request_load(self) -> None:
        if self.load_armed:
            self.load_current()
            return
        self.load_armed = True
        self.notify("Reload discards unsaved orders. Press Ctrl-O again to confirm.",
                    registry.PREVIEW)
        self.repaint()

    def zoom(self, step: int) -> None:
        size = self.app.set_font_size(self.prefs.font_size + step)
        self.session_notice = f"Type is now {size} point."
        self.save_settings()
        self.repaint()

    def reset_zoom(self) -> None:
        size = self.app.set_font_size(desktop.FONT_DEFAULT)
        self.session_notice = f"Type is back to {size} point."
        self.save_settings()
        self.repaint()

    def on_resize(self, key: str) -> None:
        """A window changed how many cells it holds, so compose it again."""
        window = self.app.windows.get(key)
        if window is None or not window.root.winfo_exists():
            return
        screen = self.compose(key)
        if screen is not None:
            window.paint(screen)

    def raise_hall(self) -> None:
        self.hall_window.focus()
        self.app.note_focus("hall")

    def tile_windows(self) -> None:
        self.app.tile()
        self.session_notice = "Windows tiled."
        self.repaint()

    def cascade_windows(self) -> None:
        self.app.cascade()
        self.session_notice = "Windows cascaded."
        self.repaint()

    def reset_window_sizes(self) -> None:
        """Every open window back to the size its screen was designed for.

        It forgets the remembered size as well as undoing it, so a window the
        player once dragged small does not come back small on the next run.
        """
        moved = self.app.reset_sizes()
        self.session_notice = (
            f"{moved} window{'s' if moved != 1 else ''} back to default size."
            if moved else "Nothing open to resize.")
        self.save_settings()
        self.repaint()

    def cycle_windows(self, backwards: bool = False) -> None:
        self.app.cycle(backwards)

    def switcher_entries(self) -> list:
        """What the switcher lists: every open window and what it is holding."""
        entries = []
        for key in self.app.live():
            if key == "switcher":
                continue
            window = self.app.windows[key]
            entries.append(switcher.Entry(
                key=key,
                title=window.title.split(" — ")[0],
                note=self._window_note(key),
                closable=key != "hall",
                dirty=(key == "stack" and self.desk is not None
                       and bool(self.desk.get("draft"))),
            ))
        return entries

    def _window_note(self, key: str) -> str:
        """One line saying what state a window is carrying."""
        b = self._language_belief(self.belief)
        if key == "hall":
            return f"{self.hours}h left"
        if key == "stack":
            if self.desk is not None:
                return "wet reply"
            if self.inbox_filter == "records":
                return "archive search"
            unread = sum(1 for item in b["stack"] if not item["read"])
            return f"{unread} unread" if unread else self.inbox_filter
        if key.startswith("letter:") or key.startswith("archive:"):
            return "tablet"
        if key == "alu":
            return "the seat"
        if key == "counsel":
            return "order pending" if self.counsel_pending else "advice"
        return ""

    def open_switcher(self) -> None:
        entries = self.switcher_entries()
        if entries and self.switcher_pick not in {e.key for e in entries}:
            self.switcher_pick = entries[0].key
        width, height = desktop.default_size("switcher")
        window = self.app.window(
            "switcher", "Windows", width, height,
            on_key=self.on_switcher_key,
            on_close=lambda: self.app.close("switcher"),
            on_resize=self.on_resize)
        self.repaint()
        window.focus()

    def on_switcher_key(self, event) -> None:
        entries = self.switcher_entries()
        keys = [entry.key for entry in entries]
        char = (event.char or "").lower()
        keysym = event.keysym

        if keysym == "Escape":
            self.app.close("switcher")
            return
        if getattr(event, "command", "").startswith("switch:"):
            self.switcher_pick = event.command.split(":", 1)[1]
            keysym = "Return"
        if keysym in ("Down", "Up") and keys:
            index = keys.index(self.switcher_pick) if self.switcher_pick in keys else 0
            index = (index + (1 if keysym == "Down" else -1)) % len(keys)
            self.switcher_pick = keys[index]
        elif char.isdigit() and char != "0":
            index = int(char) - 1
            if index < len(keys):
                self.switcher_pick = keys[index]
        elif keysym == "Return" and self.switcher_pick in keys:
            self.app.windows[self.switcher_pick].focus()
            self.app.note_focus(self.switcher_pick)
            self.switcher_notice = ""
        elif char == "x" and self.switcher_pick in keys:
            if self.switcher_pick == "hall":
                self.switcher_notice = (
                    "The hall holds the session; leave by its own door.")
            else:
                self.app.close(self.switcher_pick)
                self.switcher_pick = ""
                self.switcher_notice = ""
        elif char == "t":
            self.tile_windows()
        elif char == "c":
            self.cascade_windows()
        self.repaint()

    def save_settings(self) -> None:
        self.app.remember_geometry()
        self.prefs.save(self.settings_path)

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
        window_key, title, _how = TABLETS[char]
        width, height = desktop.default_size(window_key)
        handler = (self.on_inbox_key if window_key == "stack"
                   else lambda e, k=window_key: self.on_tablet_key(e, k))
        window = self.app.window(
            window_key, title, width, height,
            on_key=handler, on_resize=self.on_resize,
            on_close=lambda k=window_key: self.app.close(k))
        self.repaint()
        window.focus()

    def open_door(self, char: str) -> None:
        """Open whatever kind of window this key opens.

        The hall knows the three kinds apart because it has to draw them in
        groups; nothing else should have to. Anywhere that wants to send the
        player to a screen -- Orders, the adviser, Help -- names the key.
        """
        if char in TABLETS:
            self.open_tablet(char)
        elif char in LEDGERS:
            self.open_ledger(char)
        elif char in ROOMS:
            self.open_room(char)

    def open_room(self, char: str) -> None:
        """A conversation window. It binds its own handler and never shares."""
        window_key, title, handler = ROOMS[char]
        width, height = desktop.default_size(window_key)
        window = self.app.window(
            window_key, title, width, height,
            on_key=getattr(self, handler)
            if handler != "on_tablet_key"
            else (lambda e, k=window_key: self.on_tablet_key(e, k)),
            on_resize=self.on_resize,
            on_close=lambda k=window_key: self.app.close(k))
        self.repaint()
        window.focus()

    def open_focus(self, kind: str, item: dict) -> None:
        ref = str(item.get("id") or item.get("name") or len(self.focused_objects))
        key = f"focus:{kind}:{ref}"
        self.focused_objects[key] = dict(item)
        self.focus_scroll[key] = 0
        window = self.app.window(
            key, f"{kind.title()} — {item.get('name', ref)}", 72, 30,
            on_key=lambda e, k=key: self.on_focus_key(e, k),
            on_close=lambda k=key: self.app.close(k))
        self.repaint()
        window.focus()

    def on_focus_key(self, event, key: str) -> None:
        if event.keysym == "Escape":
            self.app.close(key)
            return
        step = {"Up": -1, "Down": 1, "Prior": -8, "Next": 8}.get(event.keysym)
        if step:
            self.focus_scroll[key] = max(0, self.focus_scroll.get(key, 0) + step)
            self.repaint()

    def open_letter(self, item: dict) -> None:
        key = f"letter:{item['id']}"
        self.open_letters[key] = item
        window = self.app.window(
            key, f"Tablet — {item['id']}", 62, 26,
            on_key=lambda e, k=key: self.on_tablet_key(e, k),
            on_close=lambda k=key: self.app.close(k))
        self.repaint()
        window.focus()

    def open_archive_document(self, item: dict) -> None:
        """Open a search result without reaching behind the Belief boundary."""
        ref = str(item.get("ref", "unmarked"))
        key = f"archive:{ref}"
        self.archive_documents[key] = item
        self.archive_document_scroll[key] = 0
        window = self.app.window(
            key, f"Tablet House — {ref}", 72, 24,
            on_key=lambda e, k=key: self.on_tablet_key(e, k),
            on_close=lambda k=key: self.app.close(k))
        self.repaint()
        window.focus()

    # --- the desk ------------------------------------------------------------

    def _desk_correspondence(self) -> list[dict]:
        b = self.belief
        return list(b["stack"]) + list(b.get("correspondence_archive", []))

    def _desk_item(self, desk: dict | None = None) -> dict:
        """The pinned reply, or a court-and-route tablet for a new letter."""
        state = self.desk if desk is None else desk
        if state is None:
            raise ValueError("there is no wet tablet on the Desk")
        reply_to = str(state.get("reply_to") or state.get("letter_id") or "")
        if reply_to and not reply_to.startswith("new:"):
            found = next(
                (item for item in self._desk_correspondence()
                 if item["id"] == reply_to),
                None)
            if found is not None:
                return found
        recipient = str(state.get("recipient") or "")
        relation = next(
            (entry for entry in self.belief.get("relations", [])
             if entry.get("other") == recipient),
            {})
        place = str(state.get("target_place") or relation.get("place") or "")
        route = " > ".join(state.get("path") or ())
        standing = str(relation.get("status_claim") or "standing unknown")
        return {
            "id": state.get("draft_key", f"new:{recipient}"),
            "sender": recipient,
            "topic": "new letter",
            "facts": {
                "standing": standing.replace("_", " "),
                "route": route or "no known route",
            },
            "body": "",
            "new_letter": True,
            "place": place,
        }

    def _recipient_place(self, recipient: str) -> str:
        relation = next(
            (entry for entry in self.belief.get("relations", [])
             if entry.get("other") == recipient),
            {})
        return str(relation.get("place") or "")

    def _new_term_builder(self, target_place: str,
                          kind: str = "gift") -> dict:
        belief = self.belief
        goods = [
            str(item.get("id"))
            for item in belief.get("gift_goods", [])
            if item.get("id")
        ]
        if not goods:
            goods = [
                str(good) for good, amount in belief.get("stores", {}).items()
                if type(amount) is int and amount > 0
            ]
        people = [
            str(person["id"])
            for person in belief.get("house", {}).get("members", [])
            if person.get("alive")
        ]
        return {
            "kind": (
                kind if kind in composer.TERM_KINDS
                else composer.TERM_KINDS[0]),
            "good": goods[0] if goods else "grain",
            "quantity": 60,
            "person_id": people[0] if people else "",
            "destination": target_place,
            "due_turn": self.world.date.absolute + 2,
        }

    def _store_active_desk(self) -> None:
        if self.desk is None:
            return
        saved = dict(self.desk)
        saved["dictating"] = False
        saved["composing"] = False
        saved["history"] = []
        saved["future"] = []
        key = str(
            saved.get("draft_key")
            or saved.get("letter_id")
            or f"new:{saved.get('recipient', '')}")
        saved["draft_key"] = key
        self.__dict__.setdefault("desk_drafts", {})[
            key] = saved

    def open_desk(self, letter_id: str) -> None:
        """Answer an incoming tablet at the same Desk used for new letters."""
        correspondence = self._desk_correspondence()
        item = next(
            (candidate for candidate in correspondence
             if candidate["id"] == letter_id),
            None)
        if item is None:
            self.notify("That tablet is no longer in correspondence.",
                        registry.REFUSAL, window="stack")
            self.repaint()
            return
        self._open_letter_desk(
            str(item["sender"]), reply_to=letter_id,
            target_place=self._recipient_place(str(item["sender"])))

    def open_new_letter(self, recipient: str, target_place: str = "",
                        preset_kind: str = "") -> None:
        """Begin or resume a wet tablet to a foreign court from World."""
        if not recipient:
            self.notify("No foreign court is known at that place.",
                        registry.REFUSAL, window="world")
            self.repaint()
            return
        self._open_letter_desk(
            recipient, target_place=(
                target_place or self._recipient_place(recipient)),
            preset_kind=preset_kind)

    def _open_letter_desk(self, recipient: str, reply_to: str = "",
                          target_place: str = "",
                          preset_kind: str = "") -> None:
        """Open one persistent wet tablet without spending dispatch time yet."""
        if self.hours < REPLY_COST:
            self.notify(
                f"Sealing a letter requires {REPLY_COST} hours; "
                f"{self.hours} remain.",
                registry.REFUSAL, window=(
                    "stack" if reply_to else "world"))
            self.repaint()
            return
        draft_key = reply_to or f"new:{recipient}"
        active_desk = getattr(self, "desk", None)
        if active_desk is not None and \
                active_desk.get("draft_key") != draft_key:
            self._store_active_desk()
        self.inbox_notice = ""
        saved = getattr(self, "desk_drafts", {}).get(draft_key)
        route = worldmap.route_path(
            self.belief, str(self.belief.get("seat", "")), target_place)
        if saved is not None:
            self.desk = dict(saved)
            self.desk["history"] = list(saved.get("history", ()))
            self.desk["future"] = list(saved.get("future", ()))
            self.desk["dictating"] = False
            self.desk["composing"] = False
            self.desk["intent"] = "reply" if reply_to else "letter"
            self.desk["draft_key"] = draft_key
            self.desk["letter_id"] = reply_to
            self.desk["reply_to"] = reply_to
            self.desk["recipient"] = recipient
            self.desk["target_place"] = target_place
            self.desk["path"] = tuple(saved.get("path") or route)
            self.desk["blocks"] = composer.normalize_blocks(
                saved.get("blocks"), recipient)
            self.desk["block_focus"] = saved.get("block_focus", "matter")
            self.desk["block_order"] = composer.normalise_order(
                saved.get("block_order") or composer.opening_order(recipient),
                recipient)
            self.desk["block_edits"] = dict(saved.get("block_edits") or {})
            self.desk["matter"] = saved.get("matter", saved.get("buffer", ""))
            self.desk["terms"] = tuple(saved.get("terms", ()))
            self.desk["term_builder"] = dict(
                saved.get("term_builder")
                or self._new_term_builder(target_place, preset_kind))
            self.desk["term_focus"] = saved.get("term_focus", "kind")
            self.desk["scribe_id"] = saved.get("scribe_id", "yabninu")
            self.desk["courier_id"] = saved.get("courier_id", "iliya")
            self.desk["buffer"] = self.desk["matter"]
            self.desk["cursor"] = min(
                int(saved.get("cursor", len(self.desk["matter"]))),
                len(self.desk["matter"]))
            self._regrade()
        else:
            builder = self._new_term_builder(target_place, preset_kind)
            self.desk = {
                "draft_key": draft_key,
                "letter_id": reply_to,
                "reply_to": reply_to,
                "recipient": recipient,
                "target_place": target_place,
                "intent": "reply" if reply_to else "letter",
                "dictating": False,
                "dictated": False,
                "buffer": "",
                "matter": "",
                "cursor": 0,
                "history": [],
                "future": [],
                "source_scroll": 0,
                "terms": (),
                "term_builder": builder,
                "term_focus": "kind",
                "blocks": composer.default_blocks(),
                "block_order": composer.opening_order(recipient),
                "block_edits": {},
                "block_focus": "matter",
                "scribe_id": "yabninu",
                "courier_id": "iliya",
                "path": route,
                "generation": 0,
                "composing": False,
                "draft": composer.assemble(
                    recipient, composer.default_blocks(), ""),
            }
        app = getattr(self, "app", None)
        if app is None:
            self.repaint()
            return
        width, height = desktop.default_size("stack")
        window = self.app.window(
            "stack", "The Scribes' Room", width, height,
            on_key=self.on_inbox_key, on_resize=self.on_resize,
            on_close=lambda: self.app.close("stack"))
        # A pre-overhaul saved geometry may still have left a Desk window
        # registered. It no longer owns state or a workflow.
        self.app.close("desk")
        self.repaint()
        window.focus()

    def _request_desk_draft(self, item: dict) -> None:
        """Ask Yabninu to correct only the king's one- or two-sentence matter."""
        desk = self.desk
        if desk is None:
            return
        matter = desk.get("matter", "").strip()
        if not matter:
            self.notify(
                "Write the matter before asking Yabninu to correct it.",
                registry.REFUSAL, window="stack")
            self.repaint()
            return
        desk["generation"] = desk.get("generation", 0) + 1
        generation = desk["generation"]
        draft_key = str(
            desk.get("draft_key") or desk.get("letter_id")
            or f"new:{desk.get('recipient', '')}")
        turn = self.world.date.absolute
        desk["composing"] = True

        def work():
            return ai_composer.correct_matter(
                item["sender"], matter, self.seed, turn, self.client)

        def done(result, error) -> None:
            current = self.desk
            if (
                current is None
                or str(
                    current.get("draft_key") or current.get("letter_id")
                    or f"new:{current.get('recipient', '')}") != draft_key
                or current.get("generation") != generation
                or current["dictating"]
            ):
                return
            current["composing"] = False
            if error is not None or result is None:
                self.notify(
                    "Yabninu could not correct the matter; your words remain.",
                    registry.REFUSAL, window="stack")
            else:
                corrected = getattr(result, "text", result)
                source = getattr(result, "source", "model")
                if corrected and source == "model":
                    current["advisor_origin"] = current["matter"]
                    current["matter"] = str(corrected).strip()
                    current["buffer"] = current["matter"]
                    current["cursor"] = len(current["matter"])
                    current["dictated"] = True
                    current["draft"] = composer.assemble(
                        item["sender"], current.get("blocks"),
                        current["matter"], source=source)
                if source != "model":
                    self.notify(
                        "Yabninu was unavailable; your words were not changed.",
                        registry.REFUSAL, window="stack")
                else:
                    self.notify(
                        "Yabninu corrected the matter; meaning and numbers kept.",
                        registry.SUCCESS, window="stack")
            self.repaint()

        self._run_model(work, done)

    def _regrade(self) -> None:
        """Press the selected blocks and exact matter into a graded tablet."""
        if self.desk is None:
            return
        item = self._desk_item()
        self.desk["generation"] = self.desk.get("generation", 0) + 1
        self.desk["composing"] = False
        if self.desk.get("dictating"):
            self.desk["matter"] = self.desk.get("buffer", "")
        self.desk["draft"] = composer.assemble(
            item["sender"], self.desk.get("blocks"),
            self.desk.get("matter", ""), source="player",
            order=self.desk.get("block_order"),
            edits=self.desk.get("block_edits"))

    def _desk_commitments(self) -> tuple:
        """What the matter as written binds the crown to (`ai/commitments.py`).

        Read fresh on every paint rather than stored: the player's words are the
        only record, so a stale list would be a promise nobody made.
        """
        if self.desk is None:
            return ()
        return commitments.read(self.desk.get("matter", ""), self.belief)

    def _desk_bound(self) -> tuple[str, ...]:
        orders = self._desk_commitments()
        matter = self.desk.get("matter", "") if self.desk else ""
        parsed = {item.sentence.strip().rstrip(".!?") for item in orders}
        prose = tuple(line.strip() for line in matter.replace("?", ".").replace("!", ".").split(".")
                      if line.strip() and line.strip() not in parsed)
        lower = matter.lower()
        tone = ("emphatic" if any(word in lower for word in ("must", "shall", "will not", "at once"))
                else "hedged" if any(word in lower for word in ("perhaps", "may", "if you can"))
                else "plain")
        return (tuple("order · " + item.describe() for item in orders)
                + ("tone · " + tone,)
                + tuple("unparsed · " + line for line in prose))

    def _desk_blocks(self) -> tuple[str, ...]:
        """The pieces on the wet tablet, in the order they lie on it."""
        if self.desk is None:
            return ()
        return composer.normalise_order(
            self.desk.get("block_order"), self._desk_item()["sender"])

    @staticmethod
    def _move_desk_cursor(text: str, cursor: int, vertical: int) -> int:
        """Move the stylus one written line while retaining its column."""
        line_start = text.rfind("\n", 0, cursor) + 1
        column = cursor - line_start
        if vertical < 0:
            if line_start == 0:
                return cursor
            previous_end = line_start - 1
            previous_start = text.rfind("\n", 0, previous_end) + 1
            return min(previous_start + column, previous_end)
        line_end = text.find("\n", cursor)
        if line_end < 0:
            return cursor
        next_start = line_end + 1
        next_end = text.find("\n", next_start)
        if next_end < 0:
            next_end = len(text)
        return min(next_start + column, next_end)

    def on_desk_key(self, event) -> None:
        """Operate the embedded clay workbench, including a real movable stylus."""
        desk = self.desk
        if desk is None:
            return
        command = getattr(event, "command", "")
        char = (event.char or "").lower()
        control = bool(getattr(event, "state", 0) & 4)

        def item_for_desk() -> dict:
            return self._desk_item(desk)

        def laid() -> list[str]:
            """The pieces actually on this tablet. Focus never leaves them."""
            return list(self._desk_blocks())

        def move_block(by: int) -> None:
            pieces = laid()
            current = desk.get("block_focus", "matter")
            if current not in pieces:
                current = "matter"
            desk["block_focus"] = pieces[
                (pieces.index(current) + by) % len(pieces)]

        def move_choice(by: int) -> None:
            block = desk.get("block_focus", "matter")
            if block == "matter":
                return
            choices = composer.block_choices(item_for_desk()["sender"]).get(block)
            if not choices:
                return
            # Cycling away from an edited piece restores the canned forms; the
            # king's own words are only lost when he asks for another form.
            desk.setdefault("block_edits", {}).pop(block, None)
            selected = desk.setdefault("blocks", composer.default_blocks())
            selected[block] = (
                int(selected.get(block, 0)) + by) % len(choices)
            self._regrade()

        def add_block() -> None:
            """Put the next piece this register allows onto the tablet."""
            recipient = item_for_desk()["sender"]
            on = laid()
            spare = [name for name in composer.permitted_blocks(recipient)
                     if name not in on]
            if not spare:
                self.notify(
                    "every piece this register allows is already on the clay.",
                    registry.REFUSAL, window="stack")
                return
            chosen = spare[0]
            desk["block_order"] = composer.normalise_order(
                on + [chosen], recipient)
            desk["block_focus"] = chosen
            self._regrade()
            self.notify(
                f"{composer.BLOCK_LABELS.get(chosen, chosen).lower()} added.",
                registry.SUCCESS, window="stack")

        def remove_block() -> None:
            block = desk.get("block_focus", "matter")
            if block in composer.REQUIRED_BLOCKS:
                self.notify(
                    "that piece is required for a sealed order.",
                    registry.REFUSAL, window="stack")
                return
            recipient = item_for_desk()["sender"]
            on = [name for name in laid() if name != block]
            desk["block_order"] = composer.normalise_order(on, recipient)
            desk.setdefault("block_edits", {}).pop(block, None)
            desk["block_focus"] = "matter"
            self._regrade()

        def term_option_ids(field: str) -> list[str]:
            belief = self.belief
            if field == "kind":
                return list(composer.TERM_KINDS)
            if field == "good":
                goods = [
                    str(item.get("id"))
                    for item in belief.get("gift_goods", [])
                    if item.get("id")
                ]
                return goods or [
                    str(good)
                    for good, amount in belief.get("stores", {}).items()
                    if type(amount) is int and amount > 0
                ]
            if field == "person_id":
                return [
                    str(person["id"])
                    for person in belief.get("house", {}).get("members", [])
                    if person.get("alive")
                ]
            if field == "destination":
                return [
                    str(place.get("id"))
                    for place in worldmap.places_in_order(belief)
                    if place.get("id")
                ]
            return []

        def move_term_field(by: int) -> None:
            builder = desk.setdefault(
                "term_builder",
                self._new_term_builder(desk.get("target_place", "")))
            fields = composer.term_fields(builder)
            current = desk.get("term_focus", fields[0])
            if current not in fields:
                current = fields[0]
            desk["term_focus"] = fields[
                (fields.index(current) + by) % len(fields)]

        def move_term_value(by: int) -> None:
            builder = desk.setdefault(
                "term_builder",
                self._new_term_builder(desk.get("target_place", "")))
            fields = composer.term_fields(builder)
            field = desk.get("term_focus", fields[0])
            if field not in fields:
                field = fields[0]
                desk["term_focus"] = field
            if field == "quantity":
                builder[field] = max(
                    1, int(builder.get(field, 1)) + by * 10)
                return
            if field == "due_turn":
                builder[field] = max(
                    0, int(builder.get(field, 0)) + by)
                return
            options = term_option_ids(field)
            if not options:
                return
            current = str(builder.get(field, ""))
            index = options.index(current) if current in options else 0
            builder[field] = options[(index + by) % len(options)]
            if field == "kind":
                valid = composer.term_fields(builder)
                if desk.get("term_focus") not in valid:
                    desk["term_focus"] = valid[0]

        def add_term() -> None:
            builder = desk.setdefault(
                "term_builder",
                self._new_term_builder(desk.get("target_place", "")))
            kind = str(builder.get("kind") or composer.TERM_KINDS[0])
            values = {
                "kind": kind,
                "due_turn": int(builder.get("due_turn", 0)),
            }
            if kind in {"gift", "request_good", "promise_good"}:
                values.update(
                    good=str(builder.get("good") or ""),
                    quantity=int(builder.get("quantity", 0)))
            elif kind == "service":
                values.update(
                    quantity=int(builder.get("quantity", 0)),
                    destination=str(builder.get("destination") or ""))
            else:
                values = {
                    "kind": kind,
                    "person_id": str(builder.get("person_id") or ""),
                }
            try:
                term = A.LetterTerm(**values)
            except (TypeError, ValueError) as error:
                self.notify(
                    f"That term is incomplete: {error}.",
                    registry.REFUSAL, window="stack")
                return
            desk["terms"] = tuple(desk.get("terms", ())) + (term,)
            self.notify(
                "The material term is impressed beneath the wording.",
                registry.SUCCESS, window="stack")

        def remove_term() -> None:
            terms = tuple(desk.get("terms", ()))
            if not terms:
                self.notify("No material term is impressed.",
                            registry.REFUSAL, window="stack")
                return
            desk["terms"] = terms[:-1]
            self.notify("The last material term is smoothed away.",
                        registry.SUCCESS, window="stack")

        if desk["dictating"]:
            if event.keysym == "Escape":
                desk["buffer"] = desk.pop("edit_origin_text")
                if desk.pop("editing_block", ""):
                    desk["dictating"] = False
                    desk["dictated"] = desk.pop("edit_origin_dictated", False)
                    self._regrade()
                    self.repaint()
                    return
                desk["matter"] = desk["buffer"]
                desk["dictated"] = desk.pop("edit_origin_dictated", False)
                desk["cursor"] = min(
                    len(desk["buffer"]), desk.get("cursor", 0))
                desk["history"] = []
                desk["future"] = []
                desk["dictating"] = False
                self._regrade()
                self.repaint()
                return
            if control and event.keysym.lower() == "d":
                desk["dictating"] = False
                desk["dictated"] = True
                desk.pop("edit_origin_text", None)
                desk.pop("edit_origin_dictated", None)
                written = desk.pop("editing_block", "")
                if written and written != "matter":
                    desk.setdefault("block_edits", {})[written] = \
                        desk["buffer"].strip()
                    self._regrade()
                    self.repaint()
                    return
                desk["matter"] = desk["buffer"].strip()
                desk["buffer"] = desk["matter"]
                desk["cursor"] = min(desk["cursor"], len(desk["buffer"]))
                self._regrade()
                self.repaint()
                return
            if control and event.keysym.lower() in {"z", "y"}:
                source = desk["history"] if event.keysym.lower() == "z" \
                    else desk["future"]
                target = desk["future"] if event.keysym.lower() == "z" \
                    else desk["history"]
                if source:
                    target.append(desk["buffer"])
                    desk["buffer"] = source.pop()
                    desk["cursor"] = min(
                        desk.get("cursor", 0), len(desk["buffer"]))
                    self._regrade()
                    self.repaint()
                return
            if event.keysym in {"Left", "Right", "Up", "Down",
                                "Home", "End"}:
                cursor = desk.get("cursor", len(desk["buffer"]))
                if event.keysym == "Left":
                    cursor = max(0, cursor - 1)
                elif event.keysym == "Right":
                    cursor = min(len(desk["buffer"]), cursor + 1)
                elif event.keysym == "Up":
                    cursor = self._move_desk_cursor(
                        desk["buffer"], cursor, -1)
                elif event.keysym == "Down":
                    cursor = self._move_desk_cursor(
                        desk["buffer"], cursor, 1)
                elif event.keysym == "Home":
                    cursor = desk["buffer"].rfind("\n", 0, cursor) + 1
                else:
                    end = desk["buffer"].find("\n", cursor)
                    cursor = len(desk["buffer"]) if end < 0 else end
                desk["cursor"] = cursor
                self.repaint()
                return

            before = desk["buffer"]
            cursor = desk.get("cursor", len(before))
            changed = True
            if event.keysym == "BackSpace":
                if cursor:
                    desk["buffer"] = before[:cursor - 1] + before[cursor:]
                    desk["cursor"] = cursor - 1
                else:
                    changed = False
            elif event.keysym == "Delete":
                if cursor < len(before):
                    desk["buffer"] = before[:cursor] + before[cursor + 1:]
                else:
                    changed = False
            elif event.keysym == "Return":
                desk["buffer"] = before[:cursor] + "\n" + before[cursor:]
                desk["cursor"] = cursor + 1
            elif event.char and event.char.isprintable():
                desk["buffer"] = before[:cursor] + event.char + before[cursor:]
                desk["cursor"] = cursor + len(event.char)
            else:
                return
            if changed:
                desk["history"].append(before)
                desk["history"] = desk["history"][-100:]
                desk["future"] = []
                desk["dictated"] = True
                desk.pop("advisor_origin", None)
                self._regrade()
                self.repaint()
            return

        if command.startswith("block:"):
            chosen = command.split(":", 1)[1]
            if chosen in composer.FOCI:
                desk["block_focus"] = chosen
                self.repaint()
            return
        if command.startswith("desk:term:focus:"):
            field = command.rsplit(":", 1)[1]
            if field in composer.term_fields(desk.get("term_builder")):
                desk["term_focus"] = field
                desk["block_focus"] = "terms"
            self.repaint()
            return
        if command == "desk:term:field:next" or (
                char == "t" and desk.get("block_focus") == "terms"):
            move_term_field(1)
            self.repaint()
            return
        if command == "desk:term:value:previous":
            move_term_value(-1)
            self.repaint()
            return
        if command == "desk:term:value:next":
            move_term_value(1)
            self.repaint()
            return
        if command == "desk:block:add" or char == "+":
            add_block()
            self.repaint()
            return
        if command == "desk:block:remove" or char == "-":
            remove_block()
            self.repaint()
            return
        if command == "desk:block:previous" or event.keysym == "Up":
            move_block(-1)
            self.repaint()
            return
        if command == "desk:block:next" or event.keysym in {"Down", "Tab"}:
            move_block(1)
            self.repaint()
            return
        if command == "desk:choice:previous" or event.keysym == "Left":
            move_choice(-1)
            self.repaint()
            return
        if command == "desk:choice:next" or event.keysym == "Right":
            move_choice(1)
            self.repaint()
            return
        if event.keysym == "Escape":
            self._store_active_desk()
            self.desk = None
            self.repaint()
            return
        if command == "desk:discard" or char == "x":
            draft_key = str(
                desk.get("draft_key") or desk.get("letter_id")
                or f"new:{desk.get('recipient', '')}")
            self.__dict__.setdefault("desk_drafts", {}).pop(
                draft_key, None)
            self.desk = None
            self.repaint()
            return
        if command == "desk:undo-correction" or (
                char == "u" and "advisor_origin" in desk):
            desk["matter"] = desk.pop("advisor_origin")
            desk["buffer"] = desk["matter"]
            desk["cursor"] = len(desk["matter"])
            self._regrade()
            self.repaint()
            return
        if command == "desk:correct" or char in {"y", "g"}:
            self._request_desk_draft(item_for_desk())
            self.repaint()
            return
        if command == "desk:edit" or char in {"e", "d"}:
            block = desk.get("block_focus", "matter")
            if block != "matter":
                # Editing a piece writes over its canned form. The piece keeps
                # its place and its name; only the words become the king's.
                picked = composer.selected_blocks(
                    item_for_desk()["sender"], desk.get("blocks"),
                    desk.get("block_edits"))
                desk["editing_block"] = block
                desk["edit_origin_text"] = desk.setdefault(
                    "block_edits", {}).get(
                        block, picked.get(block).text if block in picked else "")
                desk["edit_origin_dictated"] = desk["dictated"]
                desk["dictating"] = True
                desk["buffer"] = desk["edit_origin_text"]
                desk["cursor"] = len(desk["buffer"])
                desk["history"] = []
                desk["future"] = []
                self.repaint()
                return
            desk["block_focus"] = "matter"
            desk["edit_origin_text"] = desk.get("matter", "")
            desk["edit_origin_dictated"] = desk["dictated"]
            desk["dictating"] = True
            desk["dictated"] = True
            desk["buffer"] = desk.get("matter", "")
            desk["cursor"] = len(desk["buffer"])
            desk["history"] = []
            desk["future"] = []
            self._regrade()
            self.repaint()
            return
        if command == "desk:dispatch" or char == "s" or \
                event.keysym == "Return":
            if not desk.get("matter", "").strip():
                self.notify(
                    "The matter is blank. Write one or two sentences first.",
                    registry.REFUSAL, window="stack")
                self.repaint()
                return
            count = composer.sentence_count(desk["matter"])
            if count > 2:
                self.notify(
                    f"The matter has {count} sentences. Keep two, or ask "
                    "Yabninu to tighten it.",
                    registry.REFUSAL, window="stack")
                self.repaint()
                return
            if desk.get("composing", False):
                self.notify(
                    "Yabninu is still correcting the matter.",
                    registry.REFUSAL, window="stack")
                self.repaint()
                return
            draft = desk["draft"]
            recipient = str(
                desk.get("recipient") or item_for_desk().get("sender") or "")
            seal = composer.seal_id(
                recipient, desk.get("blocks"))
            if not seal:
                self.notify(
                    "An unsealed tablet cannot be dispatched. Choose a seal.",
                    registry.REFUSAL, window="stack")
                self.repaint()
                return
            path = tuple(desk.get("path") or ())
            if not path:
                self.notify(
                    "No courier route to that court is known.",
                    registry.REFUSAL, window="stack")
                self.repaint()
                return
            draft_key = str(
                desk.get("draft_key") or desk.get("letter_id")
                or f"new:{recipient}")
            action = A.DispatchLetter(
                recipient=recipient,
                reply_to=str(desk.get("reply_to") or ""),
                text=draft.text,
                profile=draft.profile,
                terms=tuple(desk.get("terms", ())),
                scribe_id=str(desk.get("scribe_id") or "yabninu"),
                seal=seal,
                courier_id=str(desk.get("courier_id") or "iliya"),
                path=path,
                orders=tuple(item.describe() for item in self._desk_commitments()),
                tone=next((line.split(" · ", 1)[1] for line in self._desk_bound()
                           if line.startswith("tone · ")), "plain"),
                unparsed=tuple(line.split(" · ", 1)[1] for line in self._desk_bound()
                               if line.startswith("unparsed · ")),
            )
            sealed = self.do(action, window="stack")
            if sealed:
                self.__dict__.setdefault("desk_drafts", {}).pop(
                    draft_key, None)
                self.desk = None
                self.inbox_filter = "outbox"
                self.inbox_pick = ""
                self.inbox_body_scroll = 0
                self.inbox_pane = "rack"
                self.repaint()
                app = getattr(self, "app", None)
                window = (
                    app.windows.get("stack") if app is not None else None)
                if window is not None:
                    window.focus()
            return

    # --- Help, counsel, the altar, and the tablet house ----------------------

    # --- the field manual ----------------------------------------------------

    def help_topics(self) -> tuple:
        """The topics Help is currently showing, in order."""
        return manual.search(self.help_query, self.help_screen)

    # --- the five ledgers (UI/UX spec 15, phase 4) ----------------------------

    @property
    def ledger_state(self) -> dict:
        """Selection, scroll, and the amount in hand, per ledger window.

        Lazily made for the same reason the notice table is: the headless tests
        drive these handlers through `Game.__new__`, and a workbench that only
        works after a constructor they skip is a workbench that is not tested.
        """
        state = self.__dict__.get("_ledger_state")
        if state is None:
            state = self.__dict__["_ledger_state"] = {
                key: {"pick": "", "scroll": 0, "amount": 0}
                for key in ("stores", "roll", "land", "reserves", "dues",
                            "muster", "oaths")
            }
            state["roll"]["priority"] = []
            state["land"]["group"] = ""
            state["muster"]["task"] = ledger_page.TASKS[0]
            state["muster"]["place"] = ""
        return state

    @property
    def storehouse_view(self) -> str:
        return self.__dict__.get("_storehouse_view", "stores")

    @storehouse_view.setter
    def storehouse_view(self, view: str) -> None:
        if view in {key for key, _label in ledger_page.STOREHOUSE_VIEWS}:
            self.__dict__["_storehouse_view"] = view

    # --- the Orders workbench (UI/UX spec 13) ---------------------------------

    @property
    def orders_state(self) -> dict:
        state = self.__dict__.get("_orders_state")
        if state is None:
            state = self.__dict__["_orders_state"] = {
                "view": orders_page.VIEWS[0][0], "pick": "", "scroll": 0}
        return state

    def on_orders_key(self, event) -> None:
        """Choose a view, choose an order, and countermand what can be.

        Countermanding is not an undo: it gives the inverse order, which the
        engine charges for and the log records beside the first. Both stay
        visible here afterwards, because both happened.
        """
        state = self.orders_state
        command = getattr(event, "command", "")
        char = (event.char or "").lower()
        if event.keysym == "Escape":
            self.app.close("orders")
            return
        if command.startswith("tab:"):
            state["view"] = command.split(":", 1)[1]
            state["pick"] = ""
            state["scroll"] = 0
            self.repaint()
            return
        if event.keysym in {"Tab", "ISO_Left_Tab"}:
            views = [key for key, _label in orders_page.VIEWS]
            step = -1 if event.keysym == "ISO_Left_Tab" or getattr(event, "state", 0) & 1 else 1
            state["view"] = views[(views.index(state["view"]) + step) % len(views)]
            state["pick"] = ""
            state["scroll"] = 0
            self.repaint()
            return
        if char.isdigit() and 1 <= int(char) <= len(orders_page.VIEWS):
            state["view"] = orders_page.VIEWS[int(char) - 1][0]
            state["pick"] = ""
            state["scroll"] = 0
            self.repaint()
            return
        if command.startswith("pick:"):
            state["pick"] = command.split(":", 1)[1]
            self.repaint()
            return
        rows = self.window_rows("orders")
        if event.keysym in ("Up", "Down"):
            if rows:
                if state["pick"] not in rows:
                    state["pick"] = rows[0 if event.keysym == "Down" else -1]
                else:
                    here = rows.index(state["pick"])
                    state["pick"] = rows[collection.step(
                        len(rows), here, 1 if event.keysym == "Down" else -1)]
            self.repaint()
            return
        if event.keysym in ("Prior", "Next", "Home", "End"):
            state["scroll"] = max(0, min(
                state["scroll"] + self.STEPS[event.keysym],
                max(0, len(rows) - 1)))
            self.repaint()
            return

        chosen = self.chosen_order()
        wanted = command.split(":", 1)[1] if command.startswith("do:") else ""
        if event.keysym == "Return" or char == "o" or wanted == "open":
            self.open_where_given(chosen)
            return
        if char == "u" or (wanted and wanted != "open"):
            self.countermand(chosen)

    def chosen_order(self):
        state = self.orders_state
        given = orders_page.visible(
            orders_page.history(self.log), state["view"],
            self.world.date.absolute)
        return next((order for order in given if order.id == state["pick"]),
                    given[0] if given else None)

    def countermand(self, order) -> None:
        """Give the inverse order, or say plainly that there is not one."""
        if order is None:
            self.notify("choose an order first.", registry.REFUSAL,
                        window="orders")
            self.repaint()
            return
        reversal = orders_page.countermand(order)
        if reversal is None:
            self.notify("that order cannot be unsaid.", registry.REFUSAL,
                        window="orders")
            self.repaint()
            return
        if self.do(reversal, window="orders"):
            self.orders_state["pick"] = ""

    def open_where_given(self, order) -> None:
        """Open the screen this order belongs to, so the evidence is at hand."""
        descriptor = order.descriptor if order is not None else None
        if descriptor is None:
            self.notify("there is no screen for that order.",
                        registry.REFUSAL, window="orders")
            self.repaint()
            return
        if set(descriptor.contexts) & {"roll", "land"}:
            self.storehouse_view = (
                "land" if "land" in descriptor.contexts else "roll")
            self.open_ledger("t")
            return
        if "archive" in descriptor.contexts:
            self.inbox_filter = "records"
            self.open_tablet("s")
            return
        doors = ({window: char for char, (window, _t, _h) in LEDGERS.items()}
                 | {window: char for char, (window, _t, _h) in ROOMS.items()}
                 | {window: char for char, (window, _t, _h) in TABLETS.items()})
        for context in descriptor.contexts:
            char = doors.get(context)
            if char is None:
                continue
            self.open_door(char)
            return
        self.notify(f"{descriptor.label} has no window of its own.",
                    registry.REFUSAL, window="orders")
        self.repaint()

    def window_rows(self, key: str) -> list[str]:
        """The ids a window is listing, in the order it lists them.

        One id however many times it can be clicked. The palace draws each
        matter twice on purpose -- once as a man standing on the floor and
        once as a line in the list -- and both are selectable. Counting both
        made the arrow keys walk a list with the first few ids repeated at the
        front, so pressing Down cycled among the men who happened to fit in
        the room and never reached the rest.
        """
        screen = self.compose(key)
        if screen is None:
            return []
        if isinstance(screen, InteractiveScreen) and screen.row_ids:
            return list(screen.row_ids)
        rows: list[str] = []
        for hit in screen.hits:
            if not hit.command.startswith("pick:"):
                continue
            row = hit.command.split(":", 1)[1]
            if row not in rows:
                rows.append(row)
        return rows

    def compose_ledger(self, key: str, b: dict, width: int, height: int,
                       notice) -> Screen:
        if key == "stores":
            view = self.storehouse_view
            state = self.ledger_state[view]
            common = dict(
                selected=state["pick"], width=width, height=height,
                scroll=state["scroll"], notice=notice, hours=self.hours,
                room=True)
            if view == "roll":
                return ledger_page.roll(
                    b, amount=state["amount"],
                    priority=tuple(state["priority"]), **common)
            if view == "land":
                return ledger_page.land(
                    b, days=state["amount"],
                    group=state.get("group", ""), **common)
            if view in {"reserves", "dues"}:
                return ledger_page.storehouse_account(
                    b, view, drafts=state.setdefault("rates", {}), **common)
            return ledger_page.stores(
                b, amount=state["amount"], **common)
        state = self.ledger_state[key]
        common = dict(selected=state["pick"], width=width, height=height,
                      scroll=state["scroll"], notice=notice, hours=self.hours)
        if key == "roll":
            return ledger_page.roll(
                b, amount=state["amount"],
                priority=tuple(state["priority"]), **common)
        if key == "land":
            return ledger_page.land(
                b, days=state["amount"],
                group=state.get("group", ""), **common)
        if key == "muster":
            return ledger_page.muster(b, task=state["task"],
                                      place=state["place"],
                                      amount=state["amount"],
                                      view=getattr(self, "muster_view", "formations"),
                                      **common)
        return ledger_page.oaths(b, amount=state["amount"], **common)

    def ledger_rows(self, key: str) -> list[str]:
        """The ids the window is listing, in the order it lists them.

        Read back off the composed screen's own hit regions rather than
        recomputed here: two ideas about what row three is, is exactly the bug
        the Alu had, and the screen is the one that knows.
        """
        return self.window_rows(key)

    def open_ledger(self, char: str) -> None:
        window_key, title, handler = LEDGERS[char]
        width, height = desktop.default_size(window_key)
        window = self.app.window(
            window_key, title, width, height,
            on_key=getattr(self, handler), on_resize=self.on_resize,
            on_close=lambda k=window_key: self.app.close(k))
        self.repaint()
        window.focus()

    def open_orders(self) -> None:
        """The Alu's station of standing orders (UI/UX spec 15, phase 4)."""
        window_key, title, handler = "orders", "Orders", "on_orders_key"
        width, height = desktop.default_size(window_key)
        window = self.app.window(
            window_key, title, width, height,
            on_key=getattr(self, handler), on_resize=self.on_resize,
            on_close=lambda k=window_key: self.app.close(k))
        self.repaint()
        window.focus()

    def open_counsel(self) -> None:
        """The Court's station for a word with the scribe."""
        width, height = desktop.default_size("counsel")
        window = self.app.window(
            "counsel", "Counsel", width, height,
            on_key=self.on_counsel_key, on_resize=self.on_resize,
            on_close=lambda: self.app.close("counsel"))
        self.repaint()
        window.focus()

    def open_oaths(self) -> None:
        """The Shrine's station for the oaths sworn to the house."""
        width, height = desktop.default_size("oaths")
        window = self.app.window(
            "oaths", "The Oaths", width, height,
            on_key=self.on_oaths_key, on_resize=self.on_resize,
            on_close=lambda: self.app.close("oaths"))
        self.repaint()
        window.focus()

    def open_plague(self) -> None:
        """The World's station for sickness and physical closures."""
        width, height = desktop.default_size("plague")
        window = self.app.window(
            "plague", "Sickness and Closures", width, height,
            on_key=self.on_plague_key, on_resize=self.on_resize,
            on_close=lambda: self.app.close("plague"))
        self.repaint()
        window.focus()

    def ledger_key(self, key: str, event, step: int,
                   window: str | None = None) -> bool:
        """The parts every ledger shares: close, choose, scroll, set an amount.

        Returns True when it handled the key, so each screen's own handler is
        only the orders that are actually its own.
        """
        state = self.ledger_state[key]
        if event.keysym == "Escape":
            self.app.close(window or key)
            return True
        command = getattr(event, "command", "")
        if command.startswith("pick:"):
            state["pick"] = command.split(":", 1)[1]
            self.repaint()
            return True
        rows = self.window_rows(window or key)
        # The composers visibly land on a first row. Keep the controller on
        # that same row before interpreting a key, so the first arrow or
        # action never targets an invisible empty selection.
        if rows and state["pick"] not in rows:
            state["pick"] = rows[0]
        if event.keysym in ("Up", "Down"):
            if rows:
                here = rows.index(state["pick"])
                state["pick"] = rows[collection.step(
                    len(rows), here,
                    1 if event.keysym == "Down" else -1)]
                self.repaint()
            return True
        if event.keysym in ("Prior", "Next", "Home", "End"):
            if rows:
                screen = self.compose(window or key)
                visible: list[str] = []
                if screen is not None:
                    for hit in screen.hits:
                        if not hit.command.startswith("pick:"):
                            continue
                        row = hit.command.split(":", 1)[1]
                        if row not in visible:
                            visible.append(row)
                page_size = max(1, len(visible))
                here = rows.index(state["pick"])
                if event.keysym == "Home":
                    target = 0
                elif event.keysym == "End":
                    target = len(rows) - 1
                else:
                    by = page_size if event.keysym == "Next" else -page_size
                    target = max(0, min(len(rows) - 1, here + by))
                state["pick"] = rows[target]
                max_start = max(0, len(rows) - page_size)
                if event.keysym == "Home":
                    state["scroll"] = 0
                elif event.keysym == "End":
                    state["scroll"] = max_start
                else:
                    state["scroll"] = max(
                        0, min(max_start, state["scroll"] + (
                            page_size if event.keysym == "Next"
                            else -page_size)))
            self.repaint()
            return True
        char = event.char or ""
        if char in ("[", "]") and step:
            # The amount in hand. Never below nothing: an order for minus two
            # hundred qa of grain is not a thing a king can give.
            state["amount"] = max(
                0, state["amount"] + (step if char == "]" else -step))
            self.repaint()
            return True
        return False

    def on_storehouse_key(self, event) -> None:
        """Move among the connected goods, labour, and estate stations."""
        command = getattr(event, "command", "")
        char = (event.char or "").lower()
        chosen = ""
        if command.startswith("tab:"):
            chosen = command.split(":", 1)[1]
        elif event.keysym in {"Tab", "ISO_Left_Tab"}:
            views = tuple(key for key, _label in ledger_page.STOREHOUSE_VIEWS)
            step = -1 if event.keysym == "ISO_Left_Tab" or getattr(event, "state", 0) & 1 else 1
            chosen = views[(views.index(self.storehouse_view) + step) % len(views)]
        elif char.isdigit() and 1 <= int(char) <= len(ledger_page.STOREHOUSE_VIEWS):
            chosen = ledger_page.STOREHOUSE_VIEWS[int(char) - 1][0]
        if chosen in {key for key, _label in ledger_page.STOREHOUSE_VIEWS}:
            self.storehouse_view = chosen
            self.clear_notice("stores")
            self.repaint()
            return
        if self.storehouse_view in {"reserves", "dues"}:
            self.on_storehouse_account_key(event)
        elif self.storehouse_view == "roll":
            self.on_roll_key(event, window="stores")
        elif self.storehouse_view == "land":
            self.on_land_key(event, window="stores")
        else:
            self.on_stores_key(event, window="stores")

    def on_storehouse_account_key(self, event) -> None:
        view = self.storehouse_view
        state = self.ledger_state[view]
        if self.ledger_key(view, event, 0, "stores"):
            return
        if view != "dues":
            return
        char = event.char or ""
        command = getattr(event, "command", "")
        target = state["pick"] or "land"
        if char in {"<", ">"}:
            self._draft_due(target, -25 if char == "<" else 25)
            return
        if event.keysym == "Return" or command == "due:commit":
            self._commit_due(target, "stores")

    def _draft_due(self, target: str, by: int) -> None:
        drafts = self.ledger_state["dues"].setdefault("rates", {})
        current = (self.belief.get("land", {}).get("land_due_rate", 0)
                   if target == "land" else
                   self.belief.get("revenue", {}).get("harbour_rate", 0))
        drafted = max(0, min(1000, drafts.get(target, current) + by))
        if drafted == current:
            drafts.pop(target, None)
        else:
            drafts[target] = drafted
        self.repaint()

    def _commit_due(self, target: str, window: str) -> None:
        drafts = self.ledger_state["dues"].setdefault("rates", {})
        if target not in drafts:
            return
        action = (A.SetLandDue(drafts[target]) if target == "land"
                  else A.SetHarbourDue(drafts[target]))
        if self.do(action, window=window):
            drafts.pop(target, None)

    def on_stores_key(self, event, window: str = "stores") -> None:
        state = self.ledger_state["stores"]
        if not state["pick"]:
            goods = sorted(self.belief.get("stores", {}).items())
            stocked = [good for good, held in goods if held]
            state["pick"] = ("grain" if "grain" in stocked else
                             stocked[0] if stocked else
                             goods[0][0] if goods else "")
        if self.ledger_key(
                "stores", event, ledger_page.STEPS["stores"], window):
            return
        char = (event.char or "").lower()
        command = getattr(event, "command", "")
        wanted = command.split(":", 1)[1] if command.startswith("do:") else ""
        if event.keysym == "Return" and not state["pick"]:
            goods = sorted(self.belief.get("stores", {}))
            state["pick"] = goods[0] if goods else ""
        ledger = ledger_page.LEDGER_OF.get(state["pick"], "")
        if event.keysym == "Return" and state["pick"]:
            good = state["pick"]
            if good in self.belief.get("stores", {}):
                history = self.belief.get("store_history", {}).get(good, ())
                held = self.belief["stores"][good]
                ration = sum(c.get("ration", 0) for c in self.belief.get("cohorts", ()))
                self.open_focus("good", {
                    "id": good, "name": good, "quantity": held,
                    "quantity_reading": render.fmt_good(good, held),
                    "ration_need": ration if good == "grain" else None,
                    "coverage_fortnights": held // ration if good == "grain" and ration else None,
                    "history": list(history), "change": (
                        history[-1] - history[-2] if len(history) > 1 else 0),
                    "source": "inspected ledger" if ledger in self.belief.get("inspected", ())
                    else "keeper's count", "as_of_turn": self.belief.get("turn"),
                    "certainty": "counted" if ledger in self.belief.get("inspected", ())
                    else "reported"})
        elif (char == _key("inspect_ledger") or wanted == "inspect_ledger") \
                and ledger:
            self.do(A.InspectLedger(ledger), window=window)

    def on_roll_key(self, event, window: str = "roll") -> None:
        state = self.ledger_state["roll"]
        active = list(self.belief.get("priority", ()))
        if state["pick"] not in active:
            state["pick"] = active[0] if active else ""
        before_pick = state["pick"]
        pick = before_pick
        group = next((item for item in self.belief.get("groups", ())
                      if item["id"] == pick), None)
        # Four presses span an ordinary ration even for the palace populace;
        # exact figures remain available through the command line.
        ration_step = max(
            ledger_page.STEPS["roll"],
            (group["size"] * group["entitlement"] // 4) if group else 0)
        if (event.char or "") in {"[", "]"} and not state["amount"] \
                and group is not None:
            # Brackets adjust the ration shown on the row. Starting at zero
            # made the first decrease a no-op and several increases necessary
            # just to reach today's ration.
            state["pick"] = pick
            state["amount"] = group["allocated"]
        if self.ledger_key("roll", event, ration_step, window):
            if state["pick"] != before_pick:
                state["amount"] = 0
                self.repaint()
            return
        char = (event.char or "").lower()
        command = getattr(event, "command", "")
        wanted = command.split(":", 1)[1] if command.startswith("do:") else ""
        order = list(state["priority"] or active)
        pick = state["pick"] or (order[0] if order else "")
        direction = (
            -1 if (event.keysym == "Left" or command == "ration:earlier"
                   or wanted == "set_priority")
            else 1 if event.keysym == "Right" or command == "ration:later"
            else -1 if char == _key("set_priority") else 0)
        if direction and pick in order:
            here = order.index(pick)
            there = max(0, min(len(order) - 1, here + direction))
            if there != here:
                order[here], order[there] = order[there], order[here]
                state["priority"] = order if order != active else []
            state["pick"] = pick
            self.repaint()
            return
        if char == _key("allocate") or wanted == "allocate":
            if not pick or state["amount"] <= 0:
                self.notify("choose a group and an amount.",
                            registry.REFUSAL, window=window)
                self.repaint()
                return
            if self.do(A.Allocate(pick, state["amount"]), window=window):
                state["amount"] = 0
        elif event.keysym == "Return" or command == "ration:commit":
            if not state["priority"]:
                item = next((g for g in self.belief.get("groups", ())
                             if g["id"] == pick), None)
                if item:
                    self.open_focus("cohort", item)
                return
            if self.do(A.SetPriority(tuple(state["priority"])), window=window):
                state["priority"] = []
        elif char == _key("send_to_harvest") or wanted == "send_to_harvest":
            if not pick:
                return
            item = next((g for g in self.belief.get("groups", ())
                         if g["id"] == pick), None)
            self.do(A.SendToHarvest(
                pick, not bool(item and item.get("at_fields"))), window=window)

    def on_land_key(self, event, window: str = "land") -> None:
        state = self.ledger_state["land"]
        if self.ledger_key("land", event, ledger_page.STEPS["corvee"], window):
            return
        char = event.char or ""
        command = getattr(event, "command", "")
        wanted = command.split(":", 1)[1] if command.startswith("do:") else ""
        data = self.belief.get("land") or {}
        rate = data.get("land_due_rate", 0)
        step = ledger_page.STEPS["land_due"]
        if char in {"<", ">"}:
            self._draft_due("land", -step if char == "<" else step)
            self.storehouse_view = "dues"
            self.ledger_state["dues"]["pick"] = "land"
            self.repaint()
        elif char.lower() == _key("levy_cohort") or wanted == "levy_cohort":
            self.command_line = "levy "
            if hasattr(self, "app"):
                self.open_palette()
            else:
                self.notify("Command is ready: levy …", registry.PREVIEW,
                            window=window)
                self.repaint()
        elif char.lower() == _key("dredge_canal") or wanted == "dredge_canal":
            estate = next(
                (e for e in data.get("estates", [])
                 if e["id"] == state["pick"]), None)
            if estate is None or not estate.get("irrigated") \
                    or state["amount"] <= 0:
                self.notify(
                    "choose an estate with a canal, and days to spend on it.",
                    registry.REFUSAL, window=window)
                self.repaint()
                return
            if self.do(A.DredgeCanal(estate["id"], state["amount"]),
                       window=window):
                state["amount"] = 0
        elif char.lower() == "g":
            groups = [item["id"] for item in self.belief.get("groups", [])]
            if groups:
                here = (groups.index(state["group"])
                        if state.get("group") in groups else -1)
                state["group"] = groups[(here + 1) % len(groups)]
                self.repaint()
        elif char.lower() == _key("send_to_harvest") or wanted == "send_to_harvest":
            if not state.get("group"):
                self.notify("[g] chooses which hands go to the fields.",
                            registry.REFUSAL, window=window)
                self.repaint()
                return
            item = next((g for g in self.belief.get("groups", ())
                         if g["id"] == state["group"]), None)
            self.do(A.SendToHarvest(
                state["group"], not bool(item and item.get("at_fields"))),
                window=window)
        elif char.lower() == _key("inspect_ledger") or wanted == "inspect_ledger":
            self.do(A.InspectLedger("seed"), window=window)
        elif char.lower() == _key("set_land_due") or wanted == "set_land_due":
            self.storehouse_view = "dues"
            self.ledger_state["dues"]["pick"] = "land"
            self.notify("Draft the land due there; Enter gives one order.",
                        registry.PREVIEW, window="stores")
            self.repaint()

    def on_muster_key(self, event) -> None:
        state = self.ledger_state["muster"]
        command = getattr(event, "command", "")
        char = (event.char or "").lower()
        views = tuple(key for key, _label in ledger_page.MUSTER_VIEWS)
        view = getattr(self, "muster_view", views[0])
        if command.startswith("tab:"):
            self.muster_view = command.split(":", 1)[1]
            self.repaint()
            return
        if event.keysym in {"Tab", "ISO_Left_Tab"}:
            step = -1 if event.keysym == "ISO_Left_Tab" or getattr(event, "state", 0) & 1 else 1
            self.muster_view = views[(views.index(view) + step) % len(views)]
            self.repaint()
            return
        if char.isdigit() and 1 <= int(char) <= len(views):
            self.muster_view = views[int(char) - 1]
            self.repaint()
            return
        if self.ledger_key(
                "muster", event, ledger_page.STEPS["corvee"]):
            return
        wanted = command.split(":", 1)[1] if command.startswith("do:") else ""
        b = self.belief
        if event.keysym == "Return" and state["pick"]:
            item = next((item for item in b.get("troops", {}).get("formations", ())
                         if item["id"] == state["pick"]), None)
            item = item or next((item for item in b.get("cohorts", ())
                                 if item["id"] == state["pick"]), None)
            if item:
                self.open_focus("formation" if "strength" in item else "cohort", item)
            return
        formations = b.get("troops", {}).get("formations", [])
        formation = next(
            (f for f in formations if f["id"] == state["pick"]), None)
        places = [place["id"] for place in affordances.places(b)]
        if view in {"cohorts", "draft"} and (
                char == _key("levy_cohort") or wanted == "levy_cohort"):
            self.command_line = "levy "
            if hasattr(self, "app"):
                self.open_palette()
            else:
                self.notify("Command is ready: levy …", registry.PREVIEW,
                            window="muster")
                self.repaint()
        elif view == "detachments" and (char == "r" or wanted == "release_cohort"):
            self.command_line = "release "
            self.open_palette()
        elif char == "t":
            tasks = ledger_page.TASKS
            state["task"] = tasks[
                (tasks.index(state["task"]) + 1) % len(tasks)]
            self.repaint()
        elif char == "l" and places:
            here = places.index(state["place"]) if state["place"] in places \
                else -1
            state["place"] = places[(here + 1) % len(places)]
            self.repaint()
        elif view == "formations" and (
                char == _key("assign_troops") or wanted == "assign_troops"):
            if formation is None or not state["place"]:
                self.notify(
                    "choose a formation, then a task and a place with [t]"
                    " and [l].", registry.REFUSAL, window="muster")
                self.repaint()
                return
            self.do(A.AssignTroops(formation["id"], state["task"],
                                   state["place"]), window="muster")
        elif char in (_key("place_person"), _key("dismiss_person")) \
                or wanted in ("place_person", "dismiss_person"):
            # A formation's command is a post like any other, and the House is
            # where the people to fill it are. Say so rather than refusing.
            self.notify(
                "a commander is appointed in the House, where the people are.",
                registry.PREVIEW, window="muster")
            self.repaint()

    def on_oaths_key(self, event, window: str = "oaths") -> None:
        state = self.ledger_state["oaths"]
        if self.ledger_key("oaths", event, ledger_page.STEPS["expiate"], window):
            return
        char = (event.char or "").lower()
        command = getattr(event, "command", "")
        wanted = command.split(":", 1)[1] if command.startswith("do:") else ""
        oath = next((o for o in self.belief.get("oaths", [])
                     if o["id"] == state["pick"]), None)
        if char == _key("swear_oath") or wanted == "swear_oath":
            if oath is None or not oath.get("lapsed"):
                self.notify("only an oath that has lapsed is sworn again.",
                            registry.REFUSAL, window=window)
                self.repaint()
                return
            self.do(A.SwearOath(oath["id"]), window=window)
        elif char == _key("expiate") or wanted == "expiate":
            if oath is None or state["amount"] <= 0:
                self.notify("choose an oath, and what you would lay down.",
                            registry.REFUSAL, window=window)
                self.repaint()
                return
            if self.do(A.Expiate(oath["id"], state["amount"]), window=window):
                state["amount"] = 0

    # --- the command palette (UI/UX spec 10) ----------------------------------

    def open_palette(self) -> None:
        """`:` or a backtick, from anywhere. Free, and never a model call."""
        width, height = desktop.default_size("palette")
        window = self.app.window(
            "palette", "Command", width, height,
            on_key=self.on_palette_key, on_resize=self.on_resize,
            on_close=lambda: self.app.close("palette"))
        self.repaint()
        window.focus()

    def close_palette(self) -> None:
        self.command_line = ""
        self.command_recall = 0
        self.app.close("palette")
        self.repaint()

    def run_command(self) -> None:
        """Do what the line says, or explain why it cannot be done.

        The palette gives orders through the same `do` as every key and every
        click, so a typed `repair the granary` costs what the button costs,
        logs what the button logs, and refuses in the same words.
        """
        line = self.command_line.strip()
        if not line:
            return
        result = command_palette.parse(line, self.belief)
        if result.status != "ok":
            self.notify(result.message or "that is not an order",
                        registry.REFUSAL, window="palette")
            self.repaint()
            return
        self.command_history.append(line)
        self.command_recall = 0

        # Some forms are a workflow rather than an action. `answer <tablet>`
        # opens the Desk, where a reply is actually written.
        opens = command_palette.handoff(result)
        if opens == "desk":
            self.command_line = ""
            self.app.close("palette")
            self.open_desk(result.values["tablet"])
            return

        action = command_palette.build(result)
        if action is None:
            self.notify("that order could not be assembled",
                        registry.REFUSAL, window="palette")
            self.repaint()
            return
        outcome = self.do(action, window="palette")
        if outcome.ok:
            self.command_line = ""
        self.repaint()

    def on_palette_key(self, event) -> None:
        """Typing, completion, history, and one Enter that gives the order."""
        keysym = event.keysym
        if keysym == "Escape":
            self.close_palette()
            return
        command = getattr(event, "command", "")
        if command.startswith("complete:"):
            offer = command.split(":", 1)[1]
            words = self.command_line.split()
            if words and not self.command_line.endswith(" ") and \
                    offer.startswith(words[-1].lower()):
                self.command_line = " ".join(words[:-1] + [offer])
            else:
                self.command_line = (
                    self.command_line.rstrip() + " " + offer).strip()
            self.repaint()
            return
        if keysym == "Return":
            self.run_command()
            return
        if keysym == "Tab":
            self.command_line = command_palette.complete(
                self.command_line, self.belief)
            self.repaint()
            return
        if keysym in ("BackSpace", "Delete"):
            self.command_line = self.command_line[:-1]
            self.repaint()
            return
        if keysym in ("Up", "Down") and self.command_history:
            # Walk back through what was typed before, newest first.
            step = 1 if keysym == "Up" else -1
            self.command_recall = max(
                0, min(len(self.command_history), self.command_recall + step))
            self.command_line = (
                "" if not self.command_recall
                else self.command_history[-self.command_recall])
            self.repaint()
            return
        if event.char and event.char.isprintable():
            self.command_line += event.char
            self.repaint()

    def open_help(self, screen: str = "") -> None:
        """Raise the manual, set to the screen the player came from (spec 11).

        Free, immediate, and deterministic: no model, no attention, no waiting.
        """
        self.help_screen = screen or self._focused_screen()
        topics = self.help_topics()
        if topics and self.help_pick not in {t.id for t in topics}:
            self.help_pick = topics[0].id
        width, height = desktop.default_size("help")
        window = self.app.window(
            "help", "Help", width, height,
            on_key=self.on_help_key, on_resize=self.on_resize,
            on_close=lambda: self.app.close("help"))
        self.repaint()
        window.focus()

    def _focused_screen(self) -> str:
        """Whichever window the player was last in, for Help's context."""
        for key in self.app.live():
            if key not in ("help", "switcher"):
                return key
        return "hall"

    def on_help_key(self, event) -> None:
        """Arrows walk the topics, printable keys search, Escape closes.

        Every keystroke re-scans the corpus. There is no submit step because
        there is no question being asked of anyone -- the manual is a book, and
        typing into it is turning to a page.
        """
        keysym = event.keysym
        char = event.char or ""
        topics = self.help_topics()
        ids = [topic.id for topic in topics]

        if keysym == "Escape":
            self.app.close("help")
            return
        command = getattr(event, "command", "")
        if command.startswith("topic:"):
            self.help_pick = command.split(":", 1)[1]
        elif getattr(event, "state", 0) & 4 and keysym.lower() == "u":
            self.help_query = ""
            self.help_pick = ""
        elif keysym in ("Down", "Up") and ids:
            index = ids.index(self.help_pick) if self.help_pick in ids else 0
            index = (index + (1 if keysym == "Down" else -1)) % len(ids)
            self.help_pick = ids[index]
        elif keysym in ("Next", "Prior") and ids:
            index = ids.index(self.help_pick) if self.help_pick in ids else 0
            step = 8 if keysym == "Next" else -8
            self.help_pick = ids[max(0, min(len(ids) - 1, index + step))]
        elif keysym in ("BackSpace", "Delete"):
            self.help_query = self.help_query[:-1]
            self.help_pick = ""
        elif char.isprintable() and char:
            self.help_query += char
            self.help_pick = ""
        else:
            return

        topics = self.help_topics()
        if topics and self.help_pick not in {t.id for t in topics}:
            self.help_pick = topics[0].id
        self.repaint()

    def ask_counsel(self, question: str, topic: str = "") -> None:
        """An hour for an answer. He talks; the model does the talking (D38).

        No engine action: a conversation changes nothing in the world, and the
        hours are session state (attention is derived — see `hall.compose`). So
        nothing goes in the log and a replay is unaffected.
        """
        question = question.strip()
        if not question:
            self.counsel_said.append((
                "scribe", "Ask me a question, my lord."))
            self.repaint()
            return
        if self.hours < counsel.ASK_COST:
            self.counsel_said.append((
                "scribe",
                f"That question takes {counsel.ASK_COST} hour; "
                f"{self.hours} remain."))
            self.repaint()
            return
        self.hours -= counsel.ASK_COST
        b = self.belief
        turn = self.world.date.absolute
        # What he is wrong about is settled here, before any prompt exists.
        remembered = counsel.recall(b, topic, self.seed, turn) if topic else {}
        asks_advice = any(phrase in question.casefold() for phrase in (
            "should", "what do you", "would you", "recommend", "advise"))
        authored = (
            counsel.recommend(b, topic) if asks_advice else
            counsel.answer(b, topic, self.seed, turn) if topic else
            counsel.recommend(b, ""))
        said = list(self.counsel_said)
        self.counsel_said.append(("king", question))
        self.repaint()          # his question lands before the answer does
        knowledge = ai_counsel.digest(b, remembered)

        def work():
            return ai_counsel.speak(
                question, said, knowledge, authored,
                self.seed, turn, self.client)

        def done(result, error) -> None:
            text = authored if error is not None or result is None else result[0]
            self.counsel_said.append(("scribe", text))
            self.repaint()

        if self.client is None:
            done(work(), None)
        else:
            self._run_model(work, done)

    @staticmethod
    def _question_topic(question: str) -> str:
        lowered = question.casefold()
        for topic, words in {
            "grain": ("grain", "granary", "food", "ration"),
            "arrears": ("owed", "unpaid", "arrears", "allocation"),
            "unanswered": ("unanswered", "written", "reply", "letter"),
            "oaths": ("oath", "bound", "sworn"),
            "troops": ("troop", "men", "army", "muster"),
            "unrest": ("town", "unrest", "people", "mood"),
        }.items():
            if any(word in lowered for word in words):
                return topic
        return ""

    @staticmethod
    def _looks_like_question(text: str) -> bool:
        lowered = text.casefold().strip()
        starts = ("who ", "what ", "where ", "when ", "why ", "how ",
                  "which ", "tell me ", "do we ", "are we ", "is there ")
        return text.rstrip().endswith("?") or lowered.startswith(starts)

    def _describe_order(self, action) -> str:
        b = self.belief
        if isinstance(action, A.Allocate):
            group = next((g["name"] for g in b["groups"]
                          if g["id"] == action.group_id), action.group_id)
            return f"{group} will be allocated {render.fmt_good('grain', action.qa)}"
        if isinstance(action, A.SetPriority):
            return "the pay-down order has been changed"
        if isinstance(action, A.ReadLetter):
            return f"tablet {action.letter_id} has been read and placed in the Inbox"
        if isinstance(action, A.ArchiveLetter):
            return (
                f"tablet {action.letter_id} has been "
                f"{'filed' if action.archived else 'restored to the Inbox'}")
        if isinstance(action, A.DelegateLetter):
            person = next((p["name"] for p in b.get("house", {}).get(
                "members", []) if p["id"] == action.person_id),
                action.person_id)
            return f"tablet {action.letter_id} has been entrusted to {person}"
        if isinstance(action, A.InspectLedger):
            return f"the {action.ledger.replace('_', ' ')} has been inspected"
        if isinstance(action, A.SendGift):
            return (
                f"{action.quantity:,} {action.good} will be sent to "
                f"{render.actor_name(action.recipient, b.get('house'))}")
        if isinstance(action, A.SendToHarvest):
            group = next((g["name"] for g in b["groups"]
                          if g["id"] == action.group_id), action.group_id)
            return f"{group} will {'go to the fields' if action.to_fields else 'return from the fields'}"
        if isinstance(action, A.AssignTroops):
            formation = next((f["name"] for f in b.get("troops", {}).get(
                "formations", []) if f["id"] == action.formation_id),
                action.formation_id)
            place = f" at {action.place}" if action.place else ""
            return f"{formation} will {action.task}{place}"
        if isinstance(action, A.RaiseCorvee):
            return f"{action.days:,} days of corvée have been called"
        if isinstance(action, A.DredgeCanal):
            return f"{action.days:,} days will dredge the canal at {action.estate_id.replace('_', ' ')}"
        if isinstance(action, A.BeginBuild):
            return f"a {action.kind.replace('_', ' ')} has been put in hand"
        if isinstance(action, A.BeginRepair):
            return f"repairs to {action.institution.replace('_', ' ')} have begun"
        if isinstance(action, A.AbandonWork):
            return f"work on {action.project.replace('_', ' ')} has been called off"
        if isinstance(action, A.Quarantine):
            verb = "reopened" if action.lift else "closed"
            return f"the routes to {action.place_id.replace('_', ' ')} have been {verb}"
        if isinstance(action, A.ConsultDiviner):
            return f"the diviner has been asked of {action.question}"
        if isinstance(action, A.MarryAbroad):
            person = next((p["name"] for p in b.get("house", {}).get(
                "members", []) if p["id"] == action.person_id), action.person_id)
            return (
                f"{person} will be sent to the court of "
                f"{render.actor_name(action.actor, b.get('house'))}")
        if isinstance(action, A.SwearOath):
            return f"{action.oath_id.replace('_', ' ')} has been re-sworn"
        if isinstance(action, A.SuppressOmen):
            return f"omen {action.omen_id} has been kept from the record"
        if isinstance(action, A.DefyOmen):
            return f"the court will act against omen {action.omen_id}"
        if isinstance(action, A.Expiate):
            return (
                f"{action.offering:,} grain has been offered against "
                f"{action.oath_id.replace('_', ' ')}")
        if isinstance(action, A.HearPetition):
            return f"both sides of {action.petition_id.replace('_', ' ')} have been heard"
        if isinstance(action, A.RulePetition):
            return f"judgement in {action.petition_id.replace('_', ' ')} is {action.verdict}"
        if isinstance(action, A.SetLandDue):
            return f"the land due is now {action.rate} in one thousand"
        if isinstance(action, A.SetHarbourDue):
            return f"the harbour due is now {action.rate} in one thousand"
        if isinstance(action, A.PlacePerson):
            person = next((p["name"] for p in b.get("house", {}).get(
                "members", []) if p["id"] == action.person_id), action.person_id)
            return f"{person} has been placed at {action.post.replace('_', ' ')}"
        if isinstance(action, A.DismissPerson):
            return f"the holder of {action.post.replace('_', ' ')} has been dismissed"
        if isinstance(action, A.NameHeir):
            person = next((p["name"] for p in b.get("house", {}).get(
                "members", []) if p["id"] == action.person_id), action.person_id)
            return f"{person} has been named heir"
        if isinstance(action, A.SearchArchive):
            return f"the tablet house has searched for {action.query!r}"
        name = type(action).__name__
        return name.replace("_", " ").lower()

    def execute_counsel_actions(self, actions: tuple[object, ...]) -> None:
        """Preflight the whole instruction, then commit it as one audience."""
        self.counsel_pending = None
        if not actions:
            self.counsel_said.append((
                "scribe", "There is no order on the tablet, my lord."))
            self.repaint()
            return
        if any(isinstance(action, A.DictateReply) for action in actions):
            self.counsel_said.append((
                "scribe",
                "I will not put words in your mouth, my lord. The form of "
                "letters is being reconsidered; for now, write at the Desk."))
            self.repaint()
            return
        if any(isinstance(action, A.EndTurn) for action in actions):
            if len(actions) != 1:
                self.counsel_said.append((
                    "scribe", "End the fortnight as a separate order, my lord."))
                self.repaint()
                return
            self.counsel_said.append(("scribe", "The audience is ended."))
            self.end_fortnight()
            return

        costs = [ai_parser.action_cost(action) for action in actions]
        total = sum(costs)
        if total > self.hours:
            self.counsel_said.append((
                "scribe",
                f"That requires {total} hours, my lord, and {self.hours} remain."))
            self.repaint()
            return

        trial = self.world
        try:
            for action in actions:
                trial, _events = apply(trial, action)
        except (ValueError, TypeError, KeyError, ModuleNotFoundError) as error:
            self.counsel_said.append(("scribe", f"I cannot do that: {error}."))
            self.repaint()
            return

        descriptions = [self._describe_order(action) for action in actions]
        for action, cost in zip(actions, costs):
            self.world, _events = apply(self.world, action)
            self.hours -= cost
            self.log.append({"turn": self.world.date.absolute,
                             "action": A.to_dict(action)})
        self.counsel_said.append((
            "scribe", "It is done: " + "; ".join(descriptions) + "."))
        self.repaint()

    def preview_counsel_actions(self, actions: tuple[object, ...]) -> None:
        """Resolve an instruction, but do not let parsing itself issue it.

        The parser is interface machinery and must be exact.  Yabninu therefore
        reads back the closed Action objects in player-facing language, and a
        second Enter is the explicit commit.
        """
        if not actions:
            self.counsel_said.append((
                "scribe", "I found no order in those words, my lord."))
            self.repaint()
            return
        if any(isinstance(action, A.DictateReply) for action in actions):
            self.counsel_said.append((
                "scribe",
                "I will not put words in your mouth, my lord. Write that "
                "answer at the Desk, where you can see the tablet it answers."))
            self.repaint()
            return
        if any(isinstance(action, A.EndTurn) for action in actions):
            if len(actions) != 1:
                self.counsel_said.append((
                    "scribe", "End the fortnight as a separate order, my lord."))
                self.repaint()
                return
            descriptions = ["end this fortnight"]
            total = 0
        else:
            costs = [ai_parser.action_cost(action) for action in actions]
            total = sum(costs)
            if total > self.hours:
                self.counsel_said.append((
                    "scribe",
                    f"That requires {total} hours, my lord, and "
                    f"{self.hours} remain."))
                self.repaint()
                return
            trial = self.world
            try:
                for action in actions:
                    trial, _events = apply(trial, action)
            except (ValueError, TypeError, KeyError,
                    ModuleNotFoundError) as error:
                self.counsel_said.append((
                    "scribe", f"I cannot make that order: {error}."))
                self.repaint()
                return
            descriptions = [self._describe_order(action) for action in actions]

        self.counsel_pending = {
            "actions": tuple(actions),
            "descriptions": descriptions,
        }
        cost_words = (
            "It costs no audience hours"
            if total == 0 else
            f"It will use {total} hour{'s' if total != 1 else ''}")
        self.counsel_said.append((
            "scribe",
            "I understand the order as: "
            + "; ".join(descriptions)
            + f". {cost_words}. Press Enter again to confirm it."))
        self.repaint()

    def confirm_counsel_order(self) -> None:
        pending = self.counsel_pending
        if pending is None:
            return
        actions = pending["actions"]
        self.counsel_pending = None
        self.execute_counsel_actions(actions)

    def cancel_counsel_order(self) -> None:
        if self.counsel_pending is None:
            return
        self.counsel_pending = None
        self.counsel_said.append(("scribe", "The draft order is struck out."))
        self.repaint()

    def submit_counsel(self, text: str) -> None:
        text = text.strip()
        if not text:
            self.counsel_said.append((
                "scribe", "Say what is to be done, my lord."))
            self.repaint()
            return
        self.counsel_said.append(("king", text))
        if self._looks_like_question(text):
            # `ask_counsel` appends the king's words itself.
            self.counsel_said.pop()
            self.ask_counsel(text, self._question_topic(text))
            return
        belief = self.belief
        turn = self.world.date.absolute
        # A clientless controller exists only in headless tests and recovery.
        # Normal free-form court language goes to the required local model
        # first; exact direct controls use their own structured paths.
        if self.client is None:
            immediate = ai_parser.preparse(text, belief)
            if immediate is not None:
                self._accept_counsel_result(immediate)
                return

        def work():
            return ai_parser.parse(
                text, belief, self.hours, self.seed, turn, self.client)

        def done(result, error) -> None:
            if error is not None:
                self.counsel_said.append((
                    "scribe", f"I could not read that order: {error}."))
                self.repaint()
                return
            self._accept_counsel_result(result)

        if self.client is not None:
            self._run_model(work, done)
            return
        done(work(), None)

    def _accept_counsel_result(self, result) -> None:
        """Surface one parsed result; parsing itself never mutates the world."""
        if result is None:
            self.counsel_said.append((
                "scribe", "I found neither a question nor an order in those "
                "words, my lord."))
            self.repaint()
            return
        if result.actions:
            self.preview_counsel_actions(result.actions)
        elif result.question:
            self.counsel_said.append(("scribe", result.question))
            self.repaint()
        elif result.unavailable:
            self.counsel_said.append((
                "scribe",
                "I could not make a precise order of that. Name the men, "
                "place, and quantity another way, my lord."))
            self.repaint()
        else:
            self.counsel_said.append((
                "scribe",
                "I found neither a question nor an order in those words, "
                "my lord."))
            self.repaint()

    def on_counsel_key(self, event) -> None:
        if event.keysym == "Escape":
            if self.counsel_pending is not None:
                self.cancel_counsel_order()
                return
            self.app.close("counsel")
            return
        if getattr(event, "state", 0) & 4 and event.keysym.lower() == "u":
            self.counsel_typed = ""
            if self.counsel_pending is not None:
                self.cancel_counsel_order()
                return
            self.counsel_typing = True
            self.repaint()
            return
        if self.counsel_pending is not None:
            if event.keysym == "Return":
                self.confirm_counsel_order()
            return
        if event.keysym in ("BackSpace", "Delete"):
            self.counsel_typed = self.counsel_typed[:-1]
        elif event.keysym == "Return":
            words, self.counsel_typed = self.counsel_typed, ""
            self.submit_counsel(words)
            return
        elif (event.char or "") == "/" and not self.counsel_typed:
            pass
        elif (event.char or "").isprintable():
            self.counsel_typed += event.char
        else:
            return
        self.counsel_typing = True
        self.repaint()

    def on_altar_key(self, event) -> None:
        views = altar.VIEWS
        view = getattr(self, "shrine_view", "rites")
        command = getattr(event, "command", "")
        char = (event.char or "").lower()
        if command.startswith("tab:"):
            self.shrine_view = command.split(":", 1)[1]
            self.repaint()
            return
        if char.isdigit() and 1 <= int(char) <= len(views):
            self.shrine_view = views[int(char) - 1]
            self.repaint()
            return
        if event.keysym in {"Tab", "ISO_Left_Tab"}:
            step = -1 if event.keysym == "ISO_Left_Tab" or getattr(event, "state", 0) & 1 else 1
            self.shrine_view = views[(views.index(view) + step) % len(views)]
            self.repaint()
            return
        if view in {"oaths", "obligations"}:
            if view == "obligations" and event.keysym == "Return":
                selected = self.ledger_state["oaths"]["pick"]
                item = next((record for record in self.belief.get("obligations", ())
                             if record["id"] == selected), None)
                if item:
                    self.open_focus("obligation", item)
                    return
            self.on_oaths_key(event, window="altar")
            return
        if event.keysym == "Escape":
            self.app.close("altar")
            return
        if view == "offerings":
            for key, good, quantity in altar.OFFERINGS:
                if char == key:
                    self.altar_offering = (good, quantity)
                    self.repaint()
                    return
            if event.keysym == "Return":
                self.shrine_view = "rites"
                self.repaint()
            return
        omen = next((o for o in reversed(self.belief.get("house", {}).get("omens", ()))
                     if o.get("published") and not o.get("defied")), None)
        wanted = command.split(":", 1)[1] if command.startswith("do:") else ""
        if omen and (char in {"s", "d"} or wanted in {"suppress_omen", "defy_omen"}):
            suppress = char == "s" or wanted == "suppress_omen"
            self.do((A.SuppressOmen if suppress else A.DefyOmen)(omen["id"]),
                    window="altar")
            return
        people = [
            person for person in self.belief.get(
                "house", {}).get("members", [])
            if person["alive"]
        ]
        people_ids = [person["id"] for person in people]
        if char in {"[", "]"} and self.altar_question == "death":
            if not people_ids:
                self.altar_subject = ""
                self.altar_notice = (
                    "There is no living member of the house to name.")
            else:
                try:
                    index = people_ids.index(self.altar_subject)
                except ValueError:
                    index = 0
                step = -1 if char == "[" else 1
                self.altar_subject = people_ids[
                    (index + step) % len(people_ids)]
                self.altar_notice = ""
            self.repaint()
            return
        for key, _label, topic in altar.QUESTIONS:
            if char == key:
                self.altar_question = topic
                if topic == "death" and self.altar_subject not in people_ids:
                    self.altar_subject = people_ids[0] if people_ids else ""
                self.altar_notice = ""
                self.repaint()
                return
        for key, good, quantity in altar.OFFERINGS:
            if char == key:
                self.altar_offering = (good, quantity)
                self.altar_notice = ""
                self.repaint()
                return
        if event.keysym == "Return" or command == "altar:ask":
            if self.hours < OMEN_COST:
                self.altar_notice = (
                    f"The rite requires {OMEN_COST} hours; "
                    f"{self.hours} remain.")
                self.repaint()
                return
            if (self.altar_question == "death"
                    and self.altar_subject not in people_ids):
                self.altar_notice = (
                    "Name a living member of the house before asking.")
                self.repaint()
                return
            good, quantity = self.altar_offering or ("", 0)
            subject = (
                self.altar_subject if self.altar_question == "death" else "")
            action = A.ConsultDiviner(
                self.altar_question, subject, good, quantity)
            try:
                self.world, events = apply(self.world, action)
            except ValueError as error:
                self.altar_notice = f"The diviner refuses: {error}."
                self.repaint()
                return
            self.hours -= OMEN_COST
            self.log.append(
                {"turn": self.world.date.absolute,
                 "action": A.to_dict(action)})
            taken = next((e for e in events
                          if isinstance(e, A.OmenTaken)), None)
            if taken is not None:
                self.altar_readings.append(
                    f"He reads the liver and says: {taken.reported}.")
                self.altar_notice = ""
            else:
                self.altar_notice = "No reading was entered on the tablet."
            self.repaint()

    def open_works(self) -> None:
        """The works window. Free to look at: the hours go on the orders."""
        window = self.app.window(
            "works", "The Works", 82, 32,
            on_key=self.on_works_key, on_close=lambda: self.app.close("works"))
        self.repaint()
        window.focus()

    def on_works_key(self, event) -> None:
        """Read and commission a plan, or call off sunk work."""
        if event.keysym == "Escape":
            self.works_pick = ""
            self.works_plan_pick = ""
            self.app.close("works")
            return
        char = (event.char or "").lower()
        command = getattr(event, "command", "")
        b = self.belief
        projects = b.get("projects") or []
        plans = b.get("plans") or []
        width, height = self._size("works")
        out = collection.page(
            len(projects), works_page.project_room(height),
            self.scroll_of("works_scroll"))
        plan_page = works_page.plan_page(
            b, width, height,
            self.scroll_of("works_scroll"),
            self.scroll_of("works_plan_scroll"))

        if event.keysym in self.STEPS:
            # Two lists in one window: the men out scroll, and shifted arrows
            # take the plans below them.
            step = self.STEPS[event.keysym]
            shifted = bool(getattr(event, "state", 0) & 1)
            if shifted:
                moved = bool(plan_page.room) and self.scrolled(
                    "works_plan_scroll", len(plans), plan_page.room, step)
                if moved:
                    self.works_plan_pick = ""
            else:
                moved = self.scrolled(
                    "works_scroll", len(projects),
                    works_page.project_room(height), step)
            if moved:
                self.repaint()
            return
        if command.startswith("works:plan:"):
            kind = command.split(":", 2)[2]
            if kind in {plan["kind"] for plan in plan_page.slice(plans)}:
                self.works_plan_pick = kind
                self.works_pick = ""
                self.repaint()
            return
        if char and char in works_page.PICK:
            if out.absolute(works_page.PICK.index(char) + 1) >= 0:
                self.works_pick = char
                self.works_plan_pick = ""
                self.repaint()
            return
        if char == "x" and self.works_pick:
            index = out.absolute(works_page.PICK.index(self.works_pick) + 1)
            if index >= 0:
                self.do(A.AbandonWork(projects[index]["id"]), window="works")
            self.works_pick = ""
            self.repaint()
            return
        if char and char in works_page.ORDER:
            index = plan_page.absolute(works_page.ORDER.index(char) + 1)
            if index >= 0:
                self.works_plan_pick = plans[index]["kind"]
                self.works_pick = ""
                self.repaint()
            return
        if event.keysym == "Return":
            visible = plan_page.slice(plans)
            chosen = next((plan for plan in visible
                           if plan["kind"] == getattr(
                               self, "works_plan_pick", "")), None)
            chosen = chosen or (visible[0] if visible else None)
            if chosen is not None:
                self.order(A.BeginBuild(chosen["kind"],
                                        b.get("seat", "seat")),
                           window="works")
            return

    def on_institution_key(self, event, key: str, institution: str) -> None:
        """One verb: [r], set the men to it. Everything else closes the window.

        The order is given here rather than on the ALU list because repair is
        a thing you decide about *one* building, standing in front of it, and
        the list is for comparing."""
        if event.keysym == "Escape":
            self.app.close(key)
            return
        if (event.char or "").lower() == "r":
            self.order(A.BeginRepair(institution), window=key)

    def order(self, action, window: str | None = None) -> None:
        """Issue one direct order and leave a visible receipt or refusal."""
        self.do(action, window=window)
        self.repaint()

    def on_alu_key(self, event) -> None:
        """Numbers walk down to the thing and look at it. An hour, every time.

        The head's figure is on the list; the true one is only ever bought. A
        failed inspection stays on this screen with its reason visible.
        """
        if event.keysym == "Escape":
            self.app.close("alu")
            return
        char = event.char or ""
        views = alu.VIEWS
        view = getattr(self, "alu_view", views[0])
        command = getattr(event, "command", "")
        if command.startswith("tab:"):
            self.alu_view = command.split(":", 1)[1]
            self.repaint()
            return
        if command.startswith("alu:open:"):
            ref = command.split(":", 2)[2]
            self.alu_pick = ref
            item = next((item for item in self.belief.get("cohorts", ())
                         if item["id"] == ref), None)
            item = item or next((item for item in self.belief.get("institutions", ())
                                 if item["id"] == ref), None)
            item = item or next((item for item in alu.sites(self.belief)
                                 if item["id"] == ref), None)
            item = item or next((item for item in self.belief.get("projects", ())
                                 if item["id"] == ref), None)
            if item:
                kind = ("cohort" if item in self.belief.get("cohorts", ()) else
                        "institution" if item in self.belief.get("institutions", ()) else
                        "project" if item in self.belief.get("projects", ()) else "site")
                self.open_focus(kind, item)
            return
        if event.keysym in {"Tab", "ISO_Left_Tab"}:
            step = -1 if event.keysym == "ISO_Left_Tab" or getattr(event, "state", 0) & 1 else 1
            self.alu_view = views[(views.index(view) + step) % len(views)]
            self.repaint()
            return
        if (view != "institutions" and char.isdigit()
                and 1 <= int(char) <= len(views)):
            self.alu_view = views[int(char) - 1]
            self.repaint()
            return
        if char.lower() == "n":
            self.open_works()
            return
        if char.lower() == "o":
            self.open_orders()
            return
        if char.lower() == "s":
            self.open_ledger("t")
            return
        if view in {"overview", "cohorts"} and char.lower() in {"a", "z", "d", "f"}:
            self.command_line = {"a": "accept ", "z": "settle ",
                                 "d": "redirect ", "f": "refuse "}[char.lower()]
            self.open_palette()
            return
        if view == "works":
            if event.keysym == "Return":
                projects = self.belief.get("projects", ())
                item = next((p for p in projects
                             if p["id"] == getattr(self, "alu_pick", "")),
                            projects[0] if projects else None)
                if item:
                    self.open_focus("project", item)
            return
        if view in {"cohorts", "sites"} and (
                event.keysym in {"Up", "Down"} or command == "alu:next"):
            source = (self.belief.get("cohorts", ()) if view == "cohorts"
                      else alu.sites(self.belief))
            ids = [item["id"] for item in source]
            if ids:
                picked = getattr(self, "alu_pick", "")
                if picked not in ids:
                    self.alu_pick = ids[0 if event.keysym == "Down" else -1]
                else:
                    here = ids.index(picked)
                    self.alu_pick = ids[(here + (-1 if event.keysym == "Up" else 1)) % len(ids)]
                self.repaint()
            return
        if view in {"cohorts", "sites"} and event.keysym == "Return":
            ref = getattr(self, "alu_pick", "")
            source = (self.belief.get("cohorts", ()) if view == "cohorts"
                      else alu.sites(self.belief))
            if not ref and source:
                ref = source[0]["id"]
            item = next((item for item in self.belief.get("cohorts", ())
                         if item["id"] == ref), None)
            item = item or next((item for item in alu.sites(self.belief)
                                 if item["id"] == ref), None)
            if item:
                self.open_focus("cohort" if view == "cohorts" else "site", item)
            return
        if view != "institutions":
            return
        institutions = self.belief.get("institutions", [])

        def open_institution(inst):
            self.alu_pick = inst["id"]
            if not inst["inspected"] and not self.do(
                    A.InspectLedger(f"institution:{inst['id']}"), window="alu"):
                return
            key = f"institution:{inst['id']}"
            window = self.app.window(
                key, inst["name"], 68, 22,
                on_key=lambda e, k=key, i=inst["id"]: self.on_institution_key(e, k, i),
                on_close=lambda k=key: self.app.close(k))
            self.repaint()
            window.focus()

        if (event.keysym in {"Up", "Down"} or command == "alu:next") and institutions:
            ids = [item["id"] for item in institutions]
            here = ids.index(getattr(self, "alu_pick", "")) if getattr(self, "alu_pick", "") in ids else 0
            self.alu_pick = ids[(here + (-1 if event.keysym == "Up" else 1)) % len(ids)]
            self.repaint()
            return
        if event.keysym == "Return" and institutions:
            inst = next((item for item in institutions
                         if item["id"] == getattr(self, "alu_pick", "")), institutions[0])
            open_institution(inst)
            return
        _width, height = self._size("alu")
        room = alu.table_room(height)
        if event.keysym in self.STEPS:
            if self.scrolled("alu_scroll", len(institutions), room,
                             self.STEPS[event.keysym]):
                self.repaint()
            return
        if char.isdigit() and char != "0":
            # The digit means the nth row *shown*, which after a scroll is not
            # the nth institution. The screen's own page resolves it.
            page = collection.page(
                len(institutions), room, self.scroll_of("alu_scroll"))
            index = page.absolute(int(char))
            if index < 0:
                return
            open_institution(institutions[index])

    def on_archive_key(self, event, embedded: bool = False) -> None:
        if embedded and self.archive_open_ref:
            if event.keysym == "Escape":
                self.archive_open_ref = ""
                self.archive_document_scroll["embedded"] = 0
                self.repaint()
                return
            if event.keysym in {"Up", "Down"}:
                step = -1 if event.keysym == "Up" else 1
                self.archive_document_scroll["embedded"] = max(
                    0, self.archive_document_scroll.get("embedded", 0) + step)
                self.repaint()
            return
        if event.keysym == "Escape":
            if self.archive_typing:
                self.archive_typing = False
                self.repaint()
                return
            if embedded:
                self.inbox_filter = "all"
                self.archive_open_ref = ""
                self.repaint()
            else:
                self.app.close("archive")
            return
        command = getattr(event, "command", "")
        if command.startswith("open:"):
            ref = command.split(":", 1)[1]
            self.archive_pick = ref
            item = next(
                (hit for hit in self.archive_hits
                 if str(hit.get("ref", "")) == ref),
                None)
            if item is not None:
                if embedded:
                    self.archive_open_ref = ref
                    self.archive_document_scroll["embedded"] = 0
                    self.repaint()
                else:
                    self.open_archive_document(item)
            return
        if self.archive_typing:
            if event.keysym in ("BackSpace", "Delete"):
                self.archive_query = self.archive_query[:-1]
            elif event.keysym == "Return":
                self.archive_typing = False
                self.search_archive(window="stack" if embedded else "archive")
                return
            elif event.char and event.char.isprintable():
                self.archive_query += event.char
            else:
                return
            self.repaint()
            return
        char = event.char or ""
        if (event.keysym in self.STEPS or command == "archive:next") \
                and self.archive_hits:
            refs = [str(hit.get("ref", "")) for hit in self.archive_hits]
            here = refs.index(self.archive_pick) if self.archive_pick in refs else 0
            self.archive_pick = refs[collection.step(
                len(refs), here, self.STEPS.get(event.keysym, 1))]
            self.repaint()
            return
        if char.isdigit() and char != "0" and self.archive_hits:
            size = self._size("stack" if embedded else "archive") \
                if hasattr(self, "app") else (84, 32)
            selected = next(
                (i for i, hit in enumerate(self.archive_hits)
                 if str(hit.get("ref", "")) == getattr(self, "archive_pick", "")), -1)
            page = archive.result_page(
                len(self.archive_hits), getattr(self, "archive_summary", ""), *size,
                self.scroll_of("archive_scroll"), embedded, selected)
            index = page.absolute(int(char))
            if index < 0:
                return
            item = self.archive_hits[index]
            self.archive_pick = str(item.get("ref", ""))
            if embedded:
                self.archive_open_ref = self.archive_pick
                self.archive_document_scroll["embedded"] = 0
                self.repaint()
            else:
                self.open_archive_document(item)
            return
        if char == "/":
            self.archive_typing = True
            self.archive_query = ""
            self.archive_pick = ""
            self.repaint()
        elif event.keysym == "Return":
            item = next((hit for hit in self.archive_hits
                         if str(hit.get("ref", "")) == self.archive_pick), None)
            if item is not None:
                if embedded:
                    self.archive_open_ref = self.archive_pick
                    self.archive_document_scroll["embedded"] = 0
                    self.repaint()
                else:
                    self.open_archive_document(item)
            else:
                self.search_archive(window="stack" if embedded else "archive")

    # --- the palace: court, house and relations in one room (spec 16) --------

    @property
    def palace_state(self) -> dict:
        state = self.__dict__.get("_palace_state")
        if state is None:
            state = self.__dict__["_palace_state"] = {
                "view": palace.VIEWS[0][0], "pick": {}, "scroll": 0,
                "choosing": "", "person": "", "amount": 0, "good": "copper"}
        return state

    def palace_pick(self, listing: str = "") -> str:
        state = self.palace_state
        listing = listing or self.palace_listing()
        chosen = state["pick"].get(listing, "")
        rows = palace.listing_rows(self.belief, listing)
        if chosen and any(row.id == chosen for row in rows):
            return chosen
        if not rows:
            state["pick"].pop(listing, None)
            return ""
        chosen = rows[0].id
        state["pick"][listing] = chosen
        return chosen

    def palace_listing(self) -> str:
        state = self.palace_state
        if state["view"] in {"house", "people", "household", "advisers"} \
                and state["choosing"] == "post":
            return "post"
        return state["view"]

    def on_palace_key(self, event) -> None:
        """One room, three views, and one way of choosing a thing in each.

        Every branch below either moves the selection or gives an order. The
        three screens this replaces each had their own answer to "what does a
        digit mean here", and two of them had no answer at all to "what does
        the letter I just pressed act on".
        """
        state = self.palace_state
        char = event.char or ""
        lower = char.lower()
        command = getattr(event, "command", "")
        listing = self.palace_listing()

        if event.keysym == "Escape":
            if state["choosing"]:
                state["choosing"] = ""
                self.repaint()
                return
            self.app.close("palace")
            return
        if command.startswith("tab:") and not state["choosing"]:
            state["view"] = command.split(":", 1)[1]
            state["scroll"] = 0
            self.repaint()
            return
        if event.keysym in {"Tab", "ISO_Left_Tab"} and not state["choosing"]:
            views = tuple(key for key, _label in palace.VIEWS)
            step = -1 if event.keysym == "ISO_Left_Tab" or getattr(event, "state", 0) & 1 else 1
            state["view"] = views[(views.index(state["view"]) + step) % len(views)]
            state["scroll"] = 0
            self.repaint()
            return
        if command.startswith("pick:"):
            state["pick"][listing] = command.split(":", 1)[1]
            self.repaint()
            return

        rows = self.window_rows("palace")
        if event.keysym == "Return" and not state["choosing"]:
            ref = self.palace_pick()
            pools = (self.belief.get("justice", {}).get("petitions", ()),
                     self.belief.get("house", {}).get("members", ()),
                     self.belief.get("institutions", ()),
                     self.belief.get("relations", ()))
            item = next((item for pool in pools for item in pool
                         if item.get("id", item.get("other")) == ref), None)
            if item:
                kind = ("person" if listing in {"house", "people", "household", "advisers"}
                        else "institution" if listing in {"post", "offices"}
                        else "petition" if listing in {"court", "audience", "justice"}
                        else listing)
                self.open_focus(kind, item)
            return
        if event.keysym in ("Up", "Down"):
            # Walked over everything the view lists, not over the rows that
            # happen to fit: a man below the fold is still a man in the queue,
            # and the scroll follows the selection rather than the other way
            # about.
            everything = [row.id for row in
                          palace.listing_rows(self.belief, listing)]
            if everything:
                here = (everything.index(self.palace_pick())
                        if self.palace_pick() in everything else 0)
                index = collection.step(
                    len(everything), here, 1 if event.keysym == "Down" else -1)
                state["pick"][listing] = everything[index]
                if everything[index] not in rows:
                    state["scroll"] = index
            self.repaint()
            return
        if event.keysym in self.STEPS:
            state["scroll"] = max(0, min(state["scroll"] + self.STEPS[event.keysym],
                                         max(0, len(rows) - 1)))
            self.repaint()
            return
        if char.isdigit() and char != "0":
            number = int(char)
            if not state["choosing"] and number <= len(palace.VIEWS):
                state["view"] = palace.VIEWS[number - 1][0]
                state["scroll"] = 0
            elif number <= len(rows):
                state["pick"][listing] = rows[number - 1]
            self.repaint()
            return

        if lower == "c" and not state["choosing"]:
            self.open_counsel()
            return

        if state["choosing"] == "post":
            self.palace_place(command, event.keysym, lower)
            return
        if state["view"] in {"court", "audience", "justice"}:
            self.palace_court(command, lower)
        elif state["view"] in {"house", "people", "household", "advisers"}:
            self.palace_house(command, lower)
        elif state["view"] == "relations":
            self.palace_relations(command, char)

    def palace_court(self, command: str, char: str) -> None:
        listing = self.palace_listing()
        petition = self.palace_pick(listing)
        wanted = command.split(":", 1)[1] if command.startswith("do:") else ""
        if not petition:
            return
        # A band of displaced people stands in the same queue as a lawsuit,
        # because to the king it is the same queue.
        if any(c["id"] == petition for c in palace.petitioners(self.belief)):
            decision = (command.split(":", 1)[1] if command.startswith("receive:")
                        else next((d for key, d, _ in palace.RECEPTIONS
                                   if key == char), ""))
            if decision and self.do(A.ReceiveCohort(petition, decision),
                                    window="palace"):
                self.palace_state["pick"].pop(listing, None)
            return
        heard = next((p["heard"] for p in
                      self.belief.get("justice", {}).get("petitions", [])
                      if p["id"] == petition), False)
        if char == registry.BY_ID["hear_petition"].mnemonic \
                or wanted == "hear_petition":
            if heard:
                self.notify("you have already heard him.", registry.REFUSAL,
                            window="palace")
                self.repaint()
                return
            self.do(A.HearPetition(petition), window="palace")
            return
        verdict = ""
        if command.startswith("verdict:"):
            verdict = command.split(":", 1)[1]
        else:
            verdict = next((v for key, v, _label in palace.VERDICTS
                            if key == char), "")
        if not verdict:
            return
        if not heard:
            self.notify("hear him before you rule.", registry.REFUSAL,
                        window="palace")
            self.repaint()
            return
        if self.do(A.RulePetition(petition, verdict), window="palace"):
            self.palace_state["pick"].pop(listing, None)

    def palace_house(self, command: str, char: str) -> None:
        state = self.palace_state
        person_id = self.palace_pick(self.palace_listing())
        person = next((p for p in palace._people(self.belief)
                       if p["id"] == person_id), None)
        wanted = command.split(":", 1)[1] if command.startswith("do:") else ""
        if command == "choose-post" or char == \
                registry.BY_ID["place_person"].mnemonic:
            if person is None:
                self.notify("choose a man first.", registry.REFUSAL,
                            window="palace")
            else:
                state["choosing"] = "post"
                state["person"] = person["id"]
                state["scroll"] = 0
            self.repaint()
            return
        if person is None:
            return
        if char == registry.BY_ID["dismiss_person"].mnemonic \
                or wanted == "dismiss_person":
            if not person.get("post"):
                self.notify(f"{person['name']} holds no post.",
                            registry.REFUSAL, window="palace")
                self.repaint()
                return
            self.do(A.DismissPerson(person["post"]), window="palace")
        elif char == registry.BY_ID["name_heir"].mnemonic \
                or wanted == "name_heir":
            self.do(A.NameHeir(person["id"]), window="palace")
        elif command == "letter-marriage" or char == "m":
            court = self.palace_pick("relations") or next(
                (r["other"] for r in self.belief.get("relations", [])), "")
            if not court:
                self.notify("no foreign court is in correspondence.",
                            registry.REFUSAL, window="palace")
                self.repaint()
                return
            relation = next(
                (item for item in self.belief.get("relations", [])
                 if item["other"] == court), None)
            if relation is None:
                return
            self.open_new_letter(
                court, relation["place"], "marriage_proposal")
            self.desk["term_builder"]["person_id"] = person["id"]

    def palace_place(self, command: str, keysym: str, char: str) -> None:
        """The second half of appointing: a post for the man already chosen."""
        state = self.palace_state
        if command == "cancel":
            state["choosing"] = ""
            self.repaint()
            return
        if command != "place" and keysym != "Return":
            return
        post = self.palace_pick("post")
        if not post:
            self.notify("choose a post.", registry.REFUSAL, window="palace")
            self.repaint()
            return
        if self.do(A.PlacePerson(state["person"], post), window="palace"):
            state["choosing"] = ""

    def palace_relations(self, command: str, char: str) -> None:
        other = self.palace_pick("relations")
        if command == "letter-gift" or char.lower() == "g":
            relation = next(
                (item for item in self.belief.get("relations", [])
                 if item["other"] == other), None)
            if relation is None:
                self.notify("choose a court.", registry.REFUSAL,
                            window="palace")
                self.repaint()
                return
            self.open_new_letter(other, relation["place"], "gift")
        elif command == "letter-marriage" or char.lower() == "m":
            person = self.palace_pick("house") or next(
                (p["id"] for p in palace._people(self.belief)), "")
            if not person or not other:
                self.notify("choose a court, and someone to send.",
                            registry.REFUSAL, window="palace")
                self.repaint()
                return
            relation = next(
                (item for item in self.belief.get("relations", [])
                 if item["other"] == other), None)
            if relation is None:
                return
            self.open_new_letter(
                other, relation["place"], "marriage_proposal")
            self.desk["term_builder"]["person_id"] = person

    def on_world_key(self, event) -> None:
        """Move about the stable chart and read its place and route tablets.

        The map and the tablet beside it share one chosen place. Roads on the
        chart are deliberately not hit targets; their written rows are, so
        choosing a place never depends on which sparse line occupied a cell.
        """
        if event.keysym == "Escape":
            self.app.close("world")
            return
        command = getattr(event, "command", "")
        places = [str(place.get("id", ""))
                  for place in worldmap.places_in_order(self.belief)]
        all_routes = getattr(self, "world_all_routes", False)
        routes = worldmap.tablet_routes(
            self.belief, self.world_place_pick, all_routes)
        route_page = worldmap.route_page_size(
            self.belief, self.world_place_pick, self._size("world")[1])
        if self.world_place_pick not in places:
            self.world_place_pick = places[0] if places else ""
        here = places.index(self.world_place_pick) if places else 0
        char = (event.char or "").lower()

        if event.keysym == "Return":
            item = next((p for p in worldmap.places_in_order(self.belief)
                         if p.get("id") == self.world_place_pick), None)
            if item:
                self.open_focus("place", item)
            return

        if command.startswith("world:letter:"):
            _world, _letter, recipient, preset = command.split(":", 3)
            self.open_new_letter(
                recipient, self.world_place_pick,
                "" if preset == "letter" else preset)
            return
        if char in {"w", "g", "m"}:
            recipient = worldmap.court_at(
                self.belief, self.world_place_pick)
            preset = {
                "w": "", "g": "gift", "m": "marriage_proposal",
            }[char]
            self.open_new_letter(
                recipient, self.world_place_pick, preset)
            return
        if command.startswith("world:open:"):
            self.open_door_for(command.split(":", 2)[2])
            return
        if command == "world:sickness" or char == "p":
            self.open_plague()
            return
        if command == "world:routes:scope" or (
                char == "a"):
            self.world_all_routes = not all_routes
            self.world_route_scroll = 0
        elif command.startswith("world:route:"):
            _prefix, _kind, a, z = command.split(":", 3)
            item = next((route for route in routes
                         if {str(route.get("a")), str(route.get("b"))} == {a, z}), None)
            if item:
                self.open_focus("route", item)
                return
        elif command.startswith("world:place:"):
            picked = command.split(":", 2)[2]
            if picked == "next" or picked == "previous":
                step = 1 if picked == "next" else -1
                self.world_place_pick = places[(here + step) % len(places)] \
                    if places else ""
            elif picked in places:
                self.world_place_pick = picked
        elif event.keysym in {"Up", "Down"} and not (getattr(event, "state", 0) & 1):
            if places:
                step = -1 if event.keysym == "Up" else 1
                self.world_place_pick = places[(here + step) % len(places)]
                self.world_focus = None
        elif command.startswith("world:pan:") or event.keysym in (
                "Left", "Right") or (
                getattr(event, "state", 0) & 1 and event.keysym in {"Up", "Down"}):
            # The arrows move the window over the map. They are the only way to
            # look at ground nobody has a court on, which on a map this size is
            # most of it.
            way = (command.split(":", 2)[2] if command.startswith("world:pan:")
                   else {"Up": "north", "Down": "south",
                         "Left": "west", "Right": "east"}[event.keysym])
            across, down = {"north": (0, -1), "south": (0, 1),
                            "west": (-1, 0), "east": (1, 0)}.get(way, (0, 0))
            width, height = self._size("world")
            self.world_focus = worldmap.pan_focus(
                self.belief, width, height, self.world_place_pick,
                self.world_wide, self.world_focus, across, down)
        elif (event.char or "") in ("]", "[") and places:
            step = 1 if event.char == "]" else -1
            self.world_place_pick = places[(here + step) % len(places)]
            self.world_focus = None
        elif command == "world:routes:previous" or (
                getattr(event, "state", 0) & 4
                and event.keysym.lower() == "u"):
            self.world_route_scroll = max(
                0, self.world_route_scroll - route_page)
        elif command == "world:routes:next" or (
                getattr(event, "state", 0) & 4
                and event.keysym.lower() == "d"):
            self.world_route_scroll = min(
                max(0, len(routes) - route_page),
                self.world_route_scroll + route_page)
        elif command.startswith("world:layer:") or event.keysym in {"Tab", "ISO_Left_Tab"}:
            asked = (command.split(":", 2)[2]
                     if command.startswith("world:layer:") else "next")
            if asked in worldmap.LAYERS:
                self.world_layer = asked
            else:
                here = worldmap.LAYERS.index(self.world_layer)
                step = -1 if event.keysym == "ISO_Left_Tab" or getattr(event, "state", 0) & 1 else 1
                self.world_layer = worldmap.LAYERS[
                    (here + step) % len(worldmap.LAYERS)]
        elif command == "world:zoom:in" or (event.char or "") in ("+", "="):
            self.world_wide = max(1, self.world_wide - 1)
        elif command == "world:zoom:out" or (event.char or "") in ("-", "_"):
            self.world_wide = min(atlas.MAX_WIDE, self.world_wide + 1)
        else:
            return
        if command.startswith(("world:place:", "world:route:")):
            # A new place is a new list of roads, and a new place to look at.
            self.world_route_scroll = 0
            self.world_all_routes = False
            self.world_focus = None
        self.repaint()

    def open_door_for(self, room: str) -> None:
        """Open the window that takes an order this one only lists."""
        if room in {"roll", "land"}:
            self.storehouse_view = room
            self.open_ledger("t")
            return
        if room == "archive":
            self.inbox_filter = "records"
            self.open_tablet("s")
            return
        if room == "orders":
            self.open_orders()
            return
        if room == "counsel":
            self.open_counsel()
            return
        if room == "oaths":
            self.open_oaths()
            return
        if room == "plague":
            self.open_plague()
            return
        for char, (key, _title, _handler) in {
                **LEDGERS, **ROOMS, **TABLETS}.items():
            if key == room:
                self.open_door(char)
                return
        self.notify(f"There is no {room} to open.",
                    registry.REFUSAL, window="world")
        self.repaint()

    def on_trade_key(self, event) -> None:
        if event.keysym == "Escape":
            self.app.close("trade")
            return
        char = (event.char or "").lower()
        views = trade_page.VIEWS
        view = getattr(self, "trade_view", views[0])
        command = getattr(event, "command", "")
        if command.startswith("trade:open:"):
            _trade, _open, kind, number = command.split(":", 3)
            source = {"cargo": self.belief.get("trade", {}).get("cargo", ()),
                      "movements": self.belief.get("trade", {}).get("movements", ()),
                      "routes": self.belief.get("trade", {}).get("routes", ())}.get(kind, ())
            index = int(number)
            if index < len(source):
                self.trade_pick = str(source[index].get("id") or f"{kind}:{index}")
                self.open_focus("cargo" if kind == "cargo" else kind.rstrip("s"), source[index])
            return
        if command.startswith("tab:"):
            self.trade_view = command.split(":", 1)[1]
            self.trade_pick = ""
            self.trade_scroll = 0
            self.repaint()
            return
        if event.keysym in {"Tab", "ISO_Left_Tab"}:
            step = -1 if event.keysym == "ISO_Left_Tab" or getattr(event, "state", 0) & 1 else 1
            self.trade_view = views[(views.index(view) + step) % len(views)]
            self.trade_pick = ""
            self.trade_scroll = 0
            self.repaint()
            return
        if char.isdigit() and 1 <= int(char) <= len(views):
            self.trade_view = views[int(char) - 1]
            self.trade_pick = ""
            self.trade_scroll = 0
            self.repaint()
            return
        source = {"cargo": self.belief.get("trade", {}).get("cargo", ()),
                  "movements": self.belief.get("trade", {}).get("movements", ()),
                  "routes": self.belief.get("trade", {}).get("routes", ())}.get(view, ())
        ids = [str(item.get("id") or f"{view}:{index}")
               for index, item in enumerate(source)]
        if ids:
            if getattr(self, "trade_pick", "") not in ids:
                self.trade_pick = ids[0]
            page_size = max(1, self._size("trade")[1] - 10)
            self.trade_scroll = max(0, min(
                getattr(self, "trade_scroll", 0),
                max(0, len(ids) - page_size)))
        else:
            self.trade_pick = ""
            self.trade_scroll = 0
        if (event.keysym in {"Up", "Down"} or command == "trade:next") and ids:
            forward = event.keysym != "Up"
            here = ids.index(self.trade_pick)
            step = 1 if forward else -1
            index = collection.step(len(ids), here, step)
            self.trade_pick = ids[index]
            if index < self.trade_scroll:
                self.trade_scroll = index
            elif index >= self.trade_scroll + page_size:
                self.trade_scroll = index - page_size + 1
            self.repaint()
            return
        if event.keysym == "Return" and ids:
            picked = getattr(self, "trade_pick", "")
            here = ids.index(picked) if picked in ids else 0
            self.open_focus(view.rstrip("s"), source[here])
            return
        if view in {"exchange", "cargo"} and char in {"f", "r"}:
            self.command_line = {"f": "finance ", "r": "requisition ",
                                 }[char]
            self.open_palette()
        elif view in {"exchange", "cargo"} and char == "e":
            self.do(A.ExemptTrade(), window="trade")
        elif view == "dues" and char in {"<", ">"}:
            self._draft_due("harbour", -25 if char == "<" else 25)
        elif view == "dues" and event.keysym == "Return":
            self._commit_due("harbour", "trade")
        elif view == "movements" and char == "g":
            self.command_line = "assign "
            self.open_palette()
        elif view in {"movements", "routes"} and char == "c":
            self.command_line = "quarantine "
            self.open_palette()
        elif view == "dues" and char in {"a", "o", "p"}:
            relation = next(iter(self.belief.get("relations", ())), None)
            if relation:
                self.open_new_letter(relation["other"], relation["place"],
                                     {"a": "trade_authorization", "o": "trade_offer",
                                      "p": "trade_protection"}[char])

    def on_plague_key(self, event) -> None:
        """Navigate every known place and issue or lift a physical closure."""
        if event.keysym == "Escape":
            self.app.close("plague")
            return
        dossiers = plague_page.place_dossiers(self.belief)
        places = [item["id"] for item in dossiers]
        if not places:
            return
        try:
            index = places.index(self.plague_pick)
        except ValueError:
            index = 0
        command = getattr(event, "command", "")
        if command.startswith("plague:select:"):
            picked = command.split(":", 2)[2]
            if picked in places:
                index = places.index(picked)
        elif command == "plague:previous" or event.keysym == "Up":
            index = max(0, index - 1)
        elif command == "plague:next" or event.keysym == "Down":
            index = min(len(places) - 1, index + 1)
        elif event.keysym == "Prior":
            index = max(0, index - plague_page.page_size(28))
        elif event.keysym == "Next":
            index = min(
                len(places) - 1, index + plague_page.page_size(28))
        else:
            index = places.index(self.plague_pick) \
                if self.plague_pick in places else 0
        char = (event.char or "").lower()
        self.plague_pick = places[index]
        self.plague_scroll = plague_page.reveal_scroll(
            len(places), index, getattr(self, "plague_scroll", 0),
            plague_page.page_size(28))
        if command.startswith("plague:") or event.keysym in {
                "Up", "Down", "Prior", "Next"}:
            self.plague_notice = ""
            self.repaint()
            return
        if char == "q" and self.plague_pick:
            closed = set(self.belief.get("plague", {}).get("quarantined", []))
            self.do(A.Quarantine(
                self.plague_pick, lift=self.plague_pick in closed),
                window="plague")
            self.repaint()

    def search_archive(self, window: str = "archive") -> None:
        """One hour per query (spec 6.17), and the hour is the mechanic."""
        query = self.archive_query.strip().lower()
        if not query or not self.do(A.SearchArchive(query), window=window):
            self.repaint()
            return
        hits = self.belief.get("archive_index", {}).get("hits", {}).get(query, [])
        self.archive_hits = hits
        self.archive_pick = str(hits[0].get("ref", "")) if hits else ""
        self.archive_generation = self.__dict__.get(
            "archive_generation", 0) + 1
        generation = self.archive_generation
        turn = self.world.date.absolute
        if len(hits) < librarian.MIN_HITS:
            self.archive_summary = librarian.fallback_summary(query, hits)
            self.archive_summary_source = "index"
            self.repaint()
            return
        self.archive_summary = "The keeper is collating the returned tablets…"
        self.archive_summary_source = "pending"
        self.repaint()

        def work():
            return librarian.summarize(
                query, hits, self.seed, turn, self.client)

        def done(result, error) -> None:
            if (
                self.archive_query.strip().lower() != query
                or self.__dict__.get("archive_generation") != generation
            ):
                return
            if error is not None or result is None:
                self.archive_summary = librarian.fallback_summary(query, hits)
                self.archive_summary_source = "recovery"
                self.notify(
                    "The keeper could not finish his collation; the exact "
                    "finding list remains.",
                    registry.REFUSAL, window=window)
            else:
                self.archive_summary, self.archive_summary_source = result
                if self.archive_summary_source != "model":
                    self.notify(
                        "The keeper could not finish his collation; the exact "
                        "finding list remains.",
                        registry.REFUSAL, window=window)
            self.repaint()

        if self.client is None:
            done(work(), None)
        else:
            self._run_model(work, done)

    # --- keys ----------------------------------------------------------------

    def on_inbox_key(self, event) -> None:
        # Drafting is a station in this room, not another window. Once the wet
        # tablet is on the table, every key belongs to it until it is sealed or
        # laid aside.
        if getattr(self, "desk", None) is not None:
            self.on_desk_key(event)
            return
        command = getattr(event, "command", "")
        if command.startswith("focus:"):
            wanted = command.split(":", 1)[1]
            if wanted == "toggle":
                self.inbox_pane = (
                    "clay"
                    if getattr(self, "inbox_pane", "rack") == "rack"
                    else "rack")
            elif wanted in {"rack", "clay"}:
                self.inbox_pane = wanted
            self.repaint()
            return

        def choose_view(chosen: str) -> None:
            self.inbox_filter = chosen
            self.inbox_scroll = 0
            self.inbox_body_scroll = 0
            self.inbox_pane = "rack"
            self.archive_open_ref = ""
            if chosen != "records":
                items = inbox_page.ordered_items(
                    self.belief, self.stack_order, chosen)
                self.inbox_pick = items[0]["id"] if items else ""
            self.repaint()

        if command.startswith("view:"):
            chosen = command.split(":", 1)[1]
            if chosen in {"next", "previous"}:
                stations = [key for key, _label in inbox_page.VIEWS]
                here = stations.index(self.inbox_filter) if self.inbox_filter in stations else 0
                chosen = stations[(here + (1 if chosen == "next" else -1)) % len(stations)]
            if chosen in {"all", "archived", "outbox", "records"}:
                choose_view(chosen)
            return

        char = (event.char or "").lower()
        views = {
            "1": "all", "2": "archived", "3": "outbox",
            "4": "records",
            # Old muscle memory remains harmless while the visible contract is
            # the four numbered stations.
            "u": "all", "a": "all", "v": "archived", "o": "outbox"}
        archive_typing = (
            self.inbox_filter == "records"
            and getattr(self, "archive_typing", False))
        if not archive_typing and char in views:
            choose_view(views[char])
            return
        if not archive_typing and event.keysym in {
                "Tab", "ISO_Left_Tab", "Left", "Right"}:
            stations = [key for key, _label in inbox_page.VIEWS]
            here = stations.index(self.inbox_filter) if self.inbox_filter in stations else 0
            step = -1 if event.keysym in {"ISO_Left_Tab", "Left"} or getattr(event, "state", 0) & 1 else 1
            choose_view(stations[(here + step) % len(stations)])
            return
        if self.inbox_filter == "records":
            self.on_archive_key(event, embedded=True)
            return
        if event.keysym == "Escape":
            self.app.close("stack")
            return
        self.inbox_notice = ""
        if command.startswith("select:"):
            self.inbox_pick = command.split(":", 1)[1]
            self.inbox_body_scroll = 0
            self.inbox_pane = "rack"
            self.repaint()
            return

        b = self._language_belief(self.belief)
        inbound = (
            inbox_page.ordered_items(b, self.stack_order, "all")
            + inbox_page.ordered_items(b, self.stack_order, "archived"))
        outbox = inbox_page.ordered_items(b, self.stack_order, "outbox")
        selectable = outbox if self.inbox_filter == "outbox" else inbound
        selected_item = next(
            (item for item in selectable if item["id"] == self.inbox_pick),
            selectable[0] if selectable else None)

        if command.startswith("reply:"):
            letter_id = command.split(":", 1)[1]
            item = next(
                (candidate for candidate in inbound
                 if candidate["id"] == letter_id),
                None)
            if (item is not None and item["read"]
                    and item.get("answered_turn") is None):
                self.open_desk(letter_id)
            return
        if command.startswith("compare:"):
            letter_id = command.split(":", 1)[1]
            item = next(
                (candidate for candidate in inbound
                 if candidate["id"] == letter_id),
                None)
            if item is not None and item["read"]:
                self.open_letter(item)
            return
        if command.startswith(("archive:", "restore:")):
            mode, letter_id = command.split(":", 1)
            item = next(
                (candidate for candidate in inbound
                 if candidate["id"] == letter_id),
                None)
            if item is not None and item["read"]:
                archived = mode == "archive"
                if self.do(A.ArchiveLetter(letter_id, archived), window="stack"):
                    self.stack_order = document.order_of(
                        self.belief, self.stack_order)
                    self.inbox_filter = "archived" if archived else "all"
                    self.inbox_pick = letter_id
                    self.inbox_scroll = 0
                    self.repaint()
            return
        if command.startswith("delegate:"):
            _, letter_id, person_id = command.split(":", 2)
            item = next(
                (candidate for candidate in inbound
                 if candidate["id"] == letter_id),
                None)
            if item is not None and item["read"]:
                self.do(
                    A.DelegateLetter(letter_id, person_id), window="stack")
            return

        if event.keysym == "space":
            self.inbox_pane = (
                "clay"
                if getattr(self, "inbox_pane", "rack") == "rack"
                else "rack")
            self.repaint()
            return

        items = inbox_page.ordered_items(
            self.belief, self.stack_order, self.inbox_filter)
        if (char == "r" and selected_item is not None
                and self.inbox_filter != "outbox"
                and selected_item["read"]):
            if selected_item.get("answered_turn") is None:
                self.open_desk(selected_item["id"])
            return
        if (char in {"p", "c"} and selected_item is not None
                and self.inbox_filter != "outbox"
                and selected_item["read"]):
            self.open_letter(selected_item)
            return
        if (char in {"g", "d"} and selected_item is not None
                and self.inbox_filter != "outbox"
                and selected_item["read"] and self.inbox_delegate_pick):
            self.do(A.DelegateLetter(
                selected_item["id"], self.inbox_delegate_pick),
                window="stack")
            return
        if (char == "x" and selected_item is not None
                and self.inbox_filter != "outbox"
                and selected_item["read"]):
            archived = not bool(selected_item.get("archived"))
            if self.do(A.ArchiveLetter(selected_item["id"], archived), window="stack"):
                self.stack_order = document.order_of(
                    self.belief, self.stack_order)
                self.inbox_filter = "archived" if archived else "all"
                self.inbox_pick = selected_item["id"]
                self.inbox_scroll = 0
                self.repaint()
            return
        if not items:
            return
        current_index = next(
            (i for i, item in enumerate(items)
             if item["id"] == self.inbox_pick),
            None)
        navigation = {
            "nav:up": "Up",
            "nav:down": "Down",
        }.get(command, event.keysym)
        if navigation in {"Up", "Down"} and getattr(
                self, "inbox_pane", "rack") == "clay":
            self.inbox_body_scroll = max(
                0, self.inbox_body_scroll
                + (-1 if navigation == "Up" else 1))
            self.repaint()
            return
        if navigation in {"Up", "Down"}:
            if current_index is None:
                # The just-read tablet has left the Unread filter.  The first
                # navigation key moves to the first remaining row rather than
                # skipping it because the vanished row had no list index.
                index = 0
            else:
                index = max(
                    0, min(
                        len(items) - 1,
                        current_index
                        + (-1 if navigation == "Up" else 1)))
            self.inbox_pick = items[index]["id"]
            self.inbox_body_scroll = 0
            room = max(1, (self._size("stack")[1] - 10) // 2)
            if index < self.inbox_scroll:
                self.inbox_scroll = index
            elif index >= self.inbox_scroll + room:
                self.inbox_scroll = index - room + 1
            self.repaint()
            return
        if event.keysym == "Return":
            if self.inbox_filter == "outbox":
                return
            item = (
                selected_item if selected_item is not None
                and selected_item["id"] == self.inbox_pick
                else items[current_index or 0])
            self.inbox_pick = item["id"]
            if not item["read"]:
                self.do(A.ReadLetter(item["id"]), window="stack")
                self.inbox_pane = "clay"
            else:
                self.repaint()

    def activate_concern(self, index: int) -> None:
        """Open the evidence or put Yabninu's suggested order on his tablet."""
        matters = advice.concerns(self.belief)
        if not 0 <= index < len(matters):
            return
        concern = matters[index]
        if concern.destination == "counsel":
            self.counsel_typed = concern.order_prompt
            self.counsel_typing = bool(concern.order_prompt)
            self.open_counsel()
            return
        if concern.destination == "oaths":
            self.open_oaths()
            return
        if concern.destination == "plague":
            self.open_plague()
            return
        if concern.destination == "orders":
            self.open_orders()
            return
        if concern.destination in {"roll", "land"}:
            self.storehouse_view = concern.destination
            self.open_ledger("t")
            return
        if concern.destination == "archive":
            self.inbox_filter = "records"
            self.open_tablet("s")
            return
        door = next((key for key, _label, target in hall.DOORS
                     if target == concern.destination), "")
        if door in TABLETS:
            self.open_tablet(door)
        elif door in LEDGERS:
            self.open_ledger(door)
        elif door in ROOMS:
            self.open_room(door)

    def on_key(self, event) -> None:
        char = (event.char or "").lower()
        control = bool(getattr(event, "state", 0) & 4)
        if control and event.keysym.lower() == "s":
            self.save_current()
        elif control and event.keysym.lower() == "o":
            self.request_load()
        elif event.keysym == "space":
            self.end_fortnight()
        elif getattr(event, "command", "").startswith("concern:"):
            self.activate_concern(int(event.command.split(":", 1)[1]))
        elif char.isdigit() and char != "0":
            self.activate_concern(int(char) - 1)
        elif char == "?":
            self.open_help()
        elif char in TABLETS or char in LEDGERS or char in ROOMS:
            self.open_door(char)
        elif char in {"r", "l"}:
            # Old keys now move to a station in the one Storehouse.
            self.storehouse_view = "roll" if char == "r" else "land"
            self.open_ledger("t")
        elif char == "a":
            self.inbox_filter = "records"
            self.open_tablet("s")
        elif char == "d":
            # The desk without a letter chosen answers the oldest thing on the
            # pile, which is what a king with a stack in front of him does.
            read = [
                item for item in self.belief["stack"]
                if item["read"]
                and item.get("answered_turn") is None
            ]
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
        if event.keysym == "space":
            # Only the Hall owns the turn. A space typed while reading a
            # pinned tablet must never advance and autosave the kingdom.
            return
        if key.startswith("archive:") and event.keysym in {
                "Up", "Down", "Prior", "Next"}:
            step = {
                "Up": -1, "Down": 1, "Prior": -8, "Next": 8,
            }[event.keysym]
            self.archive_document_scroll[key] = max(
                0, self.archive_document_scroll.get(key, 0) + step)
            self.repaint()
            return
        char = (event.char or "").lower()
        if key.startswith("letter:") and char == "a":
            # Answer the tablet you are looking at. The desk opens beside it,
            # so the claim being answered stays on screen while it is answered.
            self.open_desk(key.split(":", 1)[1])
            return
        opens_next = (
            char in TABLETS or char in LEDGERS or char in ROOMS
            or char in {"r", "l", "a", "?"})
        if char == "d":
            opens_next = any(
                item["read"] and item.get("answered_turn") is None
                for item in self.belief["stack"])
        concern = getattr(event, "command", "")
        if concern.startswith("concern:"):
            index = int(concern.split(":", 1)[1])
            opens_next = 0 <= index < len(advice.concerns(self.belief))
        elif char.isdigit() and char != "0":
            opens_next = int(char) <= len(advice.concerns(self.belief))
        if key == "fortnight" and opens_next:
            # Opening the next station is acknowledgement enough. Keep the
            # report available until then, without demanding a dismissal key.
            self.app.close("fortnight")
        self.on_key(event)

    def quit(self) -> None:
        """The hall owns the session; every other window closes freely (D33)."""
        self.save_current(automatic=True)
        # Where the windows were is part of what the player set up, so it is
        # written before the loop ends rather than left to the next crash.
        self.save_settings()
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
    from ai.client import model_status, required_model_message

    if "--check" in argv:
        report(diagnose())
        ready, detail = model_status()
        print("  court model :", detail)
        return 0 if ready else 1
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
    ready, detail = model_status()
    if not ready:
        print(required_model_message(detail))
        return 1
    args = [a for a in argv[1:] if not a.startswith("-")]
    chosen_alu = args[0] if args else "seat"
    seed = int(args[1]) if len(args) > 1 else new_seed()
    print(f"seed {seed} — pass it back to play this same world again:\n"
          f"  ./run.sh {chosen_alu} {seed}")
    Game(chosen_alu, seed).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
