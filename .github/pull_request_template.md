## What this changes (files + behavior, not just intent)

## Why (issue/decision link, or "standalone")

## Tests

What runs, what it proves, and what it does NOT prove
(including mock limits — mock-only tests must say so).

## CI on exact head

Test: ___ / Scan: ___ / Other: ___.
Name pre-existing reds instead of hiding them.

## Risks and fail-closed behavior

Empty config, missing env var, refused socket, corrupt
input — what happens? Nothing here fails open.

## Doctrine check

- Clearview: no
- Flood/resilience content in public material: no
  (internal rule only, never stated publicly)
- Surveillance or telemetry messaging: no
- No public line promising play has no Observatory
  connection while telemetry flows
- ZQM unexplained: yes

## Deploy / follow-up

Node deploy queued? Pin bump needed? Rebase needed
after another PR merges?

## Blockers

Decision needed from ___ / draft until ___
