---
id: QST-onxad
title: New frontmatter attributes
description: Decide how a language hint reaches agents — resolved as a schema-declared field with a default, not a new core field.
created: 2026-08-16
modified: 2026-08-19
type: feature
tier: spark
status: todo
priority: low
effort: xs
project: questkit
tags:
  - questkit
  - schema
blocked_by:
  - QST-j68u5
aliases:
  - QST-onxad
agentic: afk
---

## Description

Original capture: a `language:` attribute would help agents adhere to a specific
language (the Realm authors documentation in English but the family log is
naturally Swedish).

**v3 changes the answer.** With `schema.fields` gaining defaults, macros and enum
types ([[QST-j68u5--schema-engine-field-order-defaults-macros-typed-fields-strict-writes]]), `language` does not need to be a core field at all — it is
exactly the kind of vocabulary that varies per log, which is what the schema
engine exists for.

Adding it to the core would mean every log carries a field most of them never
use, and questkit would be shipping an opinion about how work is described. The
Realm's own frontmatter schema already treats `language` as **optional**, and
explicitly says to *"omit for code repos under `02-projects/lazytarget`"* — a
per-context rule, which is a per-schema rule.

## Spec

### Approach

No core field. Declare it where it is wanted:

```yaml
# 99-system/questkit/schemas/household.yaml
schema:
  fields:
    language:
      type: enum
      values: [sv, en]
      default: sv
```

`development` either omits it or defaults to `en`. `quest brief` ([[QST-xk7js--quest-brief-a-self-contained-work-order-and-the-batch-capture-that-feeds-it]]) then
surfaces it in the metadata line for free, since it renders whatever the log's
schema declares — which is the actual goal: the hint reaching the agent.

### Alternatives

| Option | Verdict | Reason |
|--------|---------|--------|
| Schema-declared field with a default | ✅ Chosen | Varies per context, which is what the schema engine is for |
| Core optional field | ❌ | Ships an opinion; most logs would never use it |
| Body convention (`## Language`) | ❌ | Not queryable, not projectable, invisible to `quest brief`'s metadata line |

## Acceptance Criteria

- [ ] `language` is **not** added to questkit's core schema
- [ ] `household` declares `language` with `default: sv`
- [ ] A quest created in a log using that schema is stamped automatically
- [ ] `quest brief` surfaces it in the metadata line
- [ ] `quest schema quest language` describes it in a log that declares it
- [ ] Docs note the general principle: context-varying vocabulary goes in a schema, not the core

## Log

- 2026-08-16: captured as "Frontmatter attribute for `language:`"
- 2026-08-19: groomed as part of [[QST-bmzl2--questkit-v3-loop-closure-multi-log-ux-and-agent-handoff]]. Resolved as a schema field rather than a core field; retitled to match the filename, which had already generalized to plural.
