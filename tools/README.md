# Standardized release tooling

There is **one production release program:** `tools/podcast_release.py`. Old experimental scripts in the Mac project's `lab/archive/` and the earlier `operations/publish-site-owner.sh` are historical, **not** release entrypoints. In particular, the old owner shell script targets the obsolete `practical-prophets-podcast` repository name; **do not run it**.

## One consistent workflow

Use an **authorized, claimed Git worktree** of `ezh2021/practical-prophets` on the Pages source branch `s052-9dc9bb`. The code in this public repository is only release plumbing and does not need access to source books or private model data.

1. Render and approve the new audiobook chapter/episode in the private Mac project, including its matching transcript and chapter markers. Assign a new semantic `audio_version` only when the audio bytes change; retain the episode GUID.
2. Update `versions.json` with the version, exact SHA-256, audio duration, file size and revision history. It is the **sole release manifest**.
3. Stage the three approved files (MP3, VTT, chapter JSON) from the private `release/site` directory with `stage`, or place them explicitly into this public repo's claimed worktree.
4. Run `build` to update `feed.xml`, hidden HTML attributes and cache-keyed audio URLs from `versions.json`.
5. Run `validate`. The script checks the audio hash/length/duration (ffprobe or mutagen), stable GUIDs, chapter markers, captions, mobile CSS, and JavaScript syntax.
6. **Actually render and inspect screenshots** at 320, 390, 768 and 1440 CSS pixels before publishing. Record visual problems and corrections. A passing DOM assertion without reviewing screenshots does not satisfy this step.
7. Publish only from the approved Git worktree, after explicit review. Then run `verify-live` to check public RSS and streaming HTTP byte-ranges.

```bash
# Small, isolated dependency; ffprobe is used if installed.
uv run --with mutagen python tools/podcast_release.py stage \
  --source ~/Projects/practical-prophets/release/site

uv run --with mutagen python tools/podcast_release.py build
uv run --with mutagen python tools/podcast_release.py validate

# Attach to an already brokered/approved Brave CDP browser on a worker node.
# Do not install or launch an unrelated browser profile.
uv run --with mutagen python tools/podcast_release.py visual \
  --cdp "$BROWSER_LANE_PORT" \
  --url http://127.0.0.1:18643/ \
  --output /tmp/practical-prophets-visual-review

# After inspecting every screenshot, set
# human_or_vision_reviewer_approved=true in visual-audit.json.
uv run --with mutagen python tools/podcast_release.py publish \
  --visual-report /tmp/practical-prophets-visual-review/visual-audit.json \
  --approve-public-release

uv run --with mutagen python tools/podcast_release.py verify-live
```

The deploy command refuses a missing screenshot review, incorrect branch, incorrect GitHub remote, bad checksum, broken feed or missing transcript. It never creates new repositories. RSS cache-query changes help Apple Podcasts discover new enclosures, but an already downloaded offline episode may still need to be deleted and downloaded again.

## Visual checklist

At each width: visually inspect the **actual PNG**, not just source code; verify the podcast cover is square and never elongated; all nav links are visible and tappable; readable hero text; episode cards don't overflow; audio player and transcript don't overlap; transcript text is readable; controls work; no unintended clipping or missing imagery. Test a real transcript opening and speed change. Record screenshots in the private project's QA folder, not on the public website.

## Future improvements

- Prefer a machine-readable `story/commentary/language` segment manifest from the private audiobook builder.
- Add Hebrew-capable TTS for named terms rather than uncontrolled English transliteration.
- Keep the public CSS/HTML/JS in this single source repository; don't copy working versions into Brain or Platform without a reviewed change.
- Consider a future reviewed `platform/labs` package for generally reusable TTS/phoneme/audio tools, without project-specific private data.
