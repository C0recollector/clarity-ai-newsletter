import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / ".vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from youtube_transcript_api import YouTubeTranscriptApi  # noqa: E402


ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"


def text_or_empty(node):
    return node.text.strip() if node is not None and node.text else ""


def parse_date(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def fetch_feed(playlist_id):
    url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
    with urlopen(url, timeout=30) as response:
        return response.read()


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    playlist = {
        "title": text_or_empty(root.find(f"{ATOM}title")),
        "playlist_id": text_or_empty(root.find(f"{YT}playlistId")),
        "channel_id": text_or_empty(root.find(f"{YT}channelId")),
        "author": text_or_empty(root.find(f"{ATOM}author/{ATOM}name")),
        "published": text_or_empty(root.find(f"{ATOM}published")),
    }

    entries = []
    for entry in root.findall(f"{ATOM}entry"):
        group = entry.find(f"{MEDIA}group")
        thumbnail = group.find(f"{MEDIA}thumbnail") if group is not None else None
        stats = group.find(f"{MEDIA}community/{MEDIA}statistics") if group is not None else None
        link = entry.find(f"{ATOM}link")
        entries.append(
            {
                "video_id": text_or_empty(entry.find(f"{YT}videoId")),
                "title": text_or_empty(entry.find(f"{ATOM}title")),
                "url": link.attrib.get("href", "") if link is not None else "",
                "channel": text_or_empty(entry.find(f"{ATOM}author/{ATOM}name")),
                "channel_id": text_or_empty(entry.find(f"{YT}channelId")),
                "published": text_or_empty(entry.find(f"{ATOM}published")),
                "updated": text_or_empty(entry.find(f"{ATOM}updated")),
                "thumbnail": thumbnail.attrib.get("url", "") if thumbnail is not None else "",
                "views": int(stats.attrib.get("views", "0")) if stats is not None else None,
                "description": text_or_empty(group.find(f"{MEDIA}description")) if group is not None else "",
            }
        )
    return playlist, entries


def fetch_transcript(api, video_id):
    try:
        transcript = api.fetch(video_id, languages=["en"])
        snippets = transcript.to_raw_data()
        return {
            "status": "ok",
            "language": getattr(transcript, "language_code", "en"),
            "snippet_count": len(snippets),
            "text": " ".join(item["text"].replace("\n", " ") for item in snippets),
            "snippets": snippets,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def write_markdown(path, report):
    lines = [
        f"# {report['playlist']['title']}",
        "",
        f"Fetched: {report['fetched_at']}",
        f"Playlist ID: `{report['playlist']['playlist_id']}`",
        "",
    ]
    for video in report["videos"]:
        lines.extend(
            [
                f"## {video['title']}",
                "",
                f"- Channel: {video['channel']}",
                f"- Published: {video['published']}",
                f"- Updated: {video['updated']}",
                f"- URL: {video['url']}",
                f"- Transcript: {video['transcript']['status']}",
                "",
            ]
        )
        if video["transcript"]["status"] == "ok":
            text = video["transcript"]["text"]
            lines.extend([text[:4000], ""])
        else:
            lines.extend([video["transcript"].get("error", ""), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist-id", required=True)
    parser.add_argument("--output-dir", default="data/youtube")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    playlist, entries = parse_feed(fetch_feed(args.playlist_id))
    if args.limit:
        entries = entries[: args.limit]

    api = YouTubeTranscriptApi()
    videos = []
    for entry in entries:
        entry["transcript"] = fetch_transcript(api, entry["video_id"])
        videos.append(entry)

    report = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "playlist": playlist,
        "videos": videos,
        "summary": {
            "video_count": len(videos),
            "transcripts_ok": sum(1 for v in videos if v["transcript"]["status"] == "ok"),
            "transcripts_error": sum(1 for v in videos if v["transcript"]["status"] != "ok"),
        },
    }

    slug = args.playlist_id
    json_path = output_dir / f"{slug}.transcripts.json"
    md_path = output_dir / f"{slug}.transcripts.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(md_path, report)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
