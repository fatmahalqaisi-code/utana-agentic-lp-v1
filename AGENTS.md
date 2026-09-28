# AGENTS.md

This repository contains the static Utana website.

## Structure

- `src/pages/` — canonical HTML pages
- `src/styles/` — production CSS
- `src/js/` — production JavaScript
- `src/experiments/` — previews and experiments; never shipped
- `static/` — images, favicons, robots.txt, sitemap.xml
- `scripts/` — build and validation tooling
- `deploy/` — Nginx and deployment configuration
- `public/` — generated production artifact
- `public-files.txt` — production allowlist

## Rules

- Edit source files under `src/` and `static/`.
- Do not edit `public/` manually.
- Do not recreate old root-level HTML/CSS/JS files.
- Do not add experiments to the production artifact.
- Preserve existing canonical URLs and SEO behavior.
- Preserve accessibility, responsive behavior, reduced motion, and email contact flow unless the task explicitly changes them.
- Keep changes focused; avoid unrelated refactors.
- Do not introduce frameworks or new build tooling without an explicit requirement.

## Validation

Before finishing a change, run:

```bash
./scripts/validate-launch.sh
```

If debugging:

```bash
./scripts/build-public.sh
python3 scripts/verify-public.py public public-files.txt
python3 scripts/verify-seo.py public public-files.txt
git diff --check
```

Do not weaken validation just to make a change pass.

## Deployment

Production serves the generated `public/` directory.

Deployment configuration is in:

- `deploy/README.md`
- `deploy/nginx/`

Never serve the repository root or `src/` directly.

## Git

For non-trivial work, use a separate branch/worktree.

Do not merge into `main` automatically.

When integrating upstream changes, map them into the current `src/`, `static/`, `scripts/`, and `deploy/` structure instead of restoring obsolete root-level files.
