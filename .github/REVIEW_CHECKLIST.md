# Review checklist

Use for every substantive PR. Dependabot PRs use the
batch rules instead (green pins per repo, majors
individually, never a bulk merge).

1. **Diff read, not title read.** Open the files
   endpoint. Confirm what changed vs what the body
   claims.
2. **Correctness.** Does the change do what it says,
   on the paths that matter? Check callers, defaults,
   and error paths.
3. **Security.** No secrets in the diff. No unsafe
   defaults. No fail-open on missing or corrupt
   config. No unauthenticated actor claims. No binds
   beyond tailnet. No new network or privilege
   surface without a note.
4. **Fail-closed test.** Delete or corrupt the
   config, empty the env var, refuse the socket —
   what happens? It must fail closed, never open.
5. **Tests test the change.** Does the test fail
   without the fix and pass with it? Mock-only
   tests must say so and defer real execution to a
   named release gate.
6. **Docs and consistency.** README and docs updated
   with the code. Links resolve. Version bumps match
   the repo template and main's version at merge
   time, not review time.
7. **Doctrine.** No Clearview or cleargeo. No flood
   or resilience content in public material
   (internal rule only, never stated publicly). No
   surveillance messaging. No public line promising
   play has no Observatory connection while telemetry
   flows. ZQM unexplained. For portal or admin
   material, confirm public vs internal scope first.
8. **CI split, stated separately.** Test vs scan vs
   other, each on the exact head. Scan red on the
   pre-existing clone or tzdata cause is not a diff
   verdict; a new scan cause is.
9. **Mergeability at merge time, not review time.**
   Re-verify head and mergeable immediately before
   merging. Mergeable flips have been observed.

A merge via API with 0 reviews is not a review.
Report it as "merged under the standing
authorization, 0 reviews", never as "reviewed".
