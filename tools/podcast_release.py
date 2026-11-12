#!/usr/bin/env python3
"""Practical Prophets: single source-of-truth release, QA and deployment tool.

The public repository contains *only* public site source, podcast assets and
the code necessary to reproduce their release. The private manuscript, TTS
caches, Hebrew research and review notes remain on the Mac.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "versions.json"
FEED_FILE = ROOT / "feed.xml"
INDEX_FILE = ROOT / "index.html"
NS_ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
NS_PP = "urn:practical-prophets:release:1"
ET.register_namespace("itunes", NS_ITUNES)
ET.register_namespace("podcast", "https://podcastindex.org/namespace/1.0")
ET.register_namespace("pp", NS_PP)
PUBLIC_REPO = "ezh2021/practical-prophets"
PUBLIC_BRANCH = "s052-9dc9bb"
BASE_URL = "https://ezh2021.github.io/practical-prophets/"
DEFAULT_PRIVATE_STAGE = Path.home() / "Projects/practical-prophets/release/site"


def die(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def run(*args: str, cwd: Path | None = None) -> str:
    process = subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)
    return process.stdout.strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def episodes(manifest: dict) -> list[dict]:
    es = manifest["episodes"]
    if not es or len({int(e["episode"]) for e in es}) != len(es):
        die("episode identifiers are absent or not unique")
    return sorted(es, key=lambda e: int(e["episode"]))


def load() -> dict:
    m = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    if m.get("release_revision") is None or m.get("show") != "Practical Prophets":
        die("versions.json is missing required release metadata")
    return m


def mp3_info(path: Path) -> tuple[float, int]:
    if not path.is_file():
        die(f"missing audio: {path}")
    if shutil.which("ffprobe"):
        obj = json.loads(run("ffprobe", "-v", "error", "-show_entries",
                             "format=duration,size", "-of", "json", str(path)))
        return float(obj["format"]["duration"]), int(obj["format"]["size"])
    # Small, pure-Python fallback for worker nodes without ffmpeg tooling.
    try:
        from mutagen.mp3 import MP3
    except ImportError:
        die("Install mutagen with 'uv run --with mutagen python tools/podcast_release.py validate'")
    return float(MP3(path).info.length), path.stat().st_size


def cache_url(e: dict) -> str:
    u = urlsplit(e["enclosure_url"])
    if urlsplit(BASE_URL).netloc != u.netloc:
        die("enclosure host does not match the approved public site")
    return urlunsplit((u.scheme, u.netloc, u.path,
                       f"rev=v{e['audio_version'].split('.')[0]}-{e['sha256'][:12]}", ""))


def verify_source_hash(e: dict, p: Path) -> None:
    actual = sha256(p)
    if actual != e["sha256"]:
        die(f"{p.name} SHA differs from versions.json; revise version manifest explicitly before release")


def stage(source: Path) -> None:
    """Copy exactly the three approved finished MP3/VTT/chapter artifacts."""
    m = load()
    for e in episodes(m):
        n = int(e["episode"])
        for ext in ("mp3", "vtt", "chapters.json"):
            old = source / f"joshua-part-{n}.{ext}"
            new = ROOT / (e["filename"].removesuffix(".mp3") + "." + ext)
            if not old.is_file() or old.is_symlink():
                die(f"source artifact missing or symlinked: {old}")
            if ext == "mp3":
                verify_source_hash(e, old)
            if not new.exists() or sha256(old) != sha256(new):
                shutil.copy2(old, new)
                print("STAGED", new.relative_to(ROOT))
    print("Staging complete; run 'build', 'validate' and visual audit before publishing.")


def build() -> None:
    """Derive hidden audio version stamps, cache-busted URLs and byte lengths."""
    manifest = load()
    tree = ET.parse(FEED_FILE)
    channel = tree.getroot().find("channel")
    if channel is None:
        die("invalid feed: channel missing")
    items = channel.findall("item")
    if len(items) != len(episodes(manifest)):
        die("RSS episode count differs from version manifest")
    by_guid = {item.findtext("guid"): item for item in items}
    stamp = f"{{{NS_PP}}}versionManifest"
    existing = channel.find(stamp)
    if existing is None:
        existing = ET.Element(stamp)
        channel.insert(0, existing)
    existing.text = BASE_URL + "versions.json"
    html = INDEX_FILE.read_text(encoding="utf-8")
    for e in episodes(manifest):
        item = by_guid.get(e["guid"])
        if item is None:
            die(f"missing stable GUID: {e['guid']}")
        dest = ROOT / e["filename"]
        verify_source_hash(e, dest)
        duration, size = mp3_info(dest)
        if abs(duration - float(e["duration_seconds"])) > 0.20:
            die(f"duration mismatch for {dest.name}: {duration}s")
        enc = item.find("enclosure")
        if enc is None:
            die("missing enclosure")
        enc.set("url", cache_url(e))
        enc.set("length", str(size))
        enc.set("type", "audio/mpeg")
        d = item.find(f"{{{NS_ITUNES}}}duration")
        if d is None:
            d = ET.SubElement(item, f"{{{NS_ITUNES}}}duration")
        d.text = str(round(duration))
        for key, value in [
            ("audioVersion", e["audio_version"]),
            ("releaseRevision", manifest["release_revision"]),
            ("sha256", e["sha256"]),
        ]:
            el = item.find(f"{{{NS_PP}}}{key}")
            if el is None:
                el = ET.SubElement(item, f"{{{NS_PP}}}{key}")
            el.text = value
        stem = e["filename"].removesuffix(".mp3")
        bare_url = stem + ".mp3"
        new_url = bare_url + "?rev=v" + e["audio_version"].split(".")[0] + "-" + e["sha256"][:12]
        pattern = re.compile(re.escape(bare_url) + r"(?:\?rev=[^\"']*)?")
        if not pattern.search(html):
            die(f"missing episode audio reference in HTML: {stem}")
        html = pattern.sub(new_url, html)
        article = re.compile(r'(<article[^>]+data-episode="' + str(e["episode"]) + r'"[^>]*)(>)')
        def attr(m):
            tag = re.sub(r'\s+data-audio-(?:version|sha256)="[^"]*"', "", m.group(1))
            return tag + f' data-audio-version="{e["audio_version"]}" data-audio-sha256="{e["sha256"][:12]}"' + m.group(2)
        html, count = article.subn(attr, html, count=1)
        if count != 1:
            die(f"episode {e['episode']} article marker missing")
    if "practical-prophets:release-revision" in html:
        html = re.sub(r'(<meta name="practical-prophets:release-revision" content=")[^"]+(")',
                      lambda m: m.group(1) + manifest["release_revision"] + m.group(2), html)
    else:
        html = html.replace("</head>", f'<meta name="practical-prophets:release-revision" content="{manifest["release_revision"]}">\n</head>')
    INDEX_FILE.write_text(html, encoding="utf-8")
    tree.write(FEED_FILE, encoding="utf-8", xml_declaration=True)
    print("BUILT", manifest["release_revision"], len(items), "episodes")


def validate() -> None:
    manifest = load()
    tree = ET.parse(FEED_FILE)
    channel = tree.getroot().find("channel")
    items = channel.findall("item")
    es = episodes(manifest)
    if len(items) != len(es):
        die("feed episode count mismatch")
    guids = [item.findtext("guid") for item in items]
    if len(set(guids)) != len(guids) or set(guids) != {e["guid"] for e in es}:
        die("feed GUIDs not stable/unique")
    html = INDEX_FILE.read_text(encoding="utf-8")
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    js = (ROOT / "player.js").read_text(encoding="utf-8")
    if '@media(max-width:440px)' not in css or "height:auto;aspect-ratio:1/1" not in css:
        die("required mobile layout and image sizing missing")
    if 'name="viewport"' not in html or html.count('<article class="episode"') != len(es):
        die("site episode cards / viewport mismatch")
    if "playbackRate" not in js or "timeupdate" not in js:
        die("interactive player script incomplete")
    for e in es:
        n = int(e["episode"])
        dest = ROOT / e["filename"]
        verify_source_hash(e, dest)
        duration, size = mp3_info(dest)
        if not 1800 <= duration <= 2700:
            die(f"duration outside 30-45min tolerance: episode {n}")
        if abs(duration - e["duration_seconds"]) > 0.20:
            die("declared duration mismatches audio")
        item = next(item for item in items if item.findtext("guid") == e["guid"])
        enc = item.find("enclosure")
        if int(enc.get("length")) != size or enc.get("url") != cache_url(e):
            die(f"enclosure length/URL invalid for episode {n}")
        stem = e["filename"].removesuffix(".mp3")
        vtt = ROOT / (stem + ".vtt")
        chapter = ROOT / (stem + ".chapters.json")
        raw = vtt.read_text(encoding="utf-8")
        if not raw.startswith("WEBVTT") or raw.count("-->") < 10:
            die(f"invalid/missing transcript for episode {n}")
        data = json.loads(chapter.read_text(encoding="utf-8"))
        starts = [c["startTime"] for c in data["chapters"]]
        if not starts or starts != sorted(starts) or starts[-1] >= duration:
            die(f"invalid chapter markers for episode {n}")
        if n > 1 and not data["chapters"][0]["title"].startswith("Previously"):
            die(f"episode {n} missing recap")
        if f'data-audio-sha256="{e["sha256"][:12]}"' not in html:
            die("hidden HTML version metadata missing")
        print(f"VALID episode {n}: {duration/60:.2f}m; sha {e['sha256'][:16]}; {len(starts)} chapters")
    run("node", "--check", str(ROOT / "player.js"))
    print("VALID: public release package consistent. Visual screenshot audit still required.")


def audit_visual(port: int, url: str, dest: Path) -> None:
    """Capture real Chromium screenshots via an *existing approved* CDP session.

    This does not install or start browsers. The caller must acquire the approved
    computer-use broker lease first. Human/vision review of PNGs is mandatory.
    """
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    env = __import__("os").environ.copy()
    env.setdefault("AGENT_BROWSER_SESSION", "practical-prophets-visual-qa")
    def browser(*args: str) -> str:
        cmd = ["agent-browser", "--cdp", str(port), *args]
        p = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if p.returncode:
            die("browser QA failed: " + p.stderr.strip())
        return p.stdout.strip()
    browser("open", url)
    for w, h in ((320, 700), (390, 844), (768, 1024), (1440, 900)):
        browser("set", "viewport", str(w), str(h))
        filename = dest / f"practical-prophets-{w}x{h}.png"
        browser("screenshot", str(filename), "--full")
        js = """JSON.stringify((()=>{const im=document.querySelector('.cover'),nav=[...document.querySelectorAll('nav a')],cards=[...document.querySelectorAll('.episode')];return {viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,image:{width:im.getBoundingClientRect().width,height:im.getBoundingClientRect().height,naturalWidth:im.naturalWidth,naturalHeight:im.naturalHeight},nav:nav.map(n=>({title:n.textContent,width:n.getBoundingClientRect().width,height:n.getBoundingClientRect().height})),cards:cards.length}})())"""
        output = browser("eval", js).strip()
        # agent-browser may print a JSON-stringified JSON object.
        metrics = json.loads(output)
        if isinstance(metrics, str):
            metrics = json.loads(metrics)
        if metrics["scrollWidth"] > w + 1:
            die(f"horizontal mobile overflow at {w}px")
        if metrics["image"]["naturalWidth"] == 0 or abs(metrics["image"]["width"] - metrics["image"]["height"]) > 3:
            die(f"cover image broken or distorted at {w}px")
        if metrics["cards"] != len(episodes(load())):
            die(f"episode cards missing at {w}px")
        if any(x["height"] < 40 for x in metrics["nav"]):
            die(f"navigation touch targets too small at {w}px")
        results.append({"width":w,"height":h,"screenshot":str(filename),
                        "screenshot_sha256":sha256(filename),"metrics":metrics})
        print(f"SCREENSHOT {w}x{h}: {filename.name}; image {metrics['image']['width']:.0f}x{metrics['image']['height']:.0f}; scroll {metrics['scrollWidth']}")
    (dest / "visual-audit.json").write_text(json.dumps({"audited_at":datetime.now(timezone.utc).isoformat(),"url":url,"results":results,"human_or_vision_reviewer_approved":False},indent=2)+"\n",encoding="utf-8")
    print("Captured real browser screenshots. Review all PNGs before marking visual audit approved.")


def verify_live() -> None:
    manifest = load()
    req = urllib.request.Request(BASE_URL + "feed.xml",headers={"Cache-Control":"no-cache"})
    with urllib.request.urlopen(req, timeout=20) as res:
        root = ET.fromstring(res.read())
        if res.status != 200: die("feed HTTP failure")
    by_guid = {x.findtext("guid"): x for x in root.find("channel").findall("item")}
    for e in episodes(manifest):
        item = by_guid.get(e["guid"])
        if item is None: die("episode missing from live RSS")
        enclosure = item.find("enclosure")
        if enclosure.get("url") != cache_url(e): die("live episode enclosure is stale")
        with urllib.request.urlopen(urllib.request.Request(enclosure.get("url"),method="HEAD"),timeout=25) as r:
            if r.status != 200 or int(r.headers["Content-Length"]) != e["bytes"]:
                die("public MP3 size differs from manifest")
        with urllib.request.urlopen(urllib.request.Request(enclosure.get("url"),headers={"Range":"bytes=0-1023"}),timeout=25) as r:
            if r.status != 206: die("HTTP byte-range playback not supported")
        print("LIVE", e["episode"], "HTTP 200; range 206")
    with urllib.request.urlopen(BASE_URL+"versions.json",timeout=20) as r:
        v=json.load(r)
        if v["release_revision"] != manifest["release_revision"]:
            die("public versions.json is stale")
    print("LIVE VERIFIED", BASE_URL)


def publish(visual_report: Path, *, approved: bool = False) -> None:
    """Push an already reviewed release to the existing GitHub Pages branch.

    This intentionally never creates a repository, rewrites history, or stages
    arbitrary files. A visual review is mandatory before deployment.
    """
    if not approved:
        die("explicit --approve-public-release is required")
    report = json.loads(visual_report.read_text(encoding="utf-8"))
    if not report.get("human_or_vision_reviewer_approved"):
        die("the screenshot report has not been reviewed/approved")
    screenshots = report.get("results", [])
    if {int(x["width"]) for x in screenshots} != {320, 390, 768, 1440}:
        die("expected mobile, tablet and desktop screenshots")
    for x in screenshots:
        p = Path(x["screenshot"])
        if not p.exists() or sha256(p) != x["screenshot_sha256"]:
            die("missing or modified audited screenshot")
    validate()
    branch = run("git", "branch", "--show-current", cwd=ROOT)
    if branch != PUBLIC_BRANCH:
        die(f"must deploy from claimed {PUBLIC_BRANCH} worktree, got {branch}")
    origin = run("git", "remote", "get-url", "origin", cwd=ROOT)
    if not origin.endswith("/" + PUBLIC_REPO + ".git") and not origin.endswith(":" + PUBLIC_REPO + ".git"):
        die("wrong GitHub origin")
    allow = [".gitignore","README.md","index.html","style.css","player.js","feed.xml","versions.json",
             "episode-1.html","episode-2.html","episode-3.html","cover.png",
             "tools/podcast_release.py","tools/README.md","tools/test_release.py"]
    for e in episodes(load()):
        stem = e["filename"].removesuffix(".mp3")
        allow.extend([stem + ".mp3", stem + ".vtt", stem + ".chapters.json"])
    run("git", "add", "--", *allow, cwd=ROOT)
    if run("git", "diff", "--cached", "--name-only", cwd=ROOT).strip() == "":
        print("No changed files to publish.")
        return
    run("git", "diff", "--cached", "--check", cwd=ROOT)
    run("git", "-c", "user.name=Practical Prophets", "-c",
        "user.email=practical-prophets@users.noreply.github.com",
        "commit", "-m", "Publish verified podcast release " + load()["release_revision"], cwd=ROOT)
    run("git", "push", "origin", "HEAD:refs/heads/" + PUBLIC_BRANCH, cwd=ROOT)
    print("PUSHED. Run 'verify-live' after GitHub Pages reports build complete.")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    s=ap.add_subparsers(dest="command",required=True)
    s.add_parser("build")
    s.add_parser("validate")
    stage_p=s.add_parser("stage")
    stage_p.add_argument("--source",type=Path,default=DEFAULT_PRIVATE_STAGE)
    visual_p=s.add_parser("visual")
    visual_p.add_argument("--cdp",type=int,required=True)
    visual_p.add_argument("--url",default=BASE_URL)
    visual_p.add_argument("--output",type=Path,required=True)
    s.add_parser("verify-live")
    publish_p=s.add_parser("publish")
    publish_p.add_argument("--visual-report",type=Path,required=True)
    publish_p.add_argument("--approve-public-release",action="store_true")
    args=ap.parse_args()
    {"build":build,"validate":validate,"verify-live":verify_live}.get(args.command,lambda:None)()
    if args.command=="stage":stage(args.source)
    if args.command=="visual":audit_visual(args.cdp,args.url,args.output)
    if args.command=="publish":publish(args.visual_report,approved=args.approve_public_release)

if __name__=="__main__":
    main()
