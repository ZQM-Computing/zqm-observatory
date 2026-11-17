# Frontend dependency audit — November 17, 2026

**Status: application merge/release blocked by the existing high-severity audit gate.**
This record supersedes the earlier clean frontend audit in the verification
history. The dependency finding is unresolved; functional checks do not clear
it. No audit exclusion, forced dependency downgrade, or gate change is included.

`npm audit --audit-level=high` reports four high-severity dependency entries from
one advisory, [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)
(CVE-2026-112366). It concerns regular-expression denial of service for crafted
extglob patterns in picomatch through 4.0.7. The advisory was updated on
November 17 and lists no patched version.

| Installed dependency | Relationship | Audit result |
| --- | --- | --- |
| `picomatch@4.0.7` | Used by Vite and file traversal helpers | Direct advisory finding |
| `fdir@6.5.0` | Depends on picomatch | Transitive high-severity entry |
| `tinyglobby@0.2.17` | Depends on fdir/picomatch | Transitive high-severity entry |
| `vite@8.3.4` | Development/build dependency | Transitive high-severity entry |

The runtime-only command `npm audit --omit=dev` reports zero findings. That result
does not clear the full audit gate. Package-registry checks show picomatch's latest
tag remains 4.0.7; the available Vite 8.3.8 patch still declares picomatch `^4.0.7`
and tinyglobby `^0.2.17`. A compatible published fix was not found.

## Reproduce

From `apps/map-explain`:

```sh
npm audit --audit-level=high
npm audit --omit=dev
npm ls picomatch fdir tinyglobby vite --all
npm view picomatch dist-tags --json
npm view vite@8.3.8 dependencies --json
```

The trusted Windows workflow retains `npm audit --audit-level=high`. Its runner
is separately queued; local audit failure is already confirmed. Before merging application code
or releasing, apply a verified compatible remediation, run a clean locked
install, rerun the full audit and functional checks, and complete the trusted CI
checks. No production deployment is part of this work.
