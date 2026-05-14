import { cp, mkdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const outputDir = join(root, 'dist', 'cloudflare');

await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });

await cp(join(root, 'AINewsletter'), join(outputDir, 'AINewsletter'), {
  recursive: true,
  filter: source => !source.includes(`${join('AINewsletter', 'admin')}`)
});

await writeFile(
  join(outputDir, 'index.html'),
  `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url=/AINewsletter/">
  <title>Clarity AI Newsletter</title>
</head>
<body>
  <p><a href="/AINewsletter/">Open the Clarity AI Newsletter</a></p>
</body>
</html>
`,
  'utf8'
);

await writeFile(
  join(outputDir, '404.html'),
  `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Page not found</title>
</head>
<body>
  <h1>Page not found</h1>
  <p><a href="/AINewsletter/">Return to the Clarity AI Newsletter</a></p>
</body>
</html>
`,
  'utf8'
);

console.log(`Built Cloudflare static site at ${outputDir}`);
