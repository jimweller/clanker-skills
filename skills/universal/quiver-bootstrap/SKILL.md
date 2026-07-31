---
name: quiver-bootstrap
description: Set up a Quiver bolt's three-layer bootstrap stack (public bootstrap repo, private dotfiles repo, private workspace repo, an age key, and an SSH key) and create the bolt. Use when a user wants to configure a new Quiver persona or dotfiles stack, onboard to Quiver, or spin up a bolt dev environment from scratch. Works on macOS, Linux, and Windows.
---

# Quiver Bootstrap Stack

Configure the three-layer bootstrap that turns a bare Quiver bolt into a
personalized dev environment. This skill scaffolds and encrypts the three repos,
produces a `bolt.yaml`, and hands off the exact command to create the bolt.

## Quiver in brief (end-user view)

- A **bolt** is an ephemeral Ubuntu container running in Kubernetes with a
  persistent home and workspace. Reach it via a browser terminal, VSCode, or
  `kubectl`.
- A fresh bolt has no SSH keys, dotfiles, or code. The **three-layer bootstrap**
  delivers them at startup from three git repos plus one age key.
- The bootstrap repo plus the dotfiles repo form a reusable **persona**. The
  workspace repo is the swappable per-task input. Rebuilding a bolt from the same
  inputs reproduces the same environment.

| Layer | Repo      | Visibility | Delivers                                  |
| ----- | --------- | ---------- | ----------------------------------------- |
| 1     | bootstrap | public     | SSH key, SSH config, `DOTFILES_KEY` (age) |
| 2     | dotfiles  | private    | dotbot install, GPG-decrypted secrets     |
| 3     | workspace | private    | project code cloned into `/workspace`     |

The bootstrap repo is public but safe: its `bootstrap.age` payload is
age-encrypted, and the dotfiles repo's `secrets.gpg` is GPG-encrypted.

## Prerequisites

The bundled builder needs `node`, `age`, `age-keygen`, `gpg`, `git`,
`ssh-keygen`, and `tar` on PATH. Adding `--push` also needs `gh`.

Run the preflight first and stop if anything is missing:

```bash
node scripts/build-stack.mjs --check
```

Install hints by OS:

- macOS: `brew install age gnupg git openssh` (and `brew install gh`)
- Linux: `apt install age gnupg git openssh-client` (or the distro equivalent)
- Windows: `winget install FiloSottile.age GnuPG.GnuPG Git.Git` (ssh and tar ship
  with Windows 10+; `winget install GitHub.cli` for `gh`)

## Build the stack

1. Confirm inputs with the user: the GitHub org or user, the three repo names
   (defaults `bootstrap`, `dotfiles`, `workspace`), the login shell, and any
   secret env vars to embed. Ask before choosing values.
2. Run the builder. Use `--dry-run` first to inspect artifacts without touching
   the network:

   ```bash
   node scripts/build-stack.mjs --org <github-org> --dry-run
   ```

3. Run for real to build the artifacts under `~/quiver-bootstrap` (override with
   `--work-dir`):

   ```bash
   node scripts/build-stack.mjs --org <github-org> \
     --shell /bin/bash \
     --secret MY_API_TOKEN=xxxxx
   ```

   Add `--push` to create and push all three repos with `gh` and register the
   generated SSH public key with GitHub. Without `--push`, the builder prints the
   exact `gh`/`git` commands to run.

The builder writes the age private key to `age-key.txt` and prints it once. It is
the single secret the user must keep. It is never committed.

Key flags: `--work-dir`, `--org`, `--bootstrap-repo`, `--dotfiles-repo`,
`--workspace-repo`, `--git-host`, `--shell`, `--ssh-key` (reuse an existing key),
`--dotfiles-key`, `--secret KEY=VALUE` (repeatable), `--dotfiles-public`,
`--workspace-public`, `--push`, `--dry-run`. Run `--help` for the full list.

## Create the bolt

The builder prints a ready-to-run command:

```bash
quiver create <name> --config ~/quiver-bootstrap/bolt.yaml \
  --age-key "AGE-SECRET-KEY-..."
```

If the user has no CLI set up, the `quiver-cli` skill covers install and auth, or
they can create the bolt from the dashboard by uploading `bolt.yaml` and pasting
the age key.

## Verify

Once the bolt is `ready`, open its terminal and confirm each layer:

```bash
env | grep MY_SECRET          # Layer 2: GPG secrets decrypted and sourced
cat /workspace/README.md      # Layer 3: workspace cloned
```

## Guardrails

- `bootstrap_repo` must be an `https://` URL. The bolt clones it without
  credentials, so that repo must be public.
- Private dotfiles and workspace repos are cloned over SSH (`git@host:org/repo.git`)
  using the key delivered by Layer 1. Register the SSH public key with the git
  host or the private clones fail.
- The `.ssh/config` `IdentityFile` must name the same key file shipped in the
  bootstrap tarball. The builder keeps these aligned.
- All layers are optional. See `reference/stack-layout.md` for partial
  configurations and the exact files the bolt expects.

## Rotating later

New bolts pick up repo changes automatically; existing bolts do not. To rotate,
rebuild with the same inputs and push. See `reference/stack-layout.md`.

## Installing this skill

```bash
npx skills add ./skills/quiver-bootstrap          # from a local checkout
npx skills add <your-quiver-repo-git-url>         # from the hosted repo
```

Add `-g` for a global install and `-a claude-code` (or another agent) to target a
specific agent.
