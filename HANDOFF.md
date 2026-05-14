# Handoff

## Recovery note

- Active project location is `C:\Users\Greg\Codex\AI News`.
- The old Google Drive copy at `G:\My Drive\AI\Codex\AI News` was retired because this project repeatedly hit sandbox/browser/runtime stalls and stale-context recovery issues from that location.
- If a future Codex chat starts in the Google Drive folder, stop and switch to `C:\Users\Greg\Codex\AI News` first. The real `HANDOFF.md`, git repo, local admin runner, and current source files live there.

## Last completed

- Moved active work to local repo at `C:\Users\Greg\Codex\AI News`; do not edit the old Google Drive copy.
- Connected GitHub remote `https://github.com/C0recollector/clarity-ai-newsletter.git` and pushed `main`.
- Fixed five annotations.
- Added `ai-infrastructure-hero.png`.
- Updated the executive page hero.
- Restored the infrastructure section layout.
- Made "Executive brief" current-page text.
- Softened footer nav font weight.
- Updated `PUBLISHING.md`.
- Refined the executive hero so `ai-infrastructure-hero.png` now acts as a right-side background image that fades into the white title area.
- Created the first structured issue content model at `data/issues/2026-05-11.json`.
- Connected `AINewsletter/admin/index.html` approval/export flow to produce structured issue JSON with the editorial review nested under `review.approved_review`.
- Added admin controls for `Export Issue JSON`, `Export Review JSON`, and `Download Issue Model`.
- Validation completed with local static checks: `data/issues/2026-05-11.json` parses, and the extracted admin page script passes Node syntax check.
- Browser automation is still blocked by `windows sandbox failed: setup refresh failed with status exit code: 1`; validate visually in the in-app browser manually until that runtime is healthy.
- Updated the technical edition hero to match the executive edition: removed the old `Implementation Lens` card and used `ai-infrastructure-hero.png` as a faded right-side hero background.
- Confirmed active work is now in `C:\Users\Greg\Codex\AI News`; the old `G:\My Drive\AI\Codex\AI News` copy should remain untouched.
- Added `scripts/generate_issue_pages.py`, a conservative first-pass generator that reads `data/issues/2026-05-11.json` and syncs issue-driven fields into the executive and technical pages while preserving the existing hand-designed layouts.
- Ran `python .\scripts\generate_issue_pages.py`; it updated `AINewsletter/2026-05-11/index.html` and `AINewsletter/2026-05-11/technical/index.html`.
- Re-ran the generator and confirmed it is idempotent (`unchanged` for both pages on the second run).
- Static validation passed: `data/issues/2026-05-11.json` parses, `scripts/generate_issue_pages.py` compiles, the admin page script parses, and the executive page script parses. The technical page currently has no script.
- Browser automation remains blocked by `windows sandbox failed: setup refresh failed with status exit code: 1`; in-app visual QA is still the main unverified item.
- Added `Add Missed Source` to `AINewsletter/admin/index.html` above `1. Candidate Items`.
- The missed-source intake accepts pasted YouTube/article/X/newsletter URLs, auto-detects source type, creates a selected high-priority manual candidate, adds a selected strong segment, and includes `manual` plus `priority` metadata in review exports.
- Current missed-source intake is local/browser-state only. It does not fetch YouTube transcripts yet because the admin page is still a static `file://` page. Transcript fetching should be added through the source-refresh backend/local command runner.
- Added `Source Refresh` controls to `AINewsletter/admin/index.html` so Greg can prepare source refreshes any day of the week, not only on Friday.
- Refresh controls support a precise `Lookback days` number field and an issue date. This lets Greg refresh from a precise prior day, such as the previous Friday, even when updates happened after the prior newsletter on the same date.
- Refresh lanes are `Refresh YouTube Playlist`, `Refresh YouTube Watchlist`, `Refresh Newsletters`, and `Refresh All Sources`.
- Added `scripts/admin_server.py`, a local admin runner that serves the admin UI at `http://127.0.0.1:8765/AINewsletter/admin/index.html` and exposes `POST /api/refresh`.
- Added `data/source_config.json` with the curated YouTube playlist `AI & News to watch` and playlist ID `PLxFjGka4tveAOS0oDFqsnlsG0UqdlN0yC`.
- When opened through the local runner URL, `Refresh YouTube Playlist` now calls the local backend and writes refreshed cache files under `data/youtube`.
- When opened through `file://`, refresh buttons cannot execute; they only emit a structured `Source Refresh Request` JSON and tell Greg to use the local runner URL.
- `Refresh YouTube Watchlist`, `Refresh Newsletters`, and `Refresh All Sources` currently create backend placeholder request files; their real data fetchers still need to be implemented.
- `Refresh YouTube Playlist` now handles the unlisted playlist correctly: YouTube RSS returns 404, so the backend falls back to the public playlist page URL, parses embedded playlist items, and then fetches transcripts.
- Last direct backend test of `Refresh YouTube Playlist` succeeded for `AI & News to watch`: 45 videos found, 42 transcripts fetched, 3 transcript errors. Output files were `data/youtube/curated-playlist-2026-05-11.json` and `data/youtube/curated-playlist-2026-05-11.md`.
- Added a `Playlist basis` selector to the Source Refresh panel: Date published newest/oldest, Date added newest/oldest, and Manual order.
- The public playlist page fallback exposes visible order and relative published age (`13 hours ago`, `3 days ago`, etc.), so `Date published` lookback filtering now works approximately from the playlist page fallback. Direct backend test with 4 lookback days and `published_newest` returned 8 videos using `playlist_page_published_age_filter`.
- The public playlist page fallback does not expose exact playlist-added timestamps. `Date added` basis is currently order-only: it respects/reverses the visible playlist order but cannot precisely filter "added in the last X days" without browser-assisted logged-in extraction or YouTube playlistItems metadata.
- Source refresh success no longer opens the large export/code box at the bottom of the page. Successful refreshes now show a compact green result message inside the Source Refresh panel. The export box remains for Issue JSON, Review JSON, and refresh errors/details only.
- Source refresh summaries are now cache-aware and report videos found, cached transcripts used, transcript fetch attempts, usable transcripts, and transcript errors. This avoids confusing `0 fetched` with `0 found`.
- Added `Source Settings` panel to `AINewsletter/admin/index.html`. It exposes curated playlist name/ID, YouTube watchlist tiers 1/2/3, and newsletter source names.
- Added `GET /api/source-config` and `POST /api/source-config` to `scripts/admin_server.py`; settings load from and save to `data/source_config.json`.
- Expanded `data/source_config.json` so source lists are no longer only hard-coded in discussion: it now stores the curated playlist, YouTube watchlist tiers, and newsletter sources.
- Source Settings now accept source lines as `Name | URL`. Existing name-only entries still work, but URLs should be added for reliable automation. The UI stores entries as structured objects when URLs are present, and `data/source_config.json` now includes the curated playlist URL.
- The refresh fallback note (`Used playlist page fallback because YouTube RSS returned 404`) now appears inside the green refresh result message instead of as a separate note below the controls.
- Removed the quick lookback buttons (`24h`, `3d`, `7d`, `14d`) from the Source Refresh row because they made the layout awkward. Use the exact `Lookback days` number field instead.
- Source refresh result now includes transcript error type counts. `IpBlocked` means the transcript library was blocked by YouTube's transcript endpoint; it does not necessarily mean the video has no transcript.
- The `local request` and `manual override` metadata labels were restyled as compact `mini-pill` labels to match the smaller theme badges.
- Do not rely on repeated button presses to fix transcript failures. If `IpBlocked` appears, repeated refreshes can make blocking worse. The next transcript implementation should cache successes, rate-limit requests, stop or pause when block errors appear, and queue transcript retries for later.
- Best transcript strategy: reuse cache first; fetch playlist/watchlist metadata second; transcript only selected/high-priority videos; use browser-assisted transcript extraction for playlist/editorial-override videos where possible; use local or API speech-to-text only as a fallback for important videos that lack accessible captions; mark metadata-only summaries as lower confidence instead of silently pretending transcripts were available.
- Implemented safer transcript handling in `scripts/admin_server.py`: cache-first, configurable transcript attempt cap, delay between transcript requests, stop/skip behavior after YouTube blocking, and `data/youtube/transcript-retry-queue.json` for videos that need a later or browser-assisted transcript pass.
- Added a `Transcript attempts` control to the admin Source Refresh panel. Use `0` for metadata-only refreshes that should not touch YouTube transcript endpoints. Use a small number, such as `3`, for cautious transcript attempts.
- Implemented real `Refresh YouTube Watchlist` backend behavior for configured channels with URLs. The backend resolves YouTube channel URLs to channel IDs, reads RSS feeds, filters by date, and stores metadata-only candidates without transcript fetching.
- Used channel IDs from the refreshed curated playlist to fill several watchlist URLs in `data/source_config.json`: Matt Wolfe, Peter Diamandis / Moonshots, Limitless Podcast, Paul J Lipsky, Riley Brown, All-In Podcast, Dan Martell, and AI Daily Brief.
- `Refresh Newsletters` now writes a connector-ready artifact under `data/newsletters/`; the local runner still cannot read Gmail by itself. Gmail ingestion needs the Gmail connector or exported newsletter files.
- `Refresh All Sources` now runs playlist, watchlist, newsletters, and candidate-pool rebuild together. Latest verified run on 2026-05-13 with `lookback_days=5` and `max_transcript_attempts=0`: 15 playlist videos, 85 watchlist videos, 91 deduplicated candidate-pool items, 2 cached usable transcripts, 89 metadata-only/missing transcripts.
- Added `scripts/package_publish.py` to build a Hostinger upload bundle for `https://clarityinnovation.ai/AINewsletter/`. It writes `dist/hostinger/clarityinnovation-ai-newsletter-2026-05-11.zip` and a manifest. `dist/` is gitignored.
- Updated `AINewsletter/PUBLISHING.md` with the Hostinger package workflow. The package excludes `AINewsletter/admin/` by default because the admin page should not be public without authentication.

## Source strategy

Use a two-lane source strategy so the weekly brief has coverage without burning tokens on every possible item.

### Lane 1: Curated playlist

- Greg has an unlisted YouTube playlist named `AI & News to watch`.
- Treat this playlist as the highest-trust source and editorial override.
- If Greg adds a video to this playlist, assume he thought it mattered.
- Always include this lane in source refresh.
- Playlist videos should be transcripted, summarized, and weighted more heavily than ordinary channel-feed discoveries.
- Use this lane for watched videos Greg found useful, evergreen explainers, and items that should be included even if they are not from a standard monitored channel.

### Lane 2: Watchlist channels

- Use watchlist channels for coverage insurance.
- Monitor channel RSS feeds for recent videos, but do not summarize everything.
- Rank channel-feed items by AI relevance, source tier, title/description keywords, overlap with newsletter themes, source priority, and whether the item is also in Greg's curated playlist.
- Only fetch transcripts for the best candidates unless a source is in the curated playlist.

### Source tiers

Tier 1: Always check

- `AI & News to watch` playlist
- Matt Wolfe
- Matthew Berman
- Peter Diamandis / Moonshots
- Limitless Podcast
- World of AI
- TLDR AI
- Superhuman AI
- Metatrends

Tier 2: Check, but filter hard

- Paul J Lipsky
- Riley Brown
- Greg Isenberg
- All-In Podcast
- BitBiased AI
- Digital Storm
- TLDR general

Tier 3: Optional / only when relevant

- Dan Martell
- Alex Finn
- Vaibhav Sisinty
- AI Daily Brief
- Julian Goldie SEO
- Universe of AI
- ByteMonk

### Weekly workflow target

- Collect Gmail newsletters from the last 7 days, the curated playlist, and recent videos from Tier 1 and Tier 2 channels.
- Filter for model releases, AI agents, coding tools, enterprise adoption, regulation/legal, AI economics/infrastructure, robotics, and AI product/workflow strategy.
- Deduplicate overlapping coverage into one topic with multiple source links.
- Weekly scale target: 30-60 discovered candidate videos/newsletters, 12-20 summarized items, and 5-8 final published themes.
- Playlist videos should always be summarized. Tier 1 videos should be summarized when relevant. Tier 2 and Tier 3 should be summarized only when they add a unique angle. Newsletters should summarize useful headlines/sections, not promotional filler.
- Desired pipeline: Gmail newsletters + curated YouTube playlist + tiered YouTube channel watchlist -> candidate pool -> AI relevance ranking -> transcripts only for selected videos -> clusters into 5-8 weekly topics -> published brief page.

### Missed-source intake

- Add or continue improving the admin feature that lets Greg paste a missed source URL into `1. Candidate Items`.
- Supported source types should include YouTube video URLs first, then article/page URLs, X/Twitter URLs or feeds, and eventually newsletter/email references.
- Pasted URLs should be added as high-priority manual candidates for the current issue and marked as manually added.
- For YouTube URLs, fetch transcript if available, summarize, and add to the candidate pool without forcing a full source refresh.
- This feature is important because automated retrieval will miss items, and manual paste avoids rerunning token-heavy discovery.

## Next step

Manually verify the admin page in the browser, especially:

- `Advanced -> Export Issue JSON`
- `Advanced -> Export Review JSON`
- `Approve and Build Brief`
- `Download Issue Model`

Then visually verify the generated executive and technical pages still look right after the generator sync. The first generator pass exists now; next improvement is to move more body content and edition-specific copy into `data/issues/2026-05-11.json` so the pages depend less on existing HTML as their template surface.

After visual QA, build the source refresh workflow. Start with the curated YouTube playlist refresh and the missed-source URL intake before adding broader Gmail/newsletter and channel-watchlist automation.

The admin UI now has source-refresh buttons and a local runner. Next implementation work is to expand the backend beyond the curated YouTube playlist: implement watchlist-channel refresh, Gmail/newsletter refresh, candidate-pool rebuild, and preservation of manual candidates.

Current source-refresh status:

- Playlist refresh works and is cache-first, but unauthenticated transcript fetching is currently being blocked by YouTube after the first uncached attempt. Use `Transcript attempts = 0` for safe metadata refreshes.
- Watchlist refresh works for the 8 configured channels with URLs. Add URLs for the remaining 14 channels in Source Settings to improve coverage.
- Newsletter refresh currently prepares an artifact and does not ingest Gmail content yet.
- Candidate pool rebuild writes `data/candidates/candidate-pool-2026-05-11.json`; the admin UI still uses its hard-coded sample candidates and should next be wired to load the rebuilt candidate pool.
- Hostinger publish package exists locally; actual upload to `clarityinnovation.ai` still requires Hostinger file manager, FTP/SFTP, Git deploy, or a working Hostinger connector with upload capability.
- Fixed the `Approve and Build Brief` architecture. Previously the button only generated structured JSON inside the browser and exposed a link to the already-existing newsletter page; it did not save the JSON or rerun the generator. The admin button now calls `POST /api/build-brief`, which writes `data/issues/{issue_id}.json` and runs `scripts/generate_issue_pages.py`.
- The admin `buildIssueModel()` now updates section `title`, `headline`, `summary`, and `evidence_segment_ids` from the approved theme state. Theme renames such as `All Things Agents` -> `Just Agents` will appear in the generated executive page after rebuilding.
- Verified `POST /api/build-brief` with the current issue model. It returned ok and reported the executive and technical pages as unchanged because the current saved model already matched the current generated pages.
- Important UX note: any admin edits made before this fix lived only in the old browser page state. Greg should reload the admin page, reapply any desired theme/evidence edits, then click `Approve and Build Brief` again to save and regenerate.
- Implemented the "select a generated newsletter item and ask AI to rewrite this exact block" workflow as a generated-newsletter editor. It uses selectable blocks mapped to issue JSON fields -> prompt box -> AI/manual draft -> approve patch -> save issue JSON -> rerun generator. Avoid editing published HTML directly as the primary workflow.
- Moved the rewrite workflow out of `AINewsletter/admin/index.html` because Greg correctly noted it belongs after newsletter generation, not during candidate/theme approval. The local rewrite/edit workflow now lives at `AINewsletter/editor/index.html`.
- Renamed the main approval action from `Approve and Build Brief` to `Generate Newsletter`. After generation, the green link points to the newsletter editor page rather than directly implying the old page is the final workflow.
- Added `AINewsletter/editor/index.html`: it shows the generated newsletter in an iframe, lets Greg click a section or choose an editable block, enter rewrite instructions, generate/edit a draft, apply it back to issue JSON, and regenerate pages.
- Added local runner endpoints: `GET /api/issue`, `POST /api/rewrite-block`, and `POST /api/apply-block`.
- `POST /api/rewrite-block` tries a local OpenAI-compatible LM Studio endpoint at `http://127.0.0.1:1234/v1/chat/completions` with a short timeout. If no local AI responds, it falls back to manual-edit mode, keeps the current text as the draft, and saves the exact prompt under `data/rewrite_requests/`.
- `POST /api/apply-block` updates the selected issue JSON block, runs the generator, and returns updated blocks plus changed page paths.
- Added `POST /api/publish`, which currently prepares the Hostinger upload package. Direct Hostinger upload is not available from the exposed local runner/plugin tools in this session. The publish package excludes local admin/editor pages by default.
- Gmail connector verification: the Codex Gmail connector is configured and can find/read matching newsletter emails. The local static admin runner cannot call Codex connectors directly, so the current `Refresh Newsletters` button only writes a connector-ready artifact. A real in-page Gmail refresh requires either a Codex-mediated import step or adding Google OAuth/API support to the local runner.
- Verified rewrite apply/regenerate in a gitignored temporary issue under `dist/verify-rewrite`; changing `section.agents.summary` updated the generated executive page. Removed the temporary `data/issues/2026-05-13.json` after verification.
- Added `GET /api/candidate-pool` to the local runner. It reads `data/candidates/candidate-pool-{issue_id}.json` and returns the rebuilt candidate pool for the admin page.
- Wired `AINewsletter/admin/index.html` to load the rebuilt candidate pool automatically when opened through the local runner. The hard-coded sample candidates remain as the fallback for `file://` mode or when no candidate pool exists.
- Candidate-pool items are normalized into review candidates with one selectable signal each, inferred suggested themes, transcript-status notes, and source-lane/priority badges. `Refresh All Sources` now reloads the candidate pool into the review UI after the backend rebuilds it.
- Restarted the local admin runner on `http://127.0.0.1:8765/AINewsletter/admin/index.html`; `GET /api/candidate-pool?issue_id=2026-05-11` returned 91 candidates.
- Cleaned up Source Settings: YouTube watchlist rows now have YouTube URLs, newsletter-only sources were moved to the Newsletter list with source URLs/search labels, and the admin UI now explains that YouTube refresh needs channel URLs while newsletter names can act as Gmail search labels.
- Added backend validation so non-YouTube URLs pasted into YouTube tiers are marked `needs_youtube_url` instead of breaking the watchlist refresh.
