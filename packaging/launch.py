"""Shared entry point for the two downloadable editions."""
import json
import os
import sys
import traceback


def launch(edition):
    os.environ["STTKML_OFFLINE"] = "1" if edition == "offline" else "0"
    from paths import SAVES
    SAVES.parent.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout = open(SAVES.parent / f"{edition}.log", "a", buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout
    try:
        if "--package-info" in sys.argv:
            import tkinter
            from load import playable_courts, load_campaign
            from ai.client import create_client
            from engine.tick import advance
            from belief.project import project
            courts = playable_courts()
            opening, _ = advance(load_campaign("seat", 20261006))
            info = {"edition": edition, "tk": tkinter.Tcl().eval("info patchlevel"),
                    "courts": [c["id"] for c in courts], "turn": project(opening)["turn"],
                    "saves": str(SAVES), "frozen": bool(getattr(sys, "frozen", False))}
            info["utf8_mode"] = sys.flags.utf8_mode
            if edition == "offline":
                info["no_model_client"] = create_client() is None
            if "--package-ui-check" in sys.argv:
                os.environ["STTKML_OFFLINE"] = "1"
                from play_gui import Game
                game = Game("seat", 20261006, playtest=True)
                game.app.root().update_idletasks()
                info["ui_opened"] = bool(game.app.windows)
                game.app.stop()
            target = SAVES.parent / f"package-info-{edition}.json"
            target.write_text(json.dumps(info, indent=2) + "\n")
            print(json.dumps(info))
            return 0
        import play_gui
        if edition == "ollama" and "--check" not in sys.argv:
            from ai.client import model_status, required_model_message
            ready, detail = model_status()
            if not ready:
                from tkinter import messagebox
                from tui.backend_tk import _root
                if messagebox.askyesno("Ollama is not ready",
                        required_model_message(detail) + "\n\nPlay offline instead?", parent=_root()):
                    os.environ["STTKML_OFFLINE"] = "1"
                else:
                    return 1
        return play_gui.main(sys.argv)
    except Exception:
        traceback.print_exc()
        from tkinter import messagebox
        messagebox.showerror("The game could not start",
                             f"Details were saved in {SAVES.parent / (edition + '.log')}.")
        return 1
