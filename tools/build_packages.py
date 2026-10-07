"""Build offline and Ollama downloads for the current OS and architecture."""
import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(edition):
    name = f"Say To The King - {edition.title()}"
    stage = ROOT / "build" / "packages" / edition
    dist = stage / "dist"
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
               "--windowed", "--onedir", "--name", name,
               "--python-option", "X utf8",
               "--paths", str(ROOT), "--paths", str(ROOT / "packaging"),
               "--add-data", f"{ROOT / 'content'}:content",
               "--hidden-import", "tkinter", "--hidden-import", "tkinter.messagebox",
               "--distpath", str(dist), "--workpath", str(stage / "work"),
               "--specpath", str(stage)]
    if sys.platform == "darwin":
        command += ["--osx-bundle-identifier", f"com.sttkml.game.{edition}"]
    command.append(str(ROOT / "packaging" / f"{edition}.py"))
    subprocess.run(command, cwd=ROOT, check=True)
    release = stage / "release"
    release.mkdir(parents=True, exist_ok=True)
    app = dist / (name + ".app" if sys.platform == "darwin" else name)
    destination = release / app.name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(app, destination, symlinks=True)
    model_note = ("No Python, Ollama or model download is needed.\n"
                  "Letters use authored text. Write letters normally; help and listed orders work offline.\n"
                  if edition == "offline" else
                  "Python is included. Install Ollama from https://ollama.com/download, then run:\n"
                  "ollama pull qwen3:4b-instruct\n"
                  "Start Ollama before opening the game. The model is not included.\n"
                  "If Ollama is unavailable, the app offers to play offline.\n")
    (release / "READ ME.txt").write_text(
        "SAY TO THE KING, MY LORD — playable alpha\n\n"
        + model_note + "\nOpen the application to play. Tab opens the Hall; Space there ends a fortnight.\n"
        "F3 shows your aims; ? opens help. Each court has its own autosave.\n\n"
        "This alpha has uneven campaign balance. Both editions use the same game and saves.\n"
        + ("These Apple Silicon builds use a macOS 26 runtime. They are ad-hoc signed, not notarized.\n"
           "If macOS blocks the download, review it in System Settings > Privacy & Security.\n"
           if sys.platform == "darwin" else
           "Windows: extract the whole ZIP, then open the .exe inside the game folder.\n"
           "Keep the _internal folder beside the executable.\n" if sys.platform == "win32" else
           "Linux: extract the archive and run ./Play.sh on a desktop system.\n"
           "Built on Ubuntu 22.04 (x86-64); glibc 2.35 or newer is required.\n"), encoding="utf-8")
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    filename = f"say-to-the-king-{edition}-{platform.system().lower()}-{platform.machine()}"
    archive = out / (filename + (".tar.gz" if sys.platform == "linux" else ".zip"))
    if sys.platform == "darwin":
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", str(release), str(archive)], check=True)
    elif sys.platform == "linux":
        launcher = release / "Play.sh"
        launcher.write_text(f'#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nexec "./{name}/{name}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
        shutil.make_archive(str(out / filename), "gztar", release)
    else:
        shutil.make_archive(str(out / filename), "zip", release)
    (out / (filename + ".sha256")).write_text(
        hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")
    print(f"Built {archive}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--edition', choices=('offline', 'ollama', 'both'), default='both')
    args = parser.parse_args()
    for edition in ('offline', 'ollama') if args.edition == 'both' else (args.edition,):
        build(edition)
