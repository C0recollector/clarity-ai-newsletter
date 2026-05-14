from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "AINewsletter"
DIST = ROOT / "dist" / "hostinger"


def should_skip(path: Path, include_admin: bool) -> bool:
    relative = path.relative_to(SOURCE)
    parts = set(relative.parts)
    if not include_admin and ("admin" in parts or "editor" in parts):
        return True
    return any(part in {"__pycache__", ".DS_Store"} for part in parts)


def copy_tree(target: Path, include_admin: bool) -> list[str]:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in SOURCE.rglob("*"):
        if path.is_dir() or should_skip(path, include_admin):
            continue
        relative = path.relative_to(SOURCE)
        destination = target / "AINewsletter" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied.append(str(Path("AINewsletter") / relative).replace("\\", "/"))
    return copied


def write_zip(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))


def package_for_hostinger(issue_date: str = "2026-05-11", include_admin: bool = False) -> dict:
    package_dir = DIST / f"clarityinnovation-ai-newsletter-{issue_date}"
    files = copy_tree(package_dir, include_admin)
    zip_path = DIST / f"clarityinnovation-ai-newsletter-{issue_date}.zip"
    write_zip(package_dir, zip_path)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_site": "https://clarityinnovation.ai/",
        "target_path": "/AINewsletter/",
        "package_dir": str(package_dir.relative_to(ROOT)),
        "zip": str(zip_path.relative_to(ROOT)),
        "include_admin": include_admin,
        "files": files,
        "verify_urls": [
            "https://clarityinnovation.ai/AINewsletter/",
            f"https://clarityinnovation.ai/AINewsletter/{issue_date}/",
            f"https://clarityinnovation.ai/AINewsletter/{issue_date}/technical/",
        ],
    }
    manifest_path = DIST / f"clarityinnovation-ai-newsletter-{issue_date}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Package AI Newsletter static files for Hostinger upload.")
    parser.add_argument("--issue-date", default="2026-05-11")
    parser.add_argument("--include-admin", action="store_true", help="Include local admin/editor tools. Do not use without auth.")
    args = parser.parse_args()
    manifest = package_for_hostinger(args.issue_date, args.include_admin)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
