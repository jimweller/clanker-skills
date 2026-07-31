# Stack Layout Reference

Exact files, paths, and mappings the Quiver bolt expects from the three-layer
bootstrap. These are what the bolt entrypoint reads at startup, so the builder
output matches them precisely.

## Files the bolt reads

### Layer 1: bootstrap repo (public)

- `bootstrap.age` at the repo root. Age-encrypted tarball, decrypted with the
  bolt's `AGE_KEY`, extracted into `$HOME`.
- The tarball contains:
  - `.ssh/<key>` and `.ssh/<key>.pub` (SSH keypair)
  - `.ssh/config` whose `IdentityFile` names `<key>`
  - `.ssh/known_hosts` (from `ssh-keyscan`)
  - `.secrets/dotfiles.env` exporting `DOTFILES_KEY`
- After extraction the bolt re-applies `chmod 600` to `.ssh/id*` and `.secrets/*`,
  so host-side file permissions do not affect correctness. If `.ssh/config`
  exists, the bolt verifies GitHub auth with `ssh -T`.

### Layer 2: dotfiles repo (private or public)

- `install.conf.yaml` (dotbot config). The bolt clones a pinned dotbot and runs
  `dotbot -d <dotfiles> -c install.conf.yaml`. If an executable `install` script
  is present instead, the bolt runs that.
- `scripts/secrets.sh` with an `open` subcommand. When `DOTFILES_KEY` is set, the
  bolt runs `bash scripts/secrets.sh open`, which GPG-decrypts
  `manifests/secrets.gpg` and extracts it into `$HOME`.
- `manifests/secrets.gpg` (GPG symmetric AES256 archive of `.secrets/*.env`).
- `bashrc` (linked to `~/.bashrc` by dotbot) sources `~/.secrets/*.env` at shell
  start.

### Layer 3: workspace repo (private or public)

- Cloned into the fixed path `/workspace`. `git_branch` selects the branch.

### Re-bootstrap sentinel

- The bolt writes `$HOME/.quiver-bootstrapped` after a successful run. On restart
  with a persistent home volume, it skips all layers. Delete the sentinel to force
  a re-bootstrap.

## bolt.yaml to bolt runtime

Repo URLs travel inside one base64 `BOLT_CONFIG` env var; only the age key is
delivered separately, via a Kubernetes Secret as `AGE_KEY`.

| bolt.yaml field   | Constraint                                  | Reaches the bolt as    |
| ----------------- | ------------------------------------------- | ---------------------- |
| `mode`            | `terminal` or `job`                         | `BOLT_CONFIG`          |
| `shell`           | `/bin/bash` or `/bin/zsh`                   | `BOLT_CONFIG`          |
| `bootstrap_repo`  | must match `^https://`                      | `BOLT_CONFIG`          |
| `dotfiles_repo`   | SSH (`git@host:org/repo.git`) or HTTPS      | `BOLT_CONFIG`          |
| `workspace_repo`  | SSH or HTTPS                                | `BOLT_CONFIG`          |
| `git_branch`      | branch name                                 | `BOLT_CONFIG`          |
| (age private key) | `AGE-SECRET-KEY-[A-Z0-9]+`, sent separately | `AGE_KEY` (K8s Secret) |

Unknown top-level fields are rejected. Resource caps: 6 CPU, 24Gi memory, 60Gi
ephemeral storage. See the hosted `/docs/bolt-config` for the full schema.

## Partial configurations

All layers are optional.

| Bootstrap | Dotfiles     | Workspace   | Result                                          |
| --------- | ------------ | ----------- | ----------------------------------------------- |
| none      | none         | none        | bare bolt                                       |
| none      | none         | HTTPS repo  | public workspace cloned to `/workspace`         |
| none      | public HTTPS | none        | public dotfiles installed, no secrets decrypted |
| yes       | private SSH  | none        | bootstrap plus dotfiles, no workspace           |
| yes       | private SSH  | private SSH | full three-layer stack                          |

SSH URLs require Layer 1 to supply the SSH key. HTTPS URLs work without a
bootstrap repo.

## Rotating secrets

New bolts clone the repos fresh and pick up changes; existing bolts do not.

- GPG secrets changed (values in `mysecrets.env`): rebuild and push the dotfiles
  repo's `manifests/secrets.gpg`.
- SSH key rotated or `DOTFILES_KEY` changed: rebuild and push the bootstrap repo's
  `bootstrap.age`. If `DOTFILES_KEY` changed, also re-encrypt `secrets.gpg` with
  the new passphrase and push the dotfiles repo.

Re-running `build-stack.mjs` with the same `--work-dir` and inputs rebuilds both
archives. Push the repos whose contents changed.
