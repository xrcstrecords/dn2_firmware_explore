"""Where this checkout, digikit, the firmware and the emulator's working files are.

Every harness used to carry one machine's absolute WSL paths --
`/mnt/d/01_Code/Z_Personal/...` and `/root/...` -- so it ran on that machine
and nowhere else. They are resolved here once, in the same order digikit's own
`emu/config.py` uses:

    1. the environment variable, if set
    2. the first default that exists
    3. the first default, so the error names a path rather than None

| variable | what | defaults, in order |
|---|---|---|
| `DIGIKIT` | the digikit clone | `digikit-up`, `digikit`, siblings of the main checkout |
| `DT2_SYX` | stock Digitone II 1.11 | `00_Resources/00_Firmware/Digitone_II_OS1.11_dist/...syx`, in this checkout, then the main one |
| `DT2_SECTIONS` | its extracted sections | `/root/dn2-sections-111`, `<digikit>/out/sections/dn2-1.11` |
| `DN2_SNAPSHOTS` | this project's snapshots | `/root/dn2-snapshots/Digitone_II_OS1.11`, `<digikit>/out/snapshots/dn2-1.11` |
| `SELMAP`, `SELAS` | selache's tools | `/root/<tool>-target/release/<tool>`, `tools/selmap/target/release/selmap` (this checkout, then the main one) |

The WSL paths stay as defaults so the original setup needs no configuration;
a sibling clone is what makes it work anywhere else.

**Worktrees.** The harnesses also run from git worktrees, one per branch, under
`.claude/worktrees/<name>/`. There `ROOT` is the worktree, but the sibling
clones sit next to the *main* checkout, and `00_Resources` (gitignored) and
built tools exist only there unless linked in. So siblings are looked for next
to `MAIN`, the main checkout, and anything untracked under the checkout in
`ROOT` first, then in `MAIN`. Outside a worktree `MAIN` is `ROOT`, and nothing
changes. A worktree made by Windows git and run from WSL has a `D:/...` path
in its `.git` file, which WSL's git cannot follow; `MAIN` is then read off
that file, with the drive mapped to `/mnt/d/...`. The full order for those: the variable, `ROOT`, `MAIN`, then the
first default.

Standard library only: these scripts run under digikit's venv, which has no
`dnfw`.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


WSL_MOUNT = pathlib.Path("/mnt")       # where WSL mounts Windows drives: D: is /mnt/d
WINDOWS = os.name == "nt"


def native(path: str, windows: bool = WINDOWS) -> pathlib.Path:
    """-> PATH as this system names it: a Windows drive path (`D:/...` or
    `D:\\...`) becomes `/mnt/d/...` off Windows, as WSL mounts it; anything
    else is unchanged."""
    if not windows and len(path) > 2 and path[0].isalpha() and path[1] == ":" and path[2] in "/\\":
        return WSL_MOUNT / path[0].lower() / path[3:].replace("\\", "/")
    return pathlib.Path(path)


def _parent_of_dot_git(common: pathlib.Path) -> pathlib.Path | None:
    # A submodule's common directory is `.git/modules/<name>`: not a checkout's.
    return common.parent if common.is_absolute() and common.name == ".git" else None


def _from_git(root: pathlib.Path) -> pathlib.Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    main = _parent_of_dot_git(pathlib.Path(out))
    return main.resolve() if main else None


def from_git_file(root: pathlib.Path, windows: bool = WINDOWS) -> pathlib.Path | None:
    """-> the main checkout, read off a worktree's `.git` file without git, or
    None. Its `gitdir:` line names the worktree's git directory, whose
    `commondir` file (normally `../..`) names the common one, relative to it.

    For a worktree made by Windows git and read in WSL: the `gitdir:` is a
    `D:/...` path, which WSL's git cannot follow (`not a git repository`).
    WINDOWS is whether drive paths are this host's own (see `native`)."""
    try:
        text = (root / ".git").read_text(encoding="utf-8")   # a directory: not a worktree
        gitdir = next(native(line[len("gitdir:"):].strip(), windows) for line in text.splitlines()
                      if line.startswith("gitdir:"))
        gitdir = gitdir if gitdir.is_absolute() else root / gitdir   # relative worktree links
        common = native((gitdir / "commondir").read_text(encoding="utf-8").strip(), windows)
    except (OSError, UnicodeDecodeError, StopIteration):
        return None
    main = _parent_of_dot_git(pathlib.Path(os.path.normpath(
        common if common.is_absolute() else gitdir / common)))
    return main.resolve() if main else None


def main_checkout(root: pathlib.Path, windows: bool = WINDOWS) -> pathlib.Path:
    """-> the main checkout ROOT belongs to: the parent of git's common
    directory, which is ROOT itself outside a worktree. Asked of git first;
    when git cannot answer (missing, too old for `--path-format`, or a
    worktree whose `.git` file another system's git wrote), read off the
    worktree's `.git` file; else ROOT, quietly."""
    return _from_git(root) or from_git_file(root, windows) or root


MAIN = main_checkout(ROOT)


def resolve(var: str, *defaults: pathlib.Path) -> pathlib.Path:
    """-> $VAR if set, else the first of DEFAULTS that exists, else the first."""
    if os.environ.get(var):
        return pathlib.Path(os.environ[var]).expanduser()
    return next((d for d in defaults if d.exists()), defaults[0])


def local(rel: str, root: pathlib.Path = ROOT, main: pathlib.Path = MAIN) -> list[pathlib.Path]:
    """-> where an untracked REL under the checkout may be: in ROOT, then in
    the main checkout (the same place outside a worktree)."""
    return [root / rel] + ([main / rel] if main != root else [])


DIGIKIT = resolve("DIGIKIT", MAIN.parent / "digikit-up", MAIN.parent / "digikit")
SYX = resolve("DT2_SYX",
              *local("00_Resources/00_Firmware/Digitone_II_OS1.11_dist/Digitone_II_OS1.11.syx"))
SECTIONS = resolve("DT2_SECTIONS", pathlib.Path("/root/dn2-sections-111"),
                   DIGIKIT / "out/sections/dn2-1.11")
SNAPSHOTS = resolve("DN2_SNAPSHOTS", pathlib.Path("/root/dn2-snapshots/Digitone_II_OS1.11"),
                    DIGIKIT / "out/snapshots/dn2-1.11")
SELMAP = resolve("SELMAP", pathlib.Path("/root/selmap-target/release/selmap"),
                 *local("tools/selmap/target/release/selmap"))
SELAS = resolve("SELAS", pathlib.Path("/root/selache-target/release/selas"))


def use_digikit(tools: bool = False) -> pathlib.Path:
    """Put digikit (and with TOOLS, its `tools/` ahead of it) on sys.path, and
    point digikit's own configuration at the 1.11 sections, before anything
    imports `emu`.

    digikit's `DT2_SECTIONS` default is `sections`, relative to the working
    directory -- which, run from this checkout, is a directory that does not
    exist, or worse, one holding another firmware's sections
    (`docs/emulator.md`, "a stale section cache"). An explicit setting wins.
    """
    for path in (DIGIKIT, DIGIKIT / "tools") if tools else (DIGIKIT,):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    os.environ.setdefault("DT2_SECTIONS", str(SECTIONS))
    return DIGIKIT
