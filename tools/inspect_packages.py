"""Load each native package and its opening windows before uploading it."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

for edition in ("offline", "ollama"):
    name = f"Say To The King - {edition.title()}"
    dist = ROOT / "build" / "packages" / edition / "dist"
    if sys.platform == "darwin":
        executable = dist / (name + ".app") / "Contents" / "MacOS" / name
    else:
        executable = dist / name / (name + (".exe" if sys.platform == "win32" else ""))
    directory = ROOT / "output" / f"package-{edition}"
    directory.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, STTKML_DATA_DIR=str(directory))
    subprocess.run([str(executable), "--package-info", "--package-ui-check"],
                   env=env, cwd=directory.parent, check=True, timeout=60)
    info = json.loads((directory / f"package-info-{edition}.json").read_text(encoding="utf-8"))
    if not (info["frozen"] and info["ui_opened"] and info["utf8_mode"]
            and len(info["courts"]) == 8 and info["turn"] == 1
            and (edition != "offline" or info["no_model_client"])):
        raise SystemExit(f"Incomplete package: {info}")
    print(json.dumps(info), flush=True)
