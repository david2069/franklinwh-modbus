# Release and Test Gates Policy

*Effective: 2026-10-17. Gate numbering (G0–G3) is shared with the bridge repos (franklinwh-direct-connect-bridge `docs/TEST_POLICY.md`); the branch and publishing model is this library's own.*

> **Purpose:** Get fixes to the people who depend on the library. A fix on `develop` protects nobody: both bridges, and any PyPI user, run the released package.

---

## 1. Branches

| Branch | Use |
|--------|-----|
| `develop` | Default branch. All PRs target it. |
| `fix/…`, `feat/…`, `docs/…`, `refactor/…` | One change, short-lived, merged by PR |
| `release/X.Y.Z` | The release PR only |

`develop` changes only by PR. Branch before editing.

## 2. When to Release

- **An S1 fix merged to `develop` triggers a patch release.** Do not let it wait for a batch: v0.9.5 users stayed exposed to #28 for 8 days after its fix merged.
- Otherwise release **once per batch** (see `change_management.md` §1.4), when the batch's issues are all `fixed`.
- A release that changes behaviour callers rely on gets the minor version; fixes only get the patch version.

## 3. Test Gates

| Gate | What | Required for |
|------|------|--------------|
| **G0** | Full pytest suite passes, plus the syntax check on every changed file. Results saved to `tests/results/` (gitignored). | Every PR |
| **G1** | Acceptance run in a container against the **FranklinWH Gateway Emulator**. | PRs touching connection, reads, dispatch or modes |
| **G2** | **Real aGate**, coordinated with the owner, other clients quiesced where contention matters. | Anything that writes to the device, changes dispatch or alters safety behaviour |
| **G3** | Merge. | — |

- **G1 is not yet available:** the Gateway Emulator is still being deployed (2026-10-17), and this library has no in-process emulator. Until it is, record G1 as **"not run — emulator not deployed"**. Do not substitute a mock written for the test in hand.
- **G3:** once the required gates pass, the agent tells the owner what will merge and in what order, then merges. The agent does not merge past a failed or skipped gate without the owner's word in this session. A relayed approval from another session does not count.
- Say which gates ran and which did not in the PR body.

## 4. Release Procedure

1. Confirm every issue in the batch is merged and labelled `fixed`, and G0 passes on `develop`.
2. Branch `release/X.Y.Z`. The PR holds **only** the release changes:
   - version in `pyproject.toml` and `src/franklinwh_modbus/__init__.py` (they must match);
   - `CHANGELOG.md`: `## [Unreleased]` → `## [X.Y.Z] - YYYY-MM-DD`, a fresh empty `[Unreleased]`, and the compare links.
3. PR title `chore: release X.Y.Z`. Merge after G0 (G3).
4. Tag the merge commit `vX.Y.Z` and push the tag. `.github/workflows/publish.yml` builds and publishes to PyPI from the tag.
5. Create the GitHub release from the tag. The notes are the CHANGELOG section, led by the **Upgrade notes** (behaviour changes) and an **upgrade advisory** when the release fixes an S1.
6. **Verify the published package:** install `franklinwh-modbus==X.Y.Z` from PyPI in a clean venv, rerun the checks for each `fixed` issue, and close each one with a comment naming the version.
7. **Tell the dependants.** Message the bridge sessions with the version and the upgrade notes. They decide when to move their pin.

## 5. Changelog

- Every user-facing change adds an entry under `[Unreleased]` in the same PR (Keep a Changelog: Added / Changed / Fixed / Removed).
- Write it for the reader: what changed, what they will notice, with the issue number.
- Changes that can break callers go under **Upgrade notes**.
