# Release-history concurrency and external-anchor contract

## Status and scope

This contract applies to every present or future ZQM Observatory node that writes, mirrors, verifies, or consumes release-history evidence. Each node must carry locally provisioned trust-root configuration and a cached, independently obtained signed checkpoint (with freshness metadata), and must refresh/verify that checkpoint before accepting a release decision. The repository currently documents and tests local tooling; it does not claim that a distributed node fleet or independent anchoring service is deployed.

A hash-linked JSONL file is useful for detecting accidental edits and broken links, but it is not by itself an independent trust anchor. A node must not treat a checkpoint stored only beside the writable history as independent evidence.

## Mandatory node material

Every participating node must have access to, and verify before accepting a release decision:

1. **Trust roots:** explicitly configured trusted public keys, key fingerprints, allowed signature algorithms, and a documented key-rotation/revocation process. Do not trust a key merely because it appears in the attestation being checked.
2. **Independent checkpoint:** the most recently accepted checkpoint obtained from a separate trust or administrative domain. It must bind a stable history identifier, sequence number, and exact entry SHA-256. A local copy of the same writable JSONL file does not qualify.
3. **Checkpoint signer identity:** the anchoring service/node identity, its trusted public-key fingerprint, the checkpoint signature, and a timezone-aware observation/issuance timestamp. The signed bytes must use a documented canonical encoding.
4. **Freshness and rollback policy:** a maximum checkpoint age appropriate to the release cadence, a monotonic sequence rule, and a fail-closed response to missing, stale, unverifiable, or regressed checkpoints.
5. **Recovery material:** a separately controlled backup of the checkpoint and trust configuration, plus a documented restoration and key-compromise procedure.

Nodes must pin trust roots and anchor checkpoints through controlled configuration/provisioning—not accept replacement trust roots from an untrusted history, attestation, product bundle, or peer response.

## Required verification order

For every release-history read or write:

1. Acquire the history writer lock before reading the current head or deciding the next sequence.
2. Validate the complete history chain and each referenced attestation hash.
3. Verify every attestation signature against an explicitly trusted key and verify its signed manifest/evidence bundle.
4. Compare the local chain head with the latest independently obtained, signature-verified checkpoint. The local history must contain the checkpointed sequence and match its entry hash exactly. A shorter history, different hash at the checkpointed sequence, stale checkpoint, or missing anchor blocks acceptance.
5. For a proposed new release, append atomically under the lock, verify the resulting full chain, then submit the new sequence/head hash to the independent anchor service.
6. Treat the new release as externally anchored only after the anchor service returns a verifiable signed checkpoint. If anchoring fails, preserve the local evidence but report **ANCHOR PENDING / BLOCKED**; do not claim independent tamper evidence or publication readiness.

A checkpoint ahead of the local history is not permission to reconstruct or rewrite history silently. Restore from a trusted replica or investigate the discrepancy. A fork or mismatch requires an explicit incident/reconciliation record.

## Concurrency contract

All writers targeting the same history path must use the same stable sidecar lock path and an OS-level inter-process lock. Hold the lock across the entire read–validate–sequence–write–replace transaction. Do not delete the sidecar lock file during routine operation: removing it can allow different processes to lock different file inodes and write concurrently.

Atomic replacement remains necessary but is not a substitute for the lock. All writer implementations and supported operating systems must have concurrent-writer regression tests. If history resides on a network filesystem, verify its locking semantics or route writes through one serialized service; do not assume local filesystem locks are reliable across all mounts.

## Trust-domain separation

The external checkpoint must be stored or signed outside the administrative boundary that can rewrite the history and its attestations. Suitable deployment designs include a separately permissioned append-only checkpoint service, an independently administered repository, or a protected object-lock/WORM store. These are design options, not claims about current deployment.

A signed checkpoint proves that the anchor signer endorsed a specific history head. It does not prove that the underlying source license permits reuse, that the data is accurate, or that publication was approved.

## Operational checklist

- [ ] Every node declares its node ID, history ID, trusted-key fingerprints, checkpoint source, freshness limit, and rollback policy.
- [ ] Each node can validate a checkpoint without trusting the writable history directory.
- [ ] Checkpoint state is backed up and restored in a clean-host exercise.
- [ ] Concurrent append tests pass on every supported OS and storage backend.
- [ ] A failed anchor submission remains explicitly pending/blocked.
- [ ] A tampered, truncated, forked, stale, or unanchored history fails closed.
- [ ] Release authorization remains separate from technical signature and hash validation.

Until an independent anchor service and per-node trust provisioning are implemented and exercised, this document is a required architecture contract—not evidence that external anchoring is already operational.

## Offline checkpoint verifier (implemented; anchoring service not deployed)

`scripts/verify_history_checkpoint.py` verifies a checkpoint envelope with exactly two fields: `payload` and base64 `signature`. The payload uses schema version 1 and binds the stable `history_id`, positive `sequence`, exact `entry_sha256`, timezone-aware `issued_at`, `issuer`, the `Ed25519` algorithm, and the SHA-256 fingerprint of the signing public key's DER SubjectPublicKeyInfo encoding. The signature covers the repository's canonical JSON encoding of the entire payload, including a final LF.

Example:

```sh
python -m pip install -r requirements-security.txt
python scripts/verify_history_checkpoint.py \
  --history data/release-history.jsonl \
  --checkpoint /securely-delivered/checkpoint.json \
  --public-key /etc/zqm/trust/anchor-ed25519-public.pem \
  --history-id zqm-observatory-production \
  --max-age-seconds 86400 \
  --minimum-sequence 42
```

Use the real history path, history identifier, independently delivered checkpoint, trusted public key, and protected state path for the deployment. The example paths are illustrative. With `--state-file`, the verifier locks a persistent sidecar, validates the checkpoint against the previously accepted sequence, history ID, signer fingerprint and same-sequence hash/timestamp, then atomically records the new high-water mark only after successful verification. Existing malformed state fails closed and must be recovered from a separately trusted backup; do not delete it to bypass a failure. Without `--state-file`, `--minimum-sequence` is only a caller-supplied floor and is not persistent.

The verifier rejects malformed payloads, untrusted-key fingerprint mismatch, invalid signatures, stale or implausibly future timestamps, sequence regression, history-ID mismatch when configured, checkpoints ahead of local history, and a local chain whose checkpointed entry hash differs. `--state-file` adds locked, atomic local high-water persistence; it does not make that state independently durable against an administrator who can replace both history and state. The verifier does not retrieve checkpoints, provision trust roots, contact an anchor service, or prove the checkpoint came from an independent administrative domain. Those integrations remain required before any release can be considered externally anchored. Missing checkpoint/key configuration or verifier failure must block release acceptance.

## Checkpoint issuer (implemented; deployment remains separate)

`scripts/create_history_checkpoint.py` creates a signed checkpoint from a fully validated, non-empty local history. It requires an explicitly supplied Ed25519 private-key PEM, stable history ID, issuer identity, and a new output path. It refuses to overwrite an existing checkpoint and does not generate or provision keys. Keep the private key only in the separately controlled anchor trust domain; never place it beside a history directory writable by untrusted release processes.

Example run inside that separately controlled domain:

```sh
python scripts/create_history_checkpoint.py \
  --history /trusted-ingest/release-history.jsonl \
  --private-key /secure/anchor/ed25519-private.pem \
  --output /checkpoint-export/checkpoint-000042.json \
  --history-id zqm-observatory-production \
  --issuer zqm-independent-anchor-01
```

Deliver the resulting checkpoint and the corresponding public key through independently controlled channels. Verify it on the consuming node with `scripts/verify_history_checkpoint.py`, using that node's separately provisioned trust root and persisted high-water mark. This issuer is a CLI, not a hosted service; running it on the same machine and under the same administrator as the mutable history does not establish independence. Private-key custody, independent delivery, durable high-water storage, key rotation/revocation, and clean-host restoration still require deployment-specific implementation and tests.
