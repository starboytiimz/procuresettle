# ForgeGuard

**ForgeGuard is a pull-request security and supply-chain malware scanner.**
It runs entirely on GitHub Actions with the repository's `GITHUB_TOKEN`.

ForgeGuard scans open pull requests for supply-chain malware patterns (such as PolinRider / GhostAction indicators) and publishes commit status checks (`ForgeGuard / malware-scan`) and PR comments.

> **Scan-only mode is active.** ForgeGuard scans every PR, publishes `ForgeGuard / malware-scan` and posts sticky findings comments, but it leaves merging to maintainers. This ensures GitHub issue linking (`Closes #N`) and Drips contributor issue completion credits are properly preserved.

## What the scan looks for

`scripts/forgeguard/scan-pr.sh BASE HEAD` checks the PR's changes since its merge base. It reports paths and line numbers only, never file content.

**BLOCK** — malware patterns. Status `ForgeGuard / malware-scan` fails:
- Anything `scripts/check-repo-hygiene.sh` rejects over the whole head tree:
  - Editor/IDE and devcontainer configs (`.vscode/`, `.cursor/`, `.idea/`, `.devcontainer/`), except `.vscode/extensions.json` recommendations and the exact reviewed Soroban configuration at `.vscode/settings.json`;
  - Disguised fonts or native binaries (`.woff2`, `.eot`, `.exe`, `.bat`, etc.);
  - npm lifecycle scripts (`preinstall`, `install`, `postinstall`, etc.);
  - Auto-run task settings (`allowAutomaticTasks`, `folderOpen`).
- Binary files (other than image assets), symlinks, and git submodules.
- Trojan Source characters (bidirectional Unicode controls, zero-width spaces).
- Code hidden after long runs of whitespace.
- `eval`/`Function` applied to `atob`, `Buffer.from`, or base64 decoders.
- npm packages resolved from outside `registry.npmjs.org`, or git/URL package sources.
- Cargo dependencies from git repositories or alternative registries.

**REVIEW** — sensitive changes requiring manual maintainer inspection:
- `.github/` workflows or automation changes;
- Cargo build scripts (`build.rs`), build dependencies, or proc macros;
- Large base64 blobs or unusually long lines (Soroban contract specs starting with `AAAA` are exempt);
- Script changes, new executables, or curl piped into shells.

## How it runs

- **In CI**: `scripts/check-repo-hygiene.sh` runs as a gate in `.github/workflows/ci.yml`.
- **In ForgeGuard**: `.github/workflows/forgeguard.yml` runs on CI completion, on PR approval, every 30 minutes, or manually via `workflow_dispatch`.
- PR code is never checked out or executed by ForgeGuard: heads are read directly from git objects.

## Running locally

```bash
# Verify repository hygiene
bash scripts/check-repo-hygiene.sh

# Scan a branch against main
bash scripts/forgeguard/scan-pr.sh main my-branch

# Run scanner regression tests
bash scripts/forgeguard/test-scan.sh
```
