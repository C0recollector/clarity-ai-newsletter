from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
VENDOR = ROOT / ".vendor"
sys.path.insert(0, str(SCRIPT_DIR))
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from fetch_youtube_playlist_transcripts import (  # noqa: E402
    fetch_feed,
    fetch_playlist_page,
    fetch_transcript,
    parse_date,
    parse_feed,
    parse_playlist_page,
    write_markdown,
)
from generate_issue_pages import generate as generate_issue_pages  # noqa: E402
from youtube_transcript_api import YouTubeTranscriptApi  # noqa: E402


SOURCE_CONFIG = ROOT / "data" / "source_config.json"
ISSUE_DIR = ROOT / "data" / "issues"
YOUTUBE_DIR = ROOT / "data" / "youtube"
NEWSLETTER_DIR = ROOT / "data" / "newsletters"
CANDIDATE_DIR = ROOT / "data" / "candidates"
TRANSCRIPT_BLOCK_ERRORS = {"IpBlocked", "RequestBlocked", "TooManyRequests"}


def load_local_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_source_config() -> dict:
    with SOURCE_CONFIG.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_source_config(config: dict) -> None:
    SOURCE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_issue_id(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        raise ValueError("Issue id must use YYYY-MM-DD format.")
    return value


def build_brief(issue_model: dict) -> dict:
    issue_id = safe_issue_id(issue_model.get("issue", {}).get("id", ""))
    ISSUE_DIR.mkdir(parents=True, exist_ok=True)
    issue_path = ISSUE_DIR / f"{issue_id}.json"
    issue_path.write_text(json.dumps(issue_model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    results = generate_issue_pages(issue_path)
    return {
        "ok": True,
        "message": "Newsletter generated from approved review.",
        "issue": str(issue_path.relative_to(ROOT)),
        "pages": [
            {
                "path": str(path.relative_to(ROOT)),
                "changed": changed,
                "url": "/" + str(path.relative_to(ROOT)).replace("\\", "/"),
            }
            for path, changed in results
        ],
    }


def issue_path(issue_id: str) -> Path:
    return ISSUE_DIR / f"{safe_issue_id(issue_id)}.json"


def load_issue(issue_id: str) -> dict:
    path = issue_path(issue_id)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def candidate_pool_path(issue_id: str) -> Path:
    return CANDIDATE_DIR / f"candidate-pool-{safe_issue_id(issue_id)}.json"


def load_candidate_pool(issue_id: str) -> dict:
    path = candidate_pool_path(issue_id)
    if not path.exists():
        return {
            "ok": False,
            "message": "Candidate pool has not been built yet.",
            "json": str(path.relative_to(ROOT)),
            "candidates": [],
            "summary": {"candidate_count": 0},
        }
    with path.open("r", encoding="utf-8") as file:
        pool = json.load(file)
    candidates = enrich_pool_candidates(pool.get("candidates", []), issue_id)
    since_date = pool.get("request", {}).get("since_date")
    if since_date:
        since = parse_iso_date(since_date)
        if since:
            candidates = [
                candidate for candidate in candidates
                if not candidate.get("date") or parse_iso_date(candidate.get("date")) is None or parse_iso_date(candidate.get("date")) >= since
            ]
    return {
        "ok": True,
        "json": str(path.relative_to(ROOT)),
        "built_at": pool.get("built_at"),
        "request": pool.get("request", {}),
        "summary": {
            **pool.get("summary", {}),
            "candidate_count": len(candidates),
            "filtered_since_date": since_date,
        },
        "candidates": candidates,
    }


def issue_blocks(issue: dict) -> list[dict]:
    blocks = [
        {
            "id": "issue.title",
            "label": "Issue title",
            "kind": "title",
            "value": issue.get("issue", {}).get("title", ""),
        },
        {
            "id": "issue.dek",
            "label": "Issue intro",
            "kind": "summary",
            "value": issue.get("issue", {}).get("dek", ""),
        },
    ]
    for section in sorted(issue.get("sections", []), key=lambda item: item.get("order", 999)):
        title = section.get("title", section.get("id", "Section"))
        blocks.extend(
            [
                {
                    "id": f"section.{section['id']}.title",
                    "label": f"{title} - title",
                    "kind": "title",
                    "value": section.get("title", ""),
                },
                {
                    "id": f"section.{section['id']}.headline",
                    "label": f"{title} - headline",
                    "kind": "headline",
                    "value": section.get("headline", ""),
                },
                {
                    "id": f"section.{section['id']}.summary",
                    "label": f"{title} - summary",
                    "kind": "summary",
                    "value": section.get("summary", ""),
                },
            ]
        )
    return blocks


def find_issue_block(issue: dict, block_id: str) -> dict:
    for block in issue_blocks(issue):
        if block["id"] == block_id:
            return block
    raise ValueError(f"Unknown issue block: {block_id}")


def set_issue_block(issue: dict, block_id: str, value: str) -> dict:
    value = value.strip()
    if block_id == "issue.title":
        issue["issue"]["title"] = value
        return issue
    if block_id == "issue.dek":
        issue["issue"]["dek"] = value
        return issue
    match = re.fullmatch(r"section\.([a-z0-9-]+)\.(title|headline|summary)", block_id)
    if not match:
        raise ValueError(f"Unsupported block id: {block_id}")
    section_id, field = match.groups()
    for section in issue.get("sections", []):
        if section.get("id") == section_id:
            section[field] = value
            if field == "title":
                section["headline"] = value
            return issue
    raise ValueError(f"Section not found: {section_id}")


def rewrite_prompt(block: dict, instruction: str, issue: dict) -> str:
    return (
        "Rewrite one block of an AI newsletter.\n\n"
        f"Issue title: {issue.get('issue', {}).get('title', '')}\n"
        f"Block: {block['label']}\n"
        f"Block kind: {block['kind']}\n\n"
        "Current text:\n"
        f"{block['value']}\n\n"
        "User instruction:\n"
        f"{instruction}\n\n"
        "Return only the replacement text. Do not add quotes, labels, markdown fences, or commentary."
    )


def codex_request_type(instruction: str) -> str:
    if re.search(r"\b(image|graphic|infographic|illustration|visual|chart|diagram|regenerate)\b", instruction, re.I):
        return "visual_or_image_request"
    return "text_rewrite_request"


def queue_codex_request(block: dict, instruction: str, prompt: str, issue_id: str) -> tuple[str, str, str]:
    output_dir = ROOT / "data" / "rewrite_requests"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{issue_id}-{block['id'].replace('.', '-')}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.md"
    request_type = codex_request_type(instruction)
    path.write_text(
        "\n".join(
            [
                "---",
                f"status: pending",
                f"request_type: {request_type}",
                f"issue_id: {issue_id}",
                f"block_id: {block['id']}",
                f"block_label: {block['label']}",
                f"block_kind: {block['kind']}",
                f"created_at: {utc_now()}",
                "---",
                "",
                "# Codex Newsletter Request",
                "",
                "## Current text",
                "",
                block["value"],
                "",
                "## Instruction",
                "",
                instruction,
                "",
                "## Prompt for Codex",
                "",
                prompt,
                "",
                "## Codex handling",
                "",
                "- Read this request from the local repo.",
                "- If this is a text request, update the selected issue block and rebuild the newsletter.",
                "- If this is a visual/image request, create or regenerate the appropriate asset and wire it into the issue/page.",
            ]
        ),
        encoding="utf-8",
    )
    return "", "queued_for_codex", str(path.relative_to(ROOT))


def rewrite_block(request: dict) -> dict:
    issue_id = safe_issue_id(request.get("issue_id", "2026-05-11"))
    block_id = request.get("block_id", "")
    instruction = request.get("instruction", "").strip()
    if not instruction:
        raise ValueError("Rewrite instruction is required.")
    issue = load_issue(issue_id)
    block = find_issue_block(issue, block_id)
    prompt = rewrite_prompt(block, instruction, issue)
    draft, mode, request_file = queue_codex_request(block, instruction, prompt, issue_id)
    return {
        "ok": True,
        "mode": mode,
        "block": block,
        "draft": draft,
        "prompt": prompt,
        "request_file": request_file,
        "note": "Queued for Codex. Ask Codex to process the pending rewrite or visual request.",
    }


def apply_block(request: dict) -> dict:
    issue_id = safe_issue_id(request.get("issue_id", "2026-05-11"))
    block_id = request.get("block_id", "")
    value = request.get("value", "")
    issue = load_issue(issue_id)
    set_issue_block(issue, block_id, value)
    result = build_brief(issue)
    updated_issue = load_issue(issue_id)
    return {
        **result,
        "issue_model": updated_issue,
        "blocks": issue_blocks(updated_issue),
        "message": "Rewrite applied and newsletter rebuilt.",
    }


def publish_newsletter(request: dict) -> dict:
    issue_id = safe_issue_id(request.get("issue_id", "2026-05-11"))
    return {
        "ok": True,
        "message": "Cloudflare publishes from GitHub after the newsletter files are committed and pushed.",
        "mode": "cloudflare_git",
        "issue_id": issue_id,
        "public_url": "https://clarity-ai-newsletter.gregboss.workers.dev/",
        "issue_url": f"https://clarity-ai-newsletter.gregboss.workers.dev/{issue_id}/",
        "next_step": "Ask Codex to commit and push the newsletter changes to GitHub; Cloudflare will deploy the pushed commit automatically.",
    }


def source_name(source: str | dict) -> str:
    if isinstance(source, dict):
        return source.get("name") or source.get("label") or source.get("url") or "Unnamed source"
    return str(source)


def source_url(source: str | dict) -> str:
    return source.get("url", "") if isinstance(source, dict) else ""


def is_youtube_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    host = host.lower().removeprefix("www.")
    return host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")


def source_items(value: object) -> list[str | dict]:
    return value if isinstance(value, list) else []


def parse_iso_date(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(f"{value}T00:00:00+00:00")


def recent_entries(entries: list[dict], since_date: str) -> list[dict]:
    since = parse_iso_date(since_date)
    if not since:
        return entries
    kept = []
    for entry in entries:
        published = parse_date(entry.get("published", ""))
        updated = parse_date(entry.get("updated", ""))
        newest = max([item for item in (published, updated) if item], default=None)
        if newest and newest >= since:
            kept.append(entry)
    return kept


def relative_age_to_days(value: str) -> float | None:
    match = re.search(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", value or "", re.I)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    multipliers = {
        "second": 1 / 86400,
        "minute": 1 / 1440,
        "hour": 1 / 24,
        "day": 1,
        "week": 7,
        "month": 30,
        "year": 365,
    }
    return amount * multipliers[unit]


def recent_entries_from_published_age(entries: list[dict], lookback_days: int) -> list[dict]:
    kept = []
    for entry in entries:
        age_days = relative_age_to_days(entry.get("video_info", ""))
        entry["published_age_days"] = age_days
        if age_days is not None and age_days <= lookback_days:
            kept.append(entry)
    return kept


def apply_playlist_basis_filter(entries: list[dict], request: dict, used_page_fallback: bool) -> tuple[list[dict], str]:
    basis = request.get("playlist_basis", "published_newest")
    lookback_days = int(request.get("lookback_days") or 7)
    if not used_page_fallback:
        return recent_entries(entries, request.get("since_date", "")), "rss_date_filter"
    if basis.startswith("published_"):
        filtered = recent_entries_from_published_age(entries, lookback_days)
        if basis == "published_oldest":
            filtered.reverse()
        return filtered, "playlist_page_published_age_filter"
    if basis == "added_oldest":
        return list(reversed(entries)), "playlist_page_order_only_no_added_dates"
    return entries, "playlist_page_order_only_no_added_dates"


def skipped_transcript(error_type: str, message: str) -> dict:
    return {
        "status": "error",
        "error_type": error_type,
        "error": message,
        "retry_later": True,
    }


def transcript_is_blocked(transcript: dict) -> bool:
    return transcript.get("error_type") in TRANSCRIPT_BLOCK_ERRORS


def fetch_transcripts_safely(entries: list[dict], request: dict, output_dir: Path) -> tuple[list[dict], dict]:
    transcript_cache = load_transcript_cache(output_dir)
    api = YouTubeTranscriptApi()
    attempts = 0
    skipped = 0
    blocked = False
    max_attempts = int(request.get("max_transcript_attempts", 8))
    delay_seconds = float(request.get("transcript_delay_seconds", 1.5))
    videos = []

    for entry in entries:
        cached_transcript = transcript_cache.get(entry["video_id"])
        if cached_transcript:
            entry["transcript"] = cached_transcript
            entry["transcript_cached"] = True
            entry["transcript_attempted"] = False
        elif blocked:
            entry["transcript"] = skipped_transcript(
                "SkippedAfterIpBlocked",
                "Skipped because YouTube blocked transcript requests earlier in this run.",
            )
            entry["transcript_cached"] = False
            entry["transcript_attempted"] = False
            skipped += 1
        elif attempts >= max_attempts:
            entry["transcript"] = skipped_transcript(
                "SkippedMaxAttempts",
                f"Skipped because this run reached the transcript attempt limit of {max_attempts}.",
            )
            entry["transcript_cached"] = False
            entry["transcript_attempted"] = False
            skipped += 1
        else:
            if attempts:
                time.sleep(delay_seconds)
            entry["transcript"] = fetch_transcript(api, entry["video_id"])
            entry["transcript_cached"] = False
            entry["transcript_attempted"] = True
            attempts += 1
            if transcript_is_blocked(entry["transcript"]):
                blocked = True
        videos.append(entry)

    return videos, {
        "transcript_attempt_limit": max_attempts,
        "transcript_attempts": attempts,
        "transcripts_skipped": skipped,
        "transcript_blocked": blocked,
    }


def refresh_youtube_playlist(request: dict) -> dict:
    config = load_source_config()
    playlist_id = config["youtube"]["curated_playlist"]["playlist_id"]
    output_dir = YOUTUBE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    used_page_fallback = False
    try:
        playlist, entries = parse_feed(fetch_feed(playlist_id))
    except HTTPError as exc:
        if exc.code == 404:
            playlist, entries = parse_playlist_page(fetch_playlist_page(playlist_id), playlist_id)
            used_page_fallback = True
        else:
            raise
    entries, filter_mode = apply_playlist_basis_filter(entries, request, used_page_fallback)

    for entry in entries:
        entry["priority"] = "editorial_override"
        entry["source_lane"] = "youtube_playlist"
    videos, transcript_summary = fetch_transcripts_safely(entries, request, output_dir)

    issue_date = request.get("issue_date") or datetime.now(timezone.utc).date().isoformat()
    report = {
        "fetched_at": utc_now(),
        "request": request,
        "playlist": playlist,
        "videos": videos,
        "summary": {
            "video_count": len(videos),
            "videos_found": len(entries),
            "transcripts_cached": sum(1 for video in videos if video.get("transcript_cached")),
            "transcripts_fetched": sum(1 for video in videos if video.get("transcript_attempted")),
            "transcripts_ok": sum(1 for video in videos if video["transcript"]["status"] == "ok"),
            "transcripts_error": sum(1 for video in videos if video["transcript"]["status"] != "ok"),
            "transcript_error_types": transcript_error_types(videos),
            "playlist_page_fallback": used_page_fallback,
            "filter_mode": filter_mode,
            **transcript_summary,
        },
    }

    slug = f"curated-playlist-{issue_date}"
    json_path = output_dir / f"{slug}.json"
    md_path = output_dir / f"{slug}.md"
    retry_path = output_dir / "transcript-retry-queue.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(md_path, report)
    write_transcript_retry_queue(retry_path, videos)
    return {
        "ok": True,
        "lane": "youtube_playlist",
        "message": "YouTube playlist refreshed.",
        "note": "Used playlist page fallback because YouTube RSS returned 404." if used_page_fallback else "",
        "json": str(json_path.relative_to(ROOT)),
        "markdown": str(md_path.relative_to(ROOT)),
        "retry_queue": str(retry_path.relative_to(ROOT)),
        "summary": report["summary"],
    }


def fetch_channel_page(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def channel_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if "channel" in path_parts:
        index = path_parts.index("channel")
        if index + 1 < len(path_parts) and path_parts[index + 1].startswith("UC"):
            return path_parts[index + 1]
    query_channel = parse_qs(parsed.query).get("channel_id", [""])[0]
    if query_channel.startswith("UC"):
        return query_channel
    page = fetch_channel_page(url)
    patterns = [
        r'"channelId":"(UC[^"]+)"',
        r'"externalId":"(UC[^"]+)"',
        r'<meta itemprop="channelId" content="(UC[^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, page)
        if match:
            return match.group(1)
    raise ValueError(f"Could not resolve YouTube channel ID from {url}")


def fetch_channel_feed(channel_id: str) -> bytes:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    with urlopen(url, timeout=30) as response:
        return response.read()


def refresh_youtube_watchlist(request: dict) -> dict:
    config = load_source_config()
    watchlist = config.get("youtube", {}).get("watchlist", {})
    output_dir = YOUTUBE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    issue_date = request.get("issue_date") or datetime.now(timezone.utc).date().isoformat()
    report = {
        "fetched_at": utc_now(),
        "request": request,
        "channels": [],
        "videos": [],
        "summary": {
            "channels_configured": 0,
            "channels_checked": 0,
            "channels_need_url": 0,
            "channels_error": 0,
            "videos_found": 0,
        },
    }

    for tier_name in ("tier_1", "tier_2", "tier_3"):
        for source in source_items(watchlist.get(tier_name)):
            report["summary"]["channels_configured"] += 1
            name = source_name(source)
            url = source_url(source)
            channel_result = {"name": name, "url": url, "tier": tier_name}
            if not url:
                channel_result["status"] = "needs_url"
                report["summary"]["channels_need_url"] += 1
                report["channels"].append(channel_result)
                continue
            if not is_youtube_url(url):
                channel_result["status"] = "needs_youtube_url"
                channel_result["note"] = "This watchlist lane only accepts YouTube channel URLs. Move newsletter or website URLs to Newsletter sources."
                report["summary"]["channels_need_url"] += 1
                report["channels"].append(channel_result)
                continue
            try:
                channel_id = channel_id_from_url(url)
                playlist, entries = parse_feed(fetch_channel_feed(channel_id))
                entries = recent_entries(entries, request.get("since_date", ""))
                channel_result.update({"status": "ok", "channel_id": channel_id, "videos_found": len(entries)})
                report["summary"]["channels_checked"] += 1
                for entry in entries:
                    entry["source_lane"] = "youtube_watchlist"
                    entry["source_tier"] = tier_name
                    entry["priority"] = "watchlist"
                    entry["watchlist_source"] = name
                    entry["transcript"] = skipped_transcript(
                        "NotFetchedWatchlistDiscovery",
                        "Watchlist discovery stores metadata first; transcripts are fetched only after candidate selection.",
                    )
                    entry["transcript_cached"] = False
                    entry["transcript_attempted"] = False
                    report["videos"].append(entry)
            except Exception as exc:
                channel_result.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc)})
                report["summary"]["channels_error"] += 1
            report["channels"].append(channel_result)

    report["summary"]["videos_found"] = len(report["videos"])
    json_path = output_dir / f"watchlist-{issue_date}.json"
    md_path = output_dir / f"watchlist-{issue_date}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_source_markdown(md_path, "YouTube Watchlist", report["videos"], report)
    return {
        "ok": True,
        "lane": "youtube_watchlist",
        "message": "YouTube watchlist refreshed.",
        "json": str(json_path.relative_to(ROOT)),
        "markdown": str(md_path.relative_to(ROOT)),
        "summary": report["summary"],
    }


def refresh_newsletters(request: dict) -> dict:
    config = load_source_config()
    NEWSLETTER_DIR.mkdir(parents=True, exist_ok=True)
    issue_date = request.get("issue_date") or datetime.now(timezone.utc).date().isoformat()
    sources = source_items(config.get("newsletters", {}).get("sources"))
    report = {
        "fetched_at": utc_now(),
        "request": request,
        "sources": [
            {
                "name": source_name(source),
                "url": source_url(source),
                "status": "connector_needed",
                "note": "Local runner cannot read Gmail by itself. Use the Gmail connector or export matching newsletters into this data folder.",
            }
            for source in sources
        ],
        "items": [],
        "summary": {
            "sources_configured": len(sources),
            "items_found": 0,
            "connector_needed": True,
        },
    }
    json_path = NEWSLETTER_DIR / f"newsletters-{issue_date}.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "ok": True,
        "lane": "newsletters",
        "message": "Newsletter refresh request prepared.",
        "note": "Gmail/newsletter ingestion needs the Gmail connector or exported newsletter files.",
        "json": str(json_path.relative_to(ROOT)),
        "summary": report["summary"],
    }


def candidate_score(video: dict) -> int:
    if video.get("source_lane") == "youtube_playlist":
        return 96
    tier = video.get("source_tier", "")
    return {"tier_1": 84, "tier_2": 72, "tier_3": 58}.get(tier, 60)


def transcript_duration_seconds(transcript: dict) -> int | None:
    entries = transcript.get("entries")
    if not isinstance(entries, list) or not entries:
        return None
    last = entries[-1]
    start = float(last.get("start", 0) or 0)
    duration = float(last.get("duration", 0) or 0)
    total = int(round(start + duration))
    return total or None


def candidate_from_video(video: dict) -> dict:
    transcript = video.get("transcript", {})
    has_transcript = transcript.get("status") == "ok"
    description = video.get("description") or ""
    summary = (
        transcript.get("text", "")[:420].strip()
        if has_transcript
        else description or transcript.get("error") or "Metadata-only candidate; transcript is not available yet."
    )
    return {
        "id": f"yt-{video.get('video_id')}",
        "video_id": video.get("video_id"),
        "kind": "youtube",
        "source": video.get("channel") or video.get("watchlist_source") or "YouTube",
        "source_lane": video.get("source_lane"),
        "source_tier": video.get("source_tier", ""),
        "title": video.get("title") or "Untitled YouTube video",
        "url": video.get("url") or f"https://www.youtube.com/watch?v={video.get('video_id')}",
        "date": video.get("published")[:10] if video.get("published") else "",
        "score": candidate_score(video),
        "priority": video.get("priority") or "standard",
        "transcript_status": transcript.get("status", "unknown"),
        "transcript_error_type": transcript.get("error_type", ""),
        "description": description,
        "duration_seconds": transcript_duration_seconds(transcript),
        "summary": summary,
    }


def source_video_index(issue_date: str) -> dict[str, dict]:
    videos = {}
    for path in sorted(YOUTUBE_DIR.glob(f"*-{issue_date}.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for video in data.get("videos", []):
            video_id = video.get("video_id")
            if video_id:
                videos.setdefault(video_id, video)
    return videos


def enrich_pool_candidates(candidates: list[dict], issue_date: str) -> list[dict]:
    videos = source_video_index(issue_date)
    enriched = []
    for candidate in candidates:
        item = dict(candidate)
        video_id = item.get("video_id") or str(item.get("id", "")).removeprefix("yt-")
        source_video = videos.get(video_id)
        if source_video:
            transcript = source_video.get("transcript", {})
            item.setdefault("description", source_video.get("description") or "")
            item.setdefault("duration_seconds", transcript_duration_seconds(transcript))
        enriched.append(item)
    return enriched


def rebuild_candidate_pool(request: dict, reports: list[dict] | None = None) -> dict:
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    issue_date = request.get("issue_date") or datetime.now(timezone.utc).date().isoformat()
    videos = []
    if reports:
        for report in reports:
            videos.extend(report.get("videos", []))
    else:
        for path in sorted(YOUTUBE_DIR.glob(f"*-{issue_date}.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            videos.extend(data.get("videos", []))

    deduped = {}
    for video in videos:
        video_id = video.get("video_id")
        if video_id:
            deduped.setdefault(video_id, video)

    candidates = sorted((candidate_from_video(video) for video in deduped.values()), key=lambda item: item["score"], reverse=True)
    pool = {
        "built_at": utc_now(),
        "request": request,
        "candidates": candidates,
        "summary": {
            "candidate_count": len(candidates),
            "playlist_candidates": sum(1 for item in candidates if item.get("source_lane") == "youtube_playlist"),
            "watchlist_candidates": sum(1 for item in candidates if item.get("source_lane") == "youtube_watchlist"),
            "transcripts_ok": sum(1 for item in candidates if item.get("transcript_status") == "ok"),
            "transcripts_missing": sum(1 for item in candidates if item.get("transcript_status") != "ok"),
        },
    }
    json_path = CANDIDATE_DIR / f"candidate-pool-{issue_date}.json"
    json_path.write_text(json.dumps(pool, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "ok": True,
        "lane": "candidate_pool",
        "message": "Candidate pool rebuilt.",
        "json": str(json_path.relative_to(ROOT)),
        "summary": pool["summary"],
    }


def write_source_markdown(path: Path, title: str, videos: list[dict], report: dict) -> None:
    lines = [f"# {title}", "", f"Fetched: {report['fetched_at']}", ""]
    for video in videos:
        lines.extend(
            [
                f"## {video.get('title', 'Untitled')}",
                "",
                f"- Channel: {video.get('channel') or video.get('watchlist_source', '')}",
                f"- Published: {video.get('published', '')}",
                f"- URL: {video.get('url', '')}",
                f"- Lane: {video.get('source_lane', '')}",
                f"- Transcript: {video.get('transcript', {}).get('status', 'not fetched')}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def load_transcript_cache(output_dir: Path) -> dict[str, dict]:
    cache = {}
    for path in output_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for video in data.get("videos", []):
            video_id = video.get("video_id")
            transcript = video.get("transcript")
            if video_id and transcript and transcript.get("status") == "ok":
                cache.setdefault(video_id, transcript)
    return cache


def write_transcript_retry_queue(path: Path, videos: list[dict]) -> None:
    retry_items = []
    existing = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            existing = {item.get("video_id"): item for item in data.get("items", []) if item.get("video_id")}
        except Exception:
            existing = {}
    for video in videos:
        transcript = video.get("transcript", {})
        if transcript.get("status") == "ok" or not transcript.get("retry_later", True):
            continue
        video_id = video.get("video_id")
        item = {
            "video_id": video_id,
            "title": video.get("title"),
            "url": video.get("url"),
            "channel": video.get("channel"),
            "source_lane": video.get("source_lane"),
            "last_error_type": transcript.get("error_type"),
            "last_error": transcript.get("error"),
            "updated_at": utc_now(),
            "attempt_count": (existing.get(video_id, {}).get("attempt_count") or 0)
            + (1 if video.get("transcript_attempted") else 0),
        }
        retry_items.append(item)
    path.write_text(json.dumps({"updated_at": utc_now(), "items": retry_items}, indent=2, ensure_ascii=False), encoding="utf-8")


def transcript_error_types(videos: list[dict]) -> dict[str, int]:
    counts = {}
    for video in videos:
        transcript = video.get("transcript", {})
        if transcript.get("status") == "ok":
            continue
        key = transcript.get("error_type") or "Unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def refresh_placeholder(request: dict) -> dict:
    lane = request.get("lane", "unknown")
    output_dir = ROOT / "data" / "refresh_requests"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{lane}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps({"ok": False, "request": request}, indent=2), encoding="utf-8")
    return {
        "ok": False,
        "lane": lane,
        "message": f"{lane} refresh is queued as a request; backend implementation is not wired yet.",
        "request_file": str(path.relative_to(ROOT)),
    }


def refresh_all(request: dict) -> dict:
    results = []
    reports = []
    for refresh_func in (refresh_youtube_playlist, refresh_youtube_watchlist, refresh_newsletters):
        try:
            result = refresh_func(request)
            results.append(result)
            if result.get("json"):
                data = json.loads((ROOT / result["json"]).read_text(encoding="utf-8"))
                reports.append(data)
        except Exception as exc:
            results.append(
                {
                    "ok": False,
                    "message": f"{refresh_func.__name__} failed.",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    candidate_result = rebuild_candidate_pool(request, reports)
    results.append(candidate_result)
    return {
        "ok": True,
        "lane": "all",
        "message": "All source refresh lanes completed with local artifacts.",
        "results": results,
        "json": candidate_result.get("json"),
        "summary": {
            "lanes_completed": sum(1 for result in results if result.get("ok")),
            "lanes_failed": sum(1 for result in results if not result.get("ok")),
            "candidate_count": candidate_result.get("summary", {}).get("candidate_count", 0),
        },
    }


def run_refresh(request: dict) -> dict:
    lane = request.get("lane")
    if lane == "youtube_playlist":
        return refresh_youtube_playlist(request)
    if lane == "youtube_watchlist":
        return refresh_youtube_watchlist(request)
    if lane == "newsletters":
        return refresh_newsletters(request)
    if lane == "all":
        return refresh_all(request)
    if lane == "candidate_pool":
        return rebuild_candidate_pool(request)
    return refresh_placeholder(request)


class AdminHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        clean = unquote(parsed.path.lstrip("/"))
        return str((ROOT / clean).resolve())

    def send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/source-config":
            self.send_json(HTTPStatus.OK, {"ok": True, "config": load_source_config()})
            return
        if parsed.path == "/api/candidate-pool":
            issue_id = parse_qs(parsed.query).get("issue_id", ["2026-05-11"])[0]
            result = load_candidate_pool(issue_id)
            self.send_json(HTTPStatus.OK, result)
            return
        if parsed.path == "/api/issue":
            issue_id = parse_qs(parsed.query).get("issue_id", ["2026-05-11"])[0]
            issue = load_issue(issue_id)
            self.send_json(HTTPStatus.OK, {"ok": True, "issue": issue, "blocks": issue_blocks(issue)})
            return
        if self.path == "/" or self.path == "":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/AINewsletter/admin/index.html")
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        try:
            request = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if path == "/api/source-config":
                config = request.get("config", request)
                save_source_config(config)
                self.send_json(HTTPStatus.OK, {"ok": True, "config": config})
                return
            if path == "/api/build-brief":
                issue_model = request.get("issue", request)
                self.send_json(HTTPStatus.OK, build_brief(issue_model))
                return
            if path == "/api/rewrite-block":
                self.send_json(HTTPStatus.OK, rewrite_block(request))
                return
            if path == "/api/apply-block":
                self.send_json(HTTPStatus.OK, apply_block(request))
                return
            if path == "/api/publish":
                self.send_json(HTTPStatus.OK, publish_newsletter(request))
                return
            if path != "/api/refresh":
                self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Unknown endpoint"})
                return
            result = run_refresh(request)
            self.send_json(HTTPStatus.OK, result)
        except Exception as exc:
            self.send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error_type": type(exc).__name__, "error": str(exc)},
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the AI newsletter admin with local refresh endpoints.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), AdminHandler)
    print(f"Serving admin at http://{args.host}:{args.port}/AINewsletter/admin/index.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
