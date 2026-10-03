# Gameplan: PR #176 (`layermidi`) onto the mod platform

A working note for whoever picks this up on a machine with digikit, the
emulator and the stock 1.11 firmware. **It is not part of any PR.** Do not
merge or cherry-pick this file into `feat/layermidi` or
`chore/portable-emu-paths`.

- Upstream PR: https://github.com/angellinares/dn2_firmware_explore/pull/176
  (head `xrcstrecords:feat/layermidi`)
- Depends on #175 (`xrcstrecords:chore/portable-emu-paths`). That branch
  already holds the worktree fixes: `a531a08` (main checkout via git),
  `73b312d` (a Windows-git worktree read in WSL) and `3973be4` (its test on any
  host), on top of `df1ad4e`.

## What the maintainer asked for (angellinares, 2026-10-02)

1. **Move the code onto the platform**, as #174 did for `arpplocks`
   (commit `97f676a`):
   - the cave routines become one `CODE` chunk that the platform loader copies
     to RAM at start-up (`platform.split` / `platform.join`,
     `area.CodeChunk(va, blob).pack()`, `platform.extents(16 + len)`);
   - only the two hooks (`0x40026980`, `0x40026d32`) stay as edits in the image;
   - `extents()` includes the platform's;
   - implement `ram()`, and pass `test/test_mods_ramcheck.py` and
     `test/test_mods_platform.py`;
   - **`0x467D8000` is yours.** Declare it so the RAM check shows it free.
2. **Combine with `usbprobe`.** `dnfw mods matrix` must show
   `layermidi + usbprobe: yes`. Regenerate the matrix with the generator, in the
   docs and the site.
3. **Keep `midiarp` refused for now**, with the note. They fixed `midiarp`'s two
   problems separately (PR #179, now on upstream `main`) and will re-check the
   pair themselves.
4. **The gates every build passes**, with the results in the PR description:
   - `scripts/emu_boot_check.py` from reset ("booted and drew its UI"), for
     `layermidi` alone and for `layermidi + usbprobe`;
   - `scripts/emu_platform_check.py` (the loader layout);
   - `scripts/check_coldfire.py`;
   - integrity 21/21;
   - `scripts/emu_layer_midi.py` still showing all three chord notes;
   - the browser parity check.
5. **Rebase onto #175** once its worktree fix is in, so #176 carries only
   `layermidi`.

After that they build `layermidi + usbprobe` and test it on their instrument,
watching MIDI out.

## Templates to copy (all on upstream `main`)

`midiarp` is the closest match. It has hooks in the image plus one `CODE`
chunk, and moved off the same cave on 2026-10-03.

| what | template |
|---|---|
| Python mod | `src/dnfw/mods/midiarp.py`: `platform.split`, guards, edits, `CodeChunk`, `platform.join`, `ram()` |
| generator | `scripts/gen_midiarp_code.py`: `compose(..., code_base=CODE_VA)`, `"code": {"va", "blob"}` |
| build script | `scripts/build_arp_midi_play.py` `compose()`: `code_base` switches cave vs chunk; returns `blob` (4-padded) |
| browser mod | `site/js/mods/midiarp.js`: `platform.split`, `platform.join(edited, [...others, [platform.CODE, platform.codeChunk(CODE_VA, blob)]])` |
| emulator harness | `scripts/emu_midiarp_layered.py`: `emulib.code_chunks(section)` installs `CODE` chunks by hand, because a snapshot never runs the loader |
| tests | `test/test_midiarp_mod.py`: `OLD_CAVE` stays stock, disjoint-from-every-mod list |

## Step 0: branch setup

```sh
git remote add upstream https://github.com/angellinares/dn2_firmware_explore  # once
git fetch upstream main
git fetch origin feat/layermidi chore/portable-emu-paths claude/pr-comments-gameplan-wqgnha
```

`feat/layermidi` today is `8c40698` + `df1ad4e` (#175) + `a87b75b` (mod) +
`a057051` (site) + `431e88c` (docs) + `750d4dd` (merge of upstream `main`) +
`5ed2f8f` (bootscreen pair note). Rebuild it on current upstream `main` with
only the layermidi commits:

```sh
git checkout -B layermidi-platform upstream/main
# If #175 has merged upstream, skip this merge.
# If not, bring in #175 *with its worktree fix*.
git merge --no-ff origin/chore/portable-emu-paths   # head 3973be4 or later
git cherry-pick a87b75b a057051 431e88c 5ed2f8f
```

Expect conflicts in **generated** files: `docs/mods-compatibility.md`,
`site/index.html` (the matrix), `src/dnfw/cli/mods.py` (REGISTRY and matrix
footer), `src/dnfw/mods/matrix.py`, and the `site/*.html` nav. Resolve them by
taking upstream's version and regenerating in step 6. Do not hand-merge
generated tables. Keep the `REGISTRY` entry `layermidi_mod.ID: layermidi_mod`
and the `layermidi` import.

Before going on, check that the cherry-picked tree still passes
`pytest test/test_layermidi_mod.py` on the **old** cave design. That keeps
rebase damage apart from port damage.

## Step 1: `scripts/build_layer_midi.py`

1. `compose(stock, log=print, code_base: int | None = None)`, following
   `build_arp_midi_play.compose`:
   - `where = CAVE if code_base is None else code_base`;
   - when `code_base` is set, skip the "cave is free" check and **do not write
     into the cave**. The cave must stay stock;
   - `payload, at = assemble_stubs(SOURCE, where)`, then
     `blob = payload + bytes(-len(payload) % 4)`;
   - the hooks stay as they are: `4eb9`/`4ef9` + `be32(at[label])` are 6-byte
     absolute instructions, so only the target changes, to `0x467D80xx`;
   - return `{"content", "cave": (where, len(payload)), "code_base": code_base, "blob": blob}`.
2. Check that `SOURCE` has nothing position-dependent on the cave. The survey
   found only absolute references (`jmp {RELEASE_SITE+6:#x}`,
   `jsr {MIDI_RECORD:#x}`, RAM/IO absolutes) and no `bsr` out of the cave.
   Confirm with `dnfw disasm` on the built blob at `0x467D8000`.
3. Add `CODE_VA = 0x467D8000`. It is free: `midiarp` is `0x467d0000`–`0x467d0250`,
   and the platform's own limit sits below `0x467e0000`. Have `main()` build
   with `code_base=CODE_VA` and add the platform area the same way
   `build_arp_midi_play.main` does. Rename the output to `layer-midi7`:
   `OUT = ROOT / "00_Resources/02_Builds/layer-midi7_DN2_1.11.syx"`, plus
   `out/layer-midi7/`.
4. Run `scripts/check_coldfire.py` on the blob.

Optional, and worth raising in the PR rather than changing silently: upstream
`midiarp` now takes a MIDI record only while **four** are free, because the live
MIDI sender allocates without a check. `layermidi` uses two. Matching four is
cheap; say so if you do.

## Step 2: `scripts/gen_layermidi_code.py`

Mirror `gen_midiarp_code.py`:

- `built = lm.compose(stock, log=..., code_base=CODE_VA)`;
- the edits come from diffing stock against `built["content"]` and should be
  **exactly the two 6-byte hooks**. Drop the special "cave is one edit" branch.
  Assert `len(edits) == 2`;
- the JSON gains `"code": {"va": CODE_VA, "blob": built["blob"].hex(), "labels": labels}`
  (labels from `assemble_stubs(lm.SOURCE, CODE_VA)`). Keep `stock_length`,
  `edits` and `guards`, and keep `labels` at the top level too if the tests or
  JS read it there;
- the replay check: apply the edits to stock, then
  `platform.join(bytes(replay), [(platform.area.CODE, CodeChunk(CODE_VA, blob).pack())])`,
  and require it to equal what `dnfw.mods.layermidi.apply` produces. At minimum,
  the edited base must equal `built["content"]`;
- write with `newline="\n"` as midiarp does;
- regenerate `src/dnfw/mods/layermidi_code.json` and `site/js/mods/layermidi-code.js`.

## Step 3: `src/dnfw/mods/layermidi.py`

Same shape as `midiarp.py`:

```python
from . import RAM, Extent, ModError, Result, platform

CODE_VA = SPEC["code"]["va"]
BLOB = bytes.fromhex(SPEC["code"]["blob"])

def extents(firmware=None):
    return ([Extent(SECTION, e["va"] - BASE, len(e["new"]) // 2, e["what"]) for e in SPEC["edits"]]
            + platform.extents(16 + len(BLOB)))

def apply(firmware):
    ...
    original, others = platform.split(section.unpack())
    ... length check, guards, edit stock bytes (unchanged) ...
    content = bytearray(original); write the two hooks
    chunk = platform.area.CodeChunk(CODE_VA, BLOB).pack()
    content = platform.join(bytes(content), others + [(platform.area.CODE, chunk)])
    return Result(payloads={SECTION: content}, extents=extents(), notes=[...,
        f"2 hooks in section 3, and a {len(BLOB):,} B CODE chunk at 0x{CODE_VA:08x} in the platform's area"])

def ram():
    return [Extent(RAM, CODE_VA, len(BLOB), "the mod's code (a platform CODE chunk)")]
```

- Add `NOT_RAM = (...)` **only if** `test_mods_ramcheck` flags a constant that
  looks like RAM but is not. Name each one and say why, as `arpplocks` does.
- Rewrite the docstring: "Two hooks in the frame ISR, one platform `CODE` chunk
  at `0x467d8000`". Remove "uses midiarp's cave on purpose". The `midiarp`
  refusal is now about behaviour only (step 6).

## Step 4: `site/js/mods/layermidi.js`

Copy `midiarp.js`: `import * as platform from "./platform.js"`, then

- `extents()` appends `...platform.extents(16 + CODE.code.blob.length / 2)`;
- `apply()`: `const [original, others] = platform.split(unpacked)`, the guard
  and edit checks on `original`, `edited = original.slice()`, write the hooks,
  then `platform.join(edited, [...others, [platform.CODE, platform.codeChunk(CODE.code.va, hex(CODE.code.blob))]])`;
- update the notes to match the Python.

`site/js/app/layermidi-page.js` needs no change: it calls `apply` and `extents`
and then `replacement(firmware, 3, content)`.
`scripts/js_layermidi_check.mjs` must still report a byte-identical section 3
against `--py-content`.

## Step 5: tests (`test/test_layermidi_mod.py` and others)

- Remove the hard-coded `CAVE = 0x402D0664` and `test_the_cave_was_free`.
  Instead, add `OLD_CAVE = (0x402D0664, 324)` and assert it **stays stock** in
  the applied image, as `test_midiarp_mod.py` does.
- The hook test: the `jsr`/`jmp` targets equal `SPEC["code"]["labels"]` (or
  `SPEC["labels"]`), and they fall inside `[CODE_VA, CODE_VA + len(BLOB))`.
- `test_byte_disjoint_from_the_other_arp_and_fx_mods`: **flip `usbprobe`** from
  "not disjoint" to disjoint. Add `midiarp` to the disjoint list as well,
  because the bytes no longer collide; the refusal is now NOTES-only.
- `test_refuses_midiarp_and_says_why`: keep `check_compatible(...)` non-empty
  and the NOTES key. If it asserted that `apply` on midiarp's output **raises**,
  that relied on the shared cave and will no longer hold. Assert the refusal
  through `check_compatible` / `dnfw mods apply` instead.
- `test_is_the_build_that_passed`: point it at `out/layer-midi7/...`.
- `test/test_mods_platform.py` hard-codes `lfo4`, `lfowaves` and `bootscreen`.
  Add a `layermidi` case: it applies on a platform image, and on top of another
  platform mod (`usbprobe`, `arpplocks`), with the chunk landing where expected.
- `test/test_midiarp_mod.py:134`
  `test_declared_bytes_are_disjoint_from_every_other_mod` uses a hard-coded id
  list. Add `layermidi` if the maintainer would want it there.
- `test_mods_ramcheck` and `test_mods_list` iterate `REGISTRY`, so they pick
  `layermidi` up automatically.

Run `pytest -q`. Before starting, record the failures that already exist on
upstream `main`. On the #175 base these were `test_telemetry` ×2 and
`test_trace` ×1, which were unrelated.

## Step 6: compatibility matrix and docs

- `src/dnfw/mods/matrix.py` NOTES: keep `frozenset(("layermidi", "midiarp"))`
  and rewrite the reason. They no longer share a cave. What remains is
  behaviour: two mods turning layered copies on MIDI tracks into MIDI. Since
  #179, `midiarp` plays a layered copy only when its own track's arp is on and
  playing it, so the overlap is smaller than before; say it is kept refused at
  the maintainer's request until they re-check.
- Keep the `bootscreen + layermidi` note, but it was flashed with the **cave**
  build. Re-boot the pair from reset (below) and update its date and wording.
- Regenerate with `dnfw mods matrix`: `docs/mods-compatibility.md`, the
  `site/index.html` matrix and the `dnfw:combines` text. Confirm
  `layermidi + usbprobe: yes`.
- `docs/layer-midi.md` and `docs/mods.md`: "a cave" becomes "a platform `CODE`
  chunk at `0x467d8000`", and add `0x467d8000` to the RAM table where
  `docs/mods.md` (or the platform doc) keeps one.

## Step 7: emulator harness `scripts/emu_layer_midi.py`

It restores `ui1200M`, a snapshot taken after boot, so the platform loader
never runs and the `CODE` chunk would never reach `0x467d8000`. The hooks would
then jump into empty RAM. Install the chunks by hand as
`emu_midiarp_layered.py` does: `emulib.code_chunks(section)`, writing each one
to its load address (or `dnfw.mods.platform.runtime(content)` for the full
area). Then confirm **all three chord notes** still come out. Also run
`scripts/emu_layer_probe.py` if it reads the cave address.

## Step 8: the gates (run them all; paste the results into the PR description)

Build both images:

```sh
STOCK=00_Resources/00_Firmware/Digitone_II_OS1.11_dist.zip
dnfw mods apply $STOCK --mod layermidi                -o 00_Resources/02_Builds/layer-midi7_DN2_1.11.syx
dnfw mods apply $STOCK --mod layermidi --mod usbprobe -o 00_Resources/02_Builds/layer-midi7-usbprobe_DN2_1.11.syx
dnfw mods apply $STOCK --mod layermidi --mod bootscreen -o 00_Resources/02_Builds/layer-midi7-bootscreen_DN2_1.11.syx
dnfw inspect 00_Resources/02_Builds/layer-midi7-usbprobe_DN2_1.11.syx   # integrity fields
```

Also extract each build's `section_3_MAIN_OS.bin` into `out/<build>/` for the
emulator gates, either with `dnfw extract` or with `python scripts/build_layer_midi.py`
for the lone build. Then:

| gate | command | pass looks like |
|---|---|---|
| boot, alone | `scripts/emu_boot_check.py out/layer-midi7/section_3_MAIN_OS.bin` | "booted and drew its UI" from **reset**, not fault and not "no UI" |
| boot, with usbprobe | same on `out/layer-midi7-usbprobe/...` | same |
| boot, with bootscreen | same on a `layermidi bootscreen` build | same (the old hardware note was for the cave build) |
| loader layout | `scripts/emu_platform_check.py` on each build | the chunk at `0x467d8000`, no overlap |
| ColdFire encodings | `scripts/check_coldfire.py` | clean, no scale-8 index |
| integrity | `dnfw mods apply` / `dnfw inspect` output | 21/21 |
| behaviour | `scripts/emu_layer_midi.py out/layer-midi7` | all three chord notes as MIDI note-ons, then their note-offs |
| browser parity | `node scripts/js_layermidi_check.mjs ... --py-content ...` | byte-identical section 3 |
| unit tests | `pytest -q` | no new failures against upstream `main` |
| matrix | `dnfw mods matrix` | `layermidi + usbprobe: yes`; `layermidi + midiarp` refused with the note |

A snapshot harness passing is **not** a boot test. `emu_boot_check` from reset
is the only one that runs the loader and the first jump into the chunk.

## Step 9: the PR description, then push

Update #176's description:

- what moved (cave to `CODE` chunk at `0x467d8000`; hooks unchanged; the cave stays stock);
- the gate table above with real output;
- `layermidi + usbprobe: yes`; `midiarp` still refused, and why;
- the `bootscreen` pair re-booted;
- builds in `00_Resources/02_Builds/` and what a pass looks like on the instrument:
  - set an audio track's TRACK WILL TRIGGER to a MIDI track and play a chord;
  - every note should arrive on the MIDI track's channel at MIDI out, with no
    hanging notes on stop;
  - a failure looks like silence at MIDI out, stuck notes, or a fault screen
    `V.. M.. P........` at boot.

Then replace the PR's head branch. This rewrites `feat/layermidi` on the fork,
so **confirm with the owner first**:

```sh
git push --force-with-lease=feat/layermidi:5ed2f8f origin layermidi-platform:feat/layermidi
```

## #175 status

`chore/portable-emu-paths` is pushed, with head `3973be4`. The maintainer's
second round reported that WSL's git cannot follow a worktree made by Windows
git (a `D:/...` gitdir). `73b312d` reads the worktree's `.git` file and
`commondir` itself, and maps the drive to `/mnt/d/`. The maintainer confirmed
the boot gate passes from such a worktree. Their third round said the new test
failed on a Windows host; `3973be4` passes `windows=False` explicitly, and the
maintainer called it "ready to merge from our side" with that change. Nothing
more to push there unless the maintainer comments again. Do not push this gameplan commit there.

The worktree setup the maintainer uses: Windows git makes the worktrees,
and the harnesses run in WSL. If this machine is set up that way, run the
emulator gates from such a worktree. That exercises the fix for real.
