---
id: QST-97lsa
title: "questkit-pages: publish a quest log as a static website via a GitHub Action"
description: "A generic GitHub Action that extracts quests with the questkit CLI and publishes a prerendered, client-interactive SvelteKit site to GitHub Pages (project sites and custom domains). Separate repo: lazytarget/questkit-pages."
project: questkit
type: epic
status: todo
priority: high
tags:
  - questkit
  - pages
  - github-actions
  - web
created: 2026-10-14
modified: 2026-10-14
agentic: hitl
aliases:
  - QST-97lsa
blocked_by: []
component: pages
effort: xl
milestone:
owner: peter
related_adrs:
tier: blueprint
---

## Description

Questkit quests are Markdown files that live next to the code. That is ideal for the author
and for agents, but nobody else can browse them without cloning the repo and installing the
CLI. GitHub Issues gives every collaborator a web view for free, and that gap is the single
biggest adoption barrier for questkit on GitHub-hosted repos.

**questkit-pages** closes it: a generic, reusable GitHub Action that anyone adds to their own
`.github/workflows/`. On push it extracts the quests through the questkit CLI
(`--format json`), builds a static site, and hands the result to GitHub Pages. No server, no
CLI for readers to install.

It is a **separate repository** (`lazytarget/questkit-pages`), not part of questkit core: the
core stays a lean CLI, and the site is a consumer of its stable JSON surface.

## Scope

Design record and conventions live in that repo's `CLAUDE.md`. Summary of the shape:

- **Extraction (Python):** `quest list -A --format json`, `quest schema quest --format json`
  and `quest logs --format json`, validated into a versioned data contract.
- **Site (SvelteKit, `adapter-static`):** every quest is **prerendered** to a real HTML page
  and then hydrated, so list / filter / sort run client-side while every quest keeps a
  linkable URL. Markdown is rendered at build time (sanitized), headings get anchor ids,
  `[[QST-...]]` wikilinks become links.
- **Action:** composite action; installs questkit from a pinned git ref (PyPI later), builds
  the site from its own source with `BASE_PATH` taken from `actions/configure-pages`
  (`base_path` / `origin`), so project sites, `<owner>.github.io` repos and **custom domains**
  all work. The adopter's own job runs `upload-pages-artifact` and `deploy-pages`.
- **URLs:** `/<quest-id>`, `/<quest-id>.html`, `/<project>/<quest-id>`, each with
  `#<heading-slug>` anchors. Both the bare and the project-qualified form always resolve;
  a `qualified-links` input (default off) only picks which form the site emits. A bare id
  that matches two logs renders a disambiguation page.

### Slices

Each slice becomes its own quest in the `questkit-pages` log; upstream prerequisites are
quests in this log.

| # | Slice | Home |
|---|-------|------|
| S0 | Repo, `CLAUDE.md`, `README.md` | questkit-pages |
| S1 | Quest bodies available in the JSON output (no file-reading fallback) | questkit (upstream) |
| S2 | Extractor and versioned data contract with JSON Schemas | questkit-pages |
| S3 | SvelteKit skeleton: prerender, `[id]` route with `entries()`, `BASE_PATH`, `404.html` | questkit-pages |
| S4 | Client-side list, filter, sort; filter state in `?query` params | questkit-pages |
| S5 | Detail pages: sanitized Markdown, heading anchors, wikilinks | questkit-pages |
| S6 | Status board, dependency graph, built-in views (`next`, `stale`, `blocked`) | questkit-pages |
| S7 | Composite Action, `configure-pages` integration, demo workflow, synthetic demo log | questkit-pages |
| S8 | Project-qualified links, disambiguation page, custom-domain verification | questkit-pages |
| S9 | Docs, `v1` tag, Marketplace listing | questkit-pages |

### Upstream questkit work this epic benefits from

Not blockers except S1; each is independently valuable:

- [[QST-vy4vt--body-as-a-lazily-loaded-queryable-field]]: the natural home for S1 (a body
  field in the JSON), together with a `--select body` decision.
- [[QST-f6otu--markdown-output-format-for-quest-list-and-views]]: Markdown output, shared
  with the changelog helper.
- [[QST-oguay--group-by-aggregation-in-quest-list]] and
  [[QST-tok0k--milestone-view-and-burnup-in-the-development-schema]]: milestone burnup.
- [[QST-eszpe--quest-stats-distributions-flow-and-backlog-age]]: a stats page.
- [[QST-z9og3--ics-feed-for-due-dated-quests]]: a subscribable calendar feed, which a hosted
  site makes reachable by URL.
- [[QST-8hq61--reusable-ci-recipe-for-repos-hosting-a-quest-log]]: `validate && format --check`
  as a step in the same workflow.
- [[QST-x4zw2--publish-questkit-remote-package-registry-and-tagged-releases]]: the first public
  release, after which the Action installs from PyPI instead of a git ref.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Repo | Separate: `lazytarget/questkit-pages` | Core stays lean; the site only consumes the JSON surface |
| Name | `questkit-pages` | Reads as part of the ecosystem and as a product (`uses: lazytarget/questkit-pages@v1`) |
| Data source | `quest ... --format json`, not file parsing | One parser for the format; computed fields (`blocked`, `idle`, ...) come from the CLI |
| Rendering | SvelteKit `adapter-static`, prerendered and hydrated | Real HTML per quest plus client-side interactivity |
| Routing | Path-based; hash routing rejected | The hash router disables prerendering |
| Base path | From `actions/configure-pages` outputs | Correct for project sites, user sites and custom domains |
| Markdown | Rendered at build time, sanitized | Quest bodies are untrusted input on the Pages origin; renderer and sanitizer packages still to be chosen (ask before adding) |
| Deploy | Adopter's job, not the Action | `pages: write` and `id-token: write` must sit on the deploying job |

## Out of scope

- Editing, authentication, comments, or any write path back to quest files
- Private or internal hosting (GitHub Pages visibility rules apply as they are)
- A hosted service; the Action is the whole product
- Non-GitHub forges (revisit if the Action proves out)

## Acceptance Criteria

- [ ] `lazytarget/questkit-pages` is public with `CLAUDE.md` and `README.md`
- [ ] The Action builds and deploys a demo site from a synthetic quest log on a project site
- [ ] The same workflow verified on a custom domain with an empty base path
- [ ] Every quest has a prerendered page; bare and `<project>/` URLs both resolve; heading anchors work
- [ ] List, filter and sort work client-side; filter state survives a reload via URL params
- [ ] Quest bodies come from the questkit JSON output (S1), not from reading files
- [ ] Markdown output is sanitized; a quest body containing a script tag does not execute
- [ ] Documented usage: a copy-paste workflow in the README
- [ ] `v1` tag released

## Log

- 2026-10-14: captured. Scope agreed in a design session: separate repo, `--format json` as the data route, prerendered SvelteKit with client-side hydration, `configure-pages` for base path, namespaced URLs opt-in for emission but always resolvable
