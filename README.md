# Utana website

This repository contains Utana's static website. The source is plain HTML, CSS,
and JavaScript; the build collects the production files into a generated
`public/` directory for validation and deployment.

## Project structure

- `src/pages/` — production HTML pages, arranged to match their public URLs.
- `src/styles/` — production stylesheets.
- `src/js/` — browser JavaScript.
- `src/experiments/` — design previews and alternate themes kept for local
  reference; these are not included in production builds.
- `static/` — runtime assets and root files such as images, icons, `robots.txt`,
  and `sitemap.xml`.
- `scripts/` — build, verification, and browser-smoke tools.
- `deploy/` — Nginx and certificate configuration for production.
- `public/` — generated, gitignored production output. Do not edit it directly.

`public-files.txt` lists every path allowed in the production artifact.

## Local development

Build the site, then serve the generated output with Python:

```sh
./scripts/build-public.sh
python3 -m http.server 8766 --directory public
```

Open <http://localhost:8766>. Rebuild after changing files under `src/`,
`static/`, or `public-files.txt`.

The build uses POSIX shell tools and Python 3; it does not install any packages.

## Validation

Run the full launch check from the repository root:

```sh
./scripts/validate-launch.sh
```

This builds the production artifact and checks:

- the allowlisted contents of `public/`;
- HTML structure, local assets, internal links, and fragments;
- canonical URLs, social metadata, favicons, robots, and sitemap data;
- browser behavior at desktop and mobile sizes, including navigation, keyboard
  interaction, reduced motion, layout overflow, broken images, and console or
  network errors;
- whitespace errors in the Git diff.

Browser smoke tests require Node.js and Chrome or Chromium. Set `CHROME_BIN` if
the browser is installed in a non-standard location. Screenshots are written to
`/tmp/utana-launch-screenshots` by default; set `SCREENSHOT_DIR` to change it.

For focused debugging, run the lower-level checks directly:

```sh
python3 scripts/verify-public.py public public-files.txt
python3 scripts/verify-seo.py public public-files.txt
node scripts/browser-smoke.mjs public
```

## Production build

`./scripts/build-public.sh` recreates `public/` from the sources in `src/` and
`static/`. `public-files.txt` is the production allowlist: if a file is not
listed there, it is not shipped. This keeps experiments, previews, repository
metadata, and build tooling out of the deployed site.

## Deployment

Production uses Nginx to serve the generated `public/` directory. Build and
validate the artifact before publishing it; do not point Nginx at the repository
checkout.

See [`deploy/README.md`](deploy/README.md) for the Ubuntu, HTTPS, and certificate
renewal steps. The Nginx configurations are in [`deploy/nginx/`](deploy/nginx/).

## Notes

- Production uses explicit `.html` URLs, including `index.html`, and the
  canonical origin is `https://utana.agentic.technologies`. Keep these URLs
  stable unless redirects are added at the hosting layer.
- `src/experiments/` is intentionally excluded from production.
- Team portraits already include responsive AVIF and JPEG variants; keep both
  formats when updating them.
- The contact form validates the required application fields and prepares an
  email draft for the visitor to review and send. There is no form backend or
  contact database.
- Google Fonts are loaded remotely, with system-font fallbacks.
