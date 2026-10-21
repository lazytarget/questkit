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
modified: 2026-10-21
agentic: hitl
aliases:
  - QST-97lsa
blocked_by:
  - QST-vy4vt
  - QST-x4zw2
  - QST-vruo7
component: pages
effort: xl
milestone: 0.5.0
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

There is no separate quest log for `questkit-pages`. Every slice becomes a quest in **this**
log, marked `component: pages` and tagged `pages`, with `blocked_by` carrying the order
between slices. `quest list --where component=pages` is the slice board. Upstream
prerequisites are ordinary quests in the same log.

| # | Slice | Home |
|---|-------|------|
| S0 | Repo, `CLAUDE.md`, `README.md`, tooling skeleton | questkit-pages |
| S1 | Quest bodies available in the JSON output (no file-reading fallback). Delivered by [[QST-vy4vt--body-as-a-lazily-loaded-queryable-field]] in 0.4.0; the remaining gaps are in [[QST-vruo7--json-surface-for-external-consumers-select-all-fields-path-field-and-views-in-the-schema-output]] | questkit (upstream) |
| S2 | Extractor and versioned data contract with JSON Schemas | questkit-pages |
| S3 | SvelteKit skeleton: prerender, `[id]` route with `entries()`, `BASE_PATH`, `404.html` | questkit-pages |
| S4 | Client-side list, filter, sort; filter state in `?query` params | questkit-pages |
| S5 | Detail pages: sanitized Markdown, heading anchors, wikilinks | questkit-pages |
| S6 | Status board, dependency graph, built-in views (`next`, `stale`, `blocked`) | questkit-pages |
| S7 | Composite Action, `configure-pages` integration, demo workflow, synthetic demo log | questkit-pages |
| S8 | Project-qualified links, disambiguation page, custom-domain verification | questkit-pages |
| S9 | Docs, `v1` tag, Marketplace listing | questkit-pages |

### Upstream questkit work

Hard prerequisites (listed in `blocked_by`; they stay listed after they are done, because the
field records dependencies, not open work):

- [[QST-vy4vt--body-as-a-lazily-loaded-queryable-field]] (done, 0.4.0): `body` in the JSON.
- [[QST-x4zw2--publish-questkit-remote-package-registry-and-tagged-releases]]: questkit is
  public on GitHub and PyPI (`v0.4.0`), so the Action has something to install. Until the
  quest below lands, the Action pins `questkit-ref` to a git ref, and moves to a PyPI
  version afterwards.
- [[QST-vruo7--json-surface-for-external-consumers-select-all-fields-path-field-and-views-in-the-schema-output]]
  (0.5.0): select all fields, a `path` field, and `views` in the schema JSON. Checked against
  0.4.0: none exists. Blocks S2 (extractor) and S6 (built-in views).

Not blockers; each is independently valuable:

- [[QST-f6otu--markdown-output-format-for-quest-list-and-views]] (done): Markdown output,
  shared with the changelog helper.
- [[QST-oguay--group-by-aggregation-in-quest-list]] and
  [[QST-tok0k--milestone-view-and-burnup-in-the-development-schema]] (both done): milestone burnup.
- [[QST-eszpe--quest-stats-distributions-flow-and-backlog-age]]: a stats page.
- [[QST-z9og3--ics-feed-for-due-dated-quests]]: a subscribable calendar feed, which a hosted
  site makes reachable by URL.
- [[QST-8hq61--reusable-ci-recipe-for-repos-hosting-a-quest-log]]: `validate && format --check`
  as a step in the same workflow.

### Wikilinks

`[[...]]` links in a body take more than one form, and S5 resolves all of them at build time:

| Form | Example | Resolves to |
|------|---------|-------------|
| Bare id | `[[QST-vy4vt]]` | the quest page |
| Id with slug | `[[QST-vy4vt--body-as-a-lazily-loaded-queryable-field]]` | the quest page; the id is the key and the slug is ignored |
| Qualified | `[[questkit/QST-vy4vt]]` | the quest page in that log |
| Alias or display text | `[[QST-vy4vt\|body field]]` | the quest page, with the given text |
| Heading fragment | `[[QST-vy4vt#acceptance-criteria]]` | the page plus anchor |
| Anything else | `[[./AGENTS]]`, `[[Some note]]` | plain text; never a broken link |

- A link to an id that is not in the published data (unsynced log, typo) renders as plain
  text with a visible "unresolved" marker, and the build **logs a warning** listing the
  source quest and target. It does not fail the build: `quest validate` is where a dangling
  link is an error, and the same quest must publish the same way on every device.
- A bare id that matches two logs links to the disambiguation page (S8).
- Resolution uses the same id and filename rules as questkit. Do not re-derive them: take the
  id with the questkit id pattern and look it up in the extracted data.

### Build metadata

`manifest.json` carries `generated_at` (UTC, ISO 8601), the source commit SHA when the
workflow runs in a checkout, `questkit_version` and `contract_version`. Computed fields
(`idle`, `age`, `overdue`, `due_in`) are evaluated at extraction time, so on a static site
they go stale on the day after the build. Every page therefore shows "as of
`<generated_at>`" in its footer, and the list page shows it next to the filters. The
extractor takes the value from one clock call at the start of the run, so every file in
one build agrees. The workflow should also run on a nightly `schedule:` trigger, so the
numbers do not drift further than a day.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Repo | Separate: `lazytarget/questkit-pages` | Core stays lean; the site only consumes the JSON surface |
| Name | `questkit-pages` | Reads as part of the ecosystem and as a product (`uses: lazytarget/questkit-pages@v1`) |
| Data source | `quest ... --format json`, not file parsing | One parser for the format; computed fields (`blocked`, `idle`, ...) come from the CLI |
| Rendering | SvelteKit `adapter-static`, prerendered and hydrated | Real HTML per quest plus client-side interactivity |
| Routing | Path-based; hash routing rejected | The hash router disables prerendering |
| Base path | From `actions/configure-pages` outputs | Correct for project sites, user sites and custom domains |
| Wikilinks | Resolve every form in the table above; unresolved ones degrade to text and a warning | A published site must not fail on a link that `quest validate` already judges |
| Build time | `generated_at` in the manifest, shown on every page | `idle` and `age` are frozen at build; readers need to know how old the numbers are |
| Slice quests | In the questkit log, `component: pages` and tag `pages`; no second log | One place to plan; `blocked_by` carries the order |
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
- [ ] The same workflow verified on a custom domain with an empty base path (hitl: needs a real domain and DNS)
- [ ] Every quest has a prerendered page; bare and `<project>/` URLs both resolve; heading anchors work
- [ ] List, filter and sort work client-side; filter state survives a reload via URL params
- [ ] Quest bodies come from the questkit JSON output (S1), not from reading files
- [ ] Every wikilink form in the table resolves in the demo log; an unresolvable one renders as plain text with a marker and a build warning
- [ ] A broken or unreadable log fails the Action instead of publishing a half-empty site
- [ ] A visible banner lists any log that was skipped (unsynced or unreadable)
- [ ] `generated_at` and the source SHA are in the manifest and shown on every page; one clock read per build
- [ ] The site loads no external assets (scripts, fonts, CDN) and works offline
- [ ] Keyboard navigation and a phone-width layout pass a basic accessibility check (automated plus a manual pass)
- [ ] The slice quests exist in this log with `component: pages`, tag `pages` and `blocked_by` links
- [ ] Markdown output is sanitized; a quest body containing a script tag does not execute
- [ ] Documented usage: a copy-paste workflow in the README
- [ ] `v1` tag released

## Log

- 2026-10-14: captured. Scope agreed in a design session: separate repo, `--format json` as the data route, prerendered SvelteKit with client-side hydration, `configure-pages` for base path, namespaced URLs opt-in for emission but always resolvable
- 2026-10-16: Added to milestone 0.5.0.
- 2026-10-21: Plan review against questkit `0.4.0` (released, on PyPI). S1's body field shipped with [[QST-vy4vt--body-as-a-lazily-loaded-queryable-field]]. Three gaps remain (select all fields, `path`, `views` in the schema JSON), filed as [[QST-vruo7--json-surface-for-external-consumers-select-all-fields-path-field-and-views-in-the-schema-output]]. `blocked_by` filled in (resolved blockers stay listed). No separate quest log: slices live here under `component: pages`. Added the wikilinks section, build metadata (`generated_at`), and the acceptance criteria for failing loudly, skipped-log banner, offline and accessibility.

