# Architecture Decision Records

Short records of non-obvious decisions and the reasoning behind them, so the
reasoning doesn't have to be re-derived (or re-litigated) later. Format:
[Michael Nygard's ADR template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
(Title / Status / Context / Decision / Consequences).

All four below are **retroactive** — written 2026-08-25 by reading the git
history and existing code rather than at decision time, since none existed
before. Where the reasoning is directly evidenced by a commit message, that's
quoted; where it's inferred from the resulting design, it's marked as such.
Treat them as a best-effort reconstruction, not a verbatim record.

| # | Decision |
|---|---|
| [0001](0001-one-project-per-networking-library.md) | One Unity project per networking library, not one project with a scene/assembly per variant |
| [0002](0002-shared-benchmark-base-package.md) | Extract common benchmark logic into a shared UPM package instead of duplicating it per project |
| [0003](0003-phase-based-workload-shape.md) | Three-phase workload (setup → spawn → move) instead of one continuous scenario |
| [0004](0004-dual-analysis-pipelines.md) | Two independent statistical pipelines (per-frame and load-based) instead of one |

To add a new one: copy the closest existing file, give it the next number,
and add a row above.
