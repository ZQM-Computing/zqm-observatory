# Frontend dependency audit — November 17, 2026

**Status: remediation implemented; clean-install/full-audit CI verification pending.**
The existing high-severity merge/release gate remains in force. This record
preserves the original finding and tracks its remediation. No audit exclusions
or dependency downgrades are used.

Before remediation, `npm audit --audit-level=high` reported four high-severity dependency entries from
one advisory, [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)
(CVE-2026-112366). It concerns regular-expression denial of service for crafted
extglob patterns in picomatch through 4.0.7. The advisory was updated on
November 17 and lists no patched version.

| Previous dependency | Relationship | Original audit result |
| --- | --- | --- |
| `picomatch@4.0.7` | Used by Vite and file traversal helpers | Direct advisory finding |
| `fdir@6.5.0` | Depends on picomatch | Transitive high-severity entry |
| `tinyglobby@0.2.17` | Depends on fdir/picomatch | Transitive high-severity entry |
| `vite@8.3.4` | Development/build dependency | Transitive high-severity entry |

The original runtime-only audit reported zero findings, which did not clear the
full gate. At investigation time, picomatch's latest tag was 4.0.7 and Vite 8.3.8
still declared picomatch `^4.0.7` and tinyglobby `^0.2.17`. A compatible published
fix was not found.

## Reproduce

From `apps/map-explain`:

```sh
npm audit --audit-level=high
npm audit --omit=dev
npm ls picomatch fdir tinyglobby vite --all
```

## Remediation and runner evidence

The app now uses its existing Rolldown 1.2.19 backend directly and Lightning CSS
1.32.0 for CSS parsing/minification. Vite, its React/Tailwind wrappers, Picomatch,
fdir and tinyglobby have been removed from the dependency graph. The prior
Tailwind reset/theme/utility output is plain CSS with its MIT license retained.
No JavaScript matcher is vendored and no finding is suppressed. The production
app keeps strict script CSP, local hashed assets and the shell-only offline cache.

The original Windows job required a self-hosted runner and had no runner assigned.
The public repository now uses the standard hosted `windows-2022` runner, with
Python 3.12 explicitly installed. Same-repository execution, read-only permissions,
locked installation without lifecycle scripts, full audit and functional checks
remain. Private repositories retain the existing self-hosted pool.

The [first hosted run](https://github.com/ZQM-Computing/zqm-observatory/actions/runs/44189578959)
ran its tests and build, then reproduced the audit failure. This confirms the
runner-routing repair separately from the dependency remediation.

Local checks pass: 85 app/tooling tests and production builds on Node 22 and 24,
17 Python/GIS service tests, and real proxy-to-service durable sync/full-size
upload checks. Browser QA verified the new assets, five panels, the expected
synthetic question result, retained local records and reload with the origin
stopped. The original source/publication gates remain unchanged.

A clean Windows locked install and `npm audit --audit-level=high` must complete
successfully before merge/release. No production deployment is included.
