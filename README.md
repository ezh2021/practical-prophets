# Practical Prophets — Public Website & RSS

**Live:** https://ezh2021.github.io/practical-prophets/

**RSS:** https://ezh2021.github.io/practical-prophets/feed.xml

This is the **public deployment repository** for Practical Prophets. GitHub Pages serves branch `s052-9dc9bb`. The site currently presents Season 1, *Joshua*, in three episodes. All listeners see clean episode titles without production version numbers.

## Where work lives

- `~/Projects/practical-prophets/` on the Mac mini — **private canonical project home**. The manuscript, source Hebrew/JPS corpus, TTS raw audio/caches, and research belong here.
- `~/brain/projects/neviim-narrative/` — knowledge-base reference and compatibility symlinks to the private project; never a second production workspace.
- `~/platform/` — shared engineering monorepo. There is **not** yet a `platform/labs/practical-prophets` package. Reusable TTS components may be proposed later by normal reviewed PR.
- `ezh2021/practical-prophets` (this GitHub repository) — the **public** website, RSS, final MP3s, VTT transcripts, chapter JSON, cover art, release manifest, and the single standardized release tool.
- `~/work/tmp/practical-prophets/repo/` — an older local clone of the public deployment repository, **not** an independent source of truth. The current authoritative remote is GitHub; use a claimed worktree for edits.
- `ezh2021/practical-prophets-podcast` — an abandoned proposed name from an earlier experiment; it is **not** the live feed's repository. Do not publish to it.

## Release structure

```
index.html, style.css, player.js    Responsive website and playback/read-along
cover.png                           Podcast artwork
feed.xml                            Apple-compatible RSS (stable episode GUIDs)
versions.json                       Machine-readable history of exact audio revisions
episode-[1..3].html                 Stable deep-link redirects to the website
practical-prophets-s01e0*.mp3       Public finished episode audio
practical-prophets-s01e0*.vtt       Text tracks
practical-prophets-s01e0*.chapters.json    Timecoded chapter navigation
tools/podcast_release.py            ONE canonical static-site release CLI
tools/README.md                     Build, validation, visual audit and publish instructions
```

## Versioning without listener clutter

`versions.json` publishes exact SHA-256 checksums, source lineage and V1-to-V2 history. The RSS also includes namespaced `pp:audioVersion`, `pp:releaseRevision` and `pp:sha256` metadata (not listener-facing titles). Audio URLs have a `?rev=vN-<hash>` cache key. **Keep episode GUIDs unchanged** when correcting the same episode; do not rename Apple episode titles for production revisions.

An app that has **already downloaded** the V1 episode might retain its local cached file until the user removes that download. The RSS update prompts clients to fetch the revised enclosure but cannot force an Apple Podcasts device to delete an earlier offline download.

## Standard production/release process

Source-controlled **public** website code is edited in this repo. Narrative writing and Kokoro generation remain private on the Mac. The single entrypoint for publishing from this repo is:

```bash
uv run --with mutagen python tools/podcast_release.py stage --source ~/Projects/practical-prophets/release/site
uv run --with mutagen python tools/podcast_release.py build
uv run --with mutagen python tools/podcast_release.py validate
```

A **real-browser screenshot audit** (mobile 320/390, tablet 768 and desktop 1440) is required before publication. See `tools/README.md`. Changes are pushed from a claimed Git worktree only, never from an unrelated checkout or a second repository. Keep screenshots, release logs, credentials, original manuscripts and TTS experiments private.

The user has requested engaging, Jewish-context narrative nonfiction. Draft fidelity and Hebrew pronunciation reviews remain open; the existing three episodes are **working editions**, not a claim of completed scholarly certification.
