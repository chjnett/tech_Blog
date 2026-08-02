# chjnett.dev blog — project instructions

Personal tech blog + portfolio on Cloudflare (Pages + Workers + D1 + R2).
Full design system, architecture, and content pipeline: [`docs/HANDOFF.md`](docs/HANDOFF.md).
Read it before working on design, D1 schema, or the content pipeline — it's the
source of truth, not this file.

## Non-negotiable rules

- **No auto-publish, ever.** Every content source (manual memo, github commit,
  paper cron) creates a `draft`. Only a human approval in the review dashboard
  moves a post to `published`. Never add a code path that publishes without
  that approval step, even conditionally.
- **Monochrome outside code blocks.** The only color in the entire site lives
  inside `.code-block` syntax highlighting (4 roles: keyword/string/comment/function,
  see `docs/HANDOFF.md` §1.1). Everywhere else, emphasis comes from weight,
  border, black/white inversion, or position — not color.

## Ask before proceeding

Don't decide these unilaterally — ask the user first (see `docs/HANDOFF.md` §6
for the full, growing checklist):

- Adding color anywhere outside a code block.
- A new content component beyond code/terminal/figure (§2) — propose a spec first.
- Running a D1 migration — confirm it won't break existing rows.
- `wrangler deploy` to production (vs. previewing first).
- Wiring a GitHub webhook — confirm which repo/branch.
- Any change that could meaningfully raise Anthropic API cost (e.g. cron frequency).
- Widening/narrowing the arXiv categories the paper cron watches.
- Any code path that looks like it might auto-publish without review.

## Skill routing for this repo

- **`superpowers:brainstorming` → `superpowers:writing-plans` → `superpowers:executing-plans`
  or `superpowers:subagent-driven-development`** — the standard flow for any new
  subsystem (review dashboard, paper cron, webhook, R2 upload, RAG). Specs live in
  `docs/superpowers/specs/`, plans in `docs/superpowers/plans/`.
- **`wrangler`** — load before running any `wrangler` CLI command (migrations, dev, deploy).
- **`workers-best-practices`** — load when writing or reviewing `worker/src/**` code.
- **`cloudflare`** — load for D1/R2/general Cloudflare platform questions beyond Workers basics.
- **`verify`** — run before marking any implementation task done; this project has no
  automated test suite by design (see Phase 1 spec), so manual `wrangler dev` + `curl`
  verification is the actual test cycle — don't skip it.
- **`code-review` / `simplify`** — run on the diff before committing non-trivial changes.
- **`ponytail`** (pending install — see below) — YAGNI/minimal-diff discipline. Useful
  everywhere in this repo since the whole design system is built on "don't add what
  isn't asked for."

### Pending

- `ponytail` (github.com/DietrichGebert/ponytail) isn't installed yet — the user needs
  to run `/plugin marketplace add DietrichGebert/ponytail` then `/plugin install
  ponytail@ponytail` themselves (two separate prompts). Once it shows up in the skill
  list, treat it as always-relevant for this repo.
