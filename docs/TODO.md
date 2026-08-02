# TODO

Running list of open items across the project. Add to this as new gaps show up;
remove/check off as they're resolved. See [`docs/HANDOFF.md`](HANDOFF.md) for the
full spec and [`docs/HANDOFF.md#6-체크포인트-질문`](HANDOFF.md#6-체크포인트-질문)
for the always-ask-first checklist (separate list, don't merge into this one).

## Blocking / needs a decision from the user

- [ ] **Production domain not chosen.** `worker/wrangler.toml`'s `routes` and
      `SITE_URL` use the literal placeholder `<YOUR_DOMAIN>` — must be filled in
      before `wrangler deploy` (local dev doesn't need it).
- [ ] **ponytail plugin not installed.** User needs to run
      `/plugin marketplace add DietrichGebert/ponytail` then
      `/plugin install ponytail@ponytail` (two separate prompts) themselves.

## Phase 1 (in progress)

- [ ] Execute `docs/superpowers/plans/2026-08-02-blog-phase1-foundation.md`
      (subagent-driven vs. inline execution choice still pending as of this writing).

## Designed but deferred (not in Phase 1)

- [ ] **Figure block auto-layout.** `exBlog.html`'s figure is hand-tuned SVG
      coordinates; the real renderer needs a grid-based auto-layout for
      `flow`/`compare`/`stack`, a node "emphasis" field (not in the current JSON
      schema draft), and label-wrapping rules. See `docs/HANDOFF.md` §2.3, §7.
- [ ] **Post detail page template.** Nothing in `pages/` renders
      `content_html` yet — need an article shell (`article-header`,
      `article-body`) plus the code-block/terminal/figure CSS from
      `exBlog.html` wired to real Prism token classes (see Phase 1 plan's
      code-block task for the class names the Worker actually emits).

## Future phases (not yet spec'd — each needs its own brainstorming → spec → plan)

- [ ] Review dashboard (`/admin/review*` — draft list, approve/edit/reject)
- [ ] Paper recommendation cron — spec already written, see
      `docs/superpowers/specs/2026-08-02-papers-pipeline-design.md` (arXiv +
      OpenReview + Semantic Scholar, top-tier filtering, deep analysis on top-N,
      draft generation). Still needs a `writing-plans` pass before implementation.
      **Content must follow the same code/terminal/figure component rules as
      manual posts**, not a separate format (see `docs/HANDOFF.md` §7).
- [ ] GitHub webhook → commit-based draft generation
- [ ] `POST /api/drafts` (manual memo/link → draft)
- [ ] R2 image upload flow
- [ ] RAG-based paper search + admin login + related vector DB
