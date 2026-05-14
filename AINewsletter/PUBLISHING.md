# AI Newsletter Publishing Notes

Target public URLs:

- `https://clarityinnovation.ai/AINewsletter`
- `https://clarityinnovation.ai/AINewsletter/2026-05-11`
- `https://clarityinnovation.ai/AINewsletter/2026-05-11/technical`

Local files to publish:

- `AINewsletter/index.html` -> `/AINewsletter/index.html`
- `AINewsletter/2026-05-11/index.html` -> `/AINewsletter/2026-05-11/index.html`
- `AINewsletter/2026-05-11/technical/index.html` -> `/AINewsletter/2026-05-11/technical/index.html`
- `AINewsletter/assets/ai-infrastructure-hero.png` -> `/AINewsletter/assets/ai-infrastructure-hero.png`
- `AINewsletter/assets/platform-distribution-map-gpt-image-2.png` -> `/AINewsletter/assets/platform-distribution-map-gpt-image-2.png`
- `AINewsletter/assets/compute-economics-gpt-image-2.png` -> `/AINewsletter/assets/compute-economics-gpt-image-2.png`
- `AINewsletter/assets/compute-economics-map.svg` -> optional fallback/reference only
- `AINewsletter/assets/platform-distribution-map.svg` -> `/AINewsletter/assets/platform-distribution-map.svg`

Local admin/review file:

- `AINewsletter/admin/index.html` -> local review page only unless auth is added.

Workflow:

1. Keep `AINewsletter/admin/index.html` and `AINewsletter/editor/index.html` local unless authentication is added.
2. Run `python scripts/package_publish.py --issue-date 2026-05-11`.
3. Upload `dist/hostinger/clarityinnovation-ai-newsletter-2026-05-11.zip` to Hostinger and extract it so the included `AINewsletter/` folder lands under the site root, normally `public_html/AINewsletter/`.
4. After upload, verify the archive page, executive issue, technical issue, assets, and cross-links.

Current note:

The available Hostinger tool in this Codex session can create or retrieve Hostinger Horizons editing links, but it does not expose a direct static-file upload/publish action for an existing Hostinger site. If the site is managed outside Horizons, upload the `AINewsletter/` folder contents through Hostinger file manager, FTP/SFTP, Git deployment, or the site's normal deployment pipeline.

Do not upload the admin/editor pages publicly until they have authentication. The package script excludes `AINewsletter/admin/` and `AINewsletter/editor/` by default.
