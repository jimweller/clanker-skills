#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  writeFileSync,
  readFileSync,
  copyFileSync,
  chmodSync,
  rmSync,
} from "node:fs";
import { join, basename } from "node:path";
import { homedir, platform } from "node:os";
import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";

const IS_WIN = platform() === "win32";

const REQUIRED_TOOLS = ["age", "age-keygen", "gpg", "git", "ssh-keygen", "tar"];

const INSTALL_HINTS = {
  darwin: "brew install age gnupg git openssh   (gh: brew install gh)",
  linux:
    "apt install age gnupg git openssh-client   (or dnf/pacman equivalents; gh: https://cli.github.com)",
  win32:
    "winget install FiloSottile.age GnuPG.GnuPG Git.Git   (ssh + tar ship with Windows 10+; gh: winget install GitHub.cli)",
};

function log(msg) {
  stdout.write(`${msg}\n`);
}
function warn(msg) {
  stdout.write(`! ${msg}\n`);
}
function fail(msg) {
  stdout.write(`x ${msg}\n`);
  process.exit(1);
}

function run(cmd, args, opts = {}) {
  const res = spawnSync(cmd, args, {
    cwd: opts.cwd,
    input: opts.input,
    encoding: "utf8",
    env: { ...process.env, ...(opts.env || {}) },
    stdio: opts.capture
      ? ["pipe", "pipe", "pipe"]
      : ["inherit", "inherit", "inherit"],
  });
  if (res.error) throw new Error(`failed to run ${cmd}: ${res.error.message}`);
  if (res.status !== 0) {
    const detail = res.stderr ? `: ${res.stderr.trim()}` : "";
    throw new Error(`${cmd} exited ${res.status}${detail}`);
  }
  return res.stdout || "";
}

function toolExists(name) {
  const probe = IS_WIN
    ? spawnSync("where", [name], { stdio: "ignore" })
    : spawnSync("/bin/sh", ["-c", `command -v ${name}`], { stdio: "ignore" });
  return probe.status === 0;
}

function chmod600(path) {
  if (!IS_WIN) chmodSync(path, 0o600);
}

function parseArgs(argv) {
  const flags = {};
  const bools = new Set([
    "check",
    "help",
    "dry-run",
    "push",
    "dotfiles-public",
    "workspace-public",
  ]);
  const secrets = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) continue;
    const key = a.slice(2);
    if (key === "secret") {
      secrets.push(argv[++i]);
      continue;
    }
    if (bools.has(key)) {
      flags[key] = true;
      continue;
    }
    flags[key] = argv[++i];
  }
  flags.secret = secrets;
  return flags;
}

function preflight(needGh) {
  const need = [...REQUIRED_TOOLS, ...(needGh ? ["gh"] : [])];
  const missing = [];
  for (const t of need) {
    const ok = toolExists(t);
    log(`${ok ? "ok " : "MISSING"}  ${t}`);
    if (!ok) missing.push(t);
  }
  if (missing.length) {
    log("");
    fail(
      `missing tools: ${missing.join(", ")}\n  install: ${
        INSTALL_HINTS[platform()] || INSTALL_HINTS.linux
      }`,
    );
  }
  log("\nall prerequisites present");
}

async function prompt(question, fallback) {
  if (!stdin.isTTY) {
    if (fallback !== undefined) return fallback;
    fail(`missing required value and no TTY to prompt: ${question}`);
  }
  const rl = createInterface({ input: stdin, output: stdout });
  const suffix = fallback ? ` [${fallback}]` : "";
  const answer = (await rl.question(`${question}${suffix}: `)).trim();
  rl.close();
  return answer || fallback || "";
}

const HELP = `build-stack.mjs - build a Quiver three-layer bootstrap stack

Usage:
  node build-stack.mjs --check
  node build-stack.mjs --org <github-org> [options]

Options:
  --check                 Run the prerequisite preflight and exit
  --org <name>            GitHub org or user that owns the three repos (required)
  --work-dir <path>       Output dir (default: ~/quiver-bootstrap)
  --bootstrap-repo <n>    Bootstrap repo name (default: bootstrap)
  --dotfiles-repo <n>     Dotfiles repo name (default: dotfiles)
  --workspace-repo <n>    Workspace repo name (default: workspace)
  --git-host <host>       Git host (default: github.com)
  --shell <path>          Bolt login shell: /bin/bash or /bin/zsh (default: /bin/bash)
  --ssh-key <path>        Reuse an existing SSH private key instead of generating one
  --dotfiles-key <pass>   GPG passphrase for secrets.gpg (default: random, printed)
  --secret KEY=VALUE      Add a secret env var (repeatable). Default: two demo values
  --dotfiles-public       Treat dotfiles repo as public (clone over HTTPS)
  --workspace-public      Treat workspace repo as public (clone over HTTPS)
  --push                  Create and push the three repos with gh (requires gh auth)
  --dry-run               Build artifacts locally, skip network and push
  --help                  Show this help

Output artifacts live under --work-dir. The age private key is written to
age-key.txt and printed once; keep it safe and never commit it.`;

function writeBashrc(shellPrompt) {
  return `${shellPrompt}\nfor f in ~/.secrets/*.env; do\n    [ -f "$f" ] && source "$f"\ndone\n`;
}

const INSTALL_CONF = `- defaults:
    link:
      force: true
      create: true
      relink: true

- create:
    - ~/.ssh
    - ~/.secrets

- link:
    ~/.bashrc: bashrc
`;

const SECRETS_SH = `#!/usr/bin/env bash
set -euo pipefail
BASEDIR="$(cd "$(dirname "$0")/.." && pwd)"

case "\${1:-}" in
    open)
        if [ -z "\${DOTFILES_KEY:-}" ]; then
            echo "ERROR: DOTFILES_KEY not set" >&2
            exit 1
        fi
        echo "$DOTFILES_KEY" | gpg --batch --decrypt --passphrase-fd 0 "\${BASEDIR}/manifests/secrets.gpg" | tar xzf - -C "$HOME"
        ;;
    *)
        echo "Usage: secrets.sh {open}" >&2
        exit 1
        ;;
esac
`;

function sshConfig(gitHost, keyName) {
  return `Host ${gitHost}
  HostName ${gitHost}
  User git
  IdentityFile ~/.ssh/${keyName}
  IdentitiesOnly yes
  StrictHostKeyChecking yes
  UserKnownHostsFile ~/.ssh/known_hosts
`;
}

function tarCreate(outFile, cwd, entries) {
  run("tar", ["czf", outFile, "-C", cwd, ...entries], {
    env: { COPYFILE_DISABLE: "1" },
  });
}

function gitInitCommit(dir, message) {
  run("git", ["init", "-q", "-b", "main"], { cwd: dir });
  run("git", ["add", "-A"], { cwd: dir });
  run(
    "git",
    [
      "-c",
      "user.name=quiver-bootstrap",
      "-c",
      "user.email=quiver-bootstrap@local",
      "commit",
      "-q",
      "-m",
      message,
    ],
    { cwd: dir },
  );
}

function parseSecrets(pairs) {
  if (!pairs.length) {
    return "export MY_SECRET_1=\"hello-from-layer2\"\nexport MY_SECRET_2=\"gpg-decrypt-worked\"\n";
  }
  return (
    pairs
      .map((p) => {
        const eq = p.indexOf("=");
        if (eq < 0) fail(`invalid --secret (want KEY=VALUE): ${p}`);
        const k = p.slice(0, eq);
        const v = p.slice(eq + 1);
        return `export ${k}="${v}"`;
      })
      .join("\n") + "\n"
  );
}

async function main() {
  const flags = parseArgs(process.argv.slice(2));

  if (flags.help) {
    log(HELP);
    return;
  }
  if (flags.check) {
    preflight(false);
    return;
  }

  preflight(Boolean(flags.push));
  log("");

  const dryRun = Boolean(flags["dry-run"]);
  const org = flags.org || (await prompt("GitHub org or user"));
  if (!org) fail("--org is required");

  const gitHost = flags["git-host"] || "github.com";
  const bootstrapRepo = flags["bootstrap-repo"] || "bootstrap";
  const dotfilesRepo = flags["dotfiles-repo"] || "dotfiles";
  const workspaceRepo = flags["workspace-repo"] || "workspace";
  const shell = flags.shell || "/bin/bash";
  if (!["/bin/bash", "/bin/zsh"].includes(shell))
    fail(`--shell must be /bin/bash or /bin/zsh, got ${shell}`);

  const workDir = flags["work-dir"] || join(homedir(), "quiver-bootstrap");
  const staging = join(workDir, "staging");
  const bootDir = join(workDir, bootstrapRepo);
  const dotDir = join(workDir, dotfilesRepo);
  const wsDir = join(workDir, workspaceRepo);

  for (const d of [
    workDir,
    staging,
    join(staging, "bootstrap", ".ssh"),
    join(staging, "bootstrap", ".secrets"),
    join(staging, "secrets", ".secrets"),
    join(bootDir),
    join(dotDir, "manifests"),
    join(dotDir, "scripts"),
    wsDir,
  ]) {
    mkdirSync(d, { recursive: true });
  }

  const ageKeyFile = join(workDir, "age-key.txt");
  let agePub;
  if (flags["age-key-file"]) {
    agePub = run("age-keygen", ["-y", flags["age-key-file"]], {
      capture: true,
    }).trim();
    copyFileSync(flags["age-key-file"], ageKeyFile);
  } else {
    run("age-keygen", ["-o", ageKeyFile]);
    agePub = run("age-keygen", ["-y", ageKeyFile], { capture: true }).trim();
  }
  const ageKeyText = readFileSync(ageKeyFile, "utf8");
  const ageSecretLine = ageKeyText
    .split(/\r?\n/)
    .find((l) => l.startsWith("AGE-SECRET-KEY-"));
  if (!ageSecretLine) fail("could not read AGE-SECRET-KEY from age key file");
  chmod600(ageKeyFile);
  log(`age key ready (public: ${agePub})`);

  const keyName = flags["ssh-key"]
    ? basename(flags["ssh-key"])
    : "id_quiver";
  const stageSshDir = join(staging, "bootstrap", ".ssh");
  const stageKey = join(stageSshDir, keyName);
  const stagePub = join(stageSshDir, `${keyName}.pub`);
  if (flags["ssh-key"]) {
    copyFileSync(flags["ssh-key"], stageKey);
    const pubSrc = `${flags["ssh-key"]}.pub`;
    if (existsSync(pubSrc)) copyFileSync(pubSrc, stagePub);
    else
      writeFileSync(
        stagePub,
        run("ssh-keygen", ["-y", "-f", stageKey], { capture: true }),
      );
  } else {
    run("ssh-keygen", [
      "-t",
      "ed25519",
      "-f",
      stageKey,
      "-N",
      "",
      "-C",
      "quiver-bootstrap",
      "-q",
    ]);
  }
  chmod600(stageKey);
  log(`ssh key ready (${keyName})`);

  const khPath = join(stageSshDir, "known_hosts");
  try {
    const kh = run(
      "ssh-keyscan",
      ["-t", "rsa,ecdsa,ed25519", gitHost],
      { capture: true },
    );
    if (!kh.trim()) throw new Error("ssh-keyscan returned no keys");
    writeFileSync(khPath, kh);
    log("known_hosts populated");
  } catch (e) {
    if (dryRun) {
      writeFileSync(khPath, `# ssh-keyscan skipped in dry-run for ${gitHost}\n`);
      warn(`ssh-keyscan skipped (dry-run): ${e.message}`);
    } else {
      throw new Error(
        `ssh-keyscan ${gitHost} failed (network required): ${e.message}`,
      );
    }
  }
  chmod600(khPath);

  const cfgPath = join(stageSshDir, "config");
  writeFileSync(cfgPath, sshConfig(gitHost, keyName));
  chmod600(cfgPath);

  const dotfilesKey =
    flags["dotfiles-key"] || randomBytes(24).toString("base64url");
  const dotfilesEnv = join(staging, "bootstrap", ".secrets", "dotfiles.env");
  writeFileSync(dotfilesEnv, `export DOTFILES_KEY="${dotfilesKey}"\n`);
  chmod600(dotfilesEnv);

  const bootTar = join(staging, "bootstrap.tar.gz");
  tarCreate(bootTar, join(staging, "bootstrap"), [".ssh", ".secrets"]);
  run("age", ["-r", agePub, "-o", join(bootDir, "bootstrap.age"), bootTar]);
  log("layer 1: bootstrap.age built");

  const shellPrompt =
    "PS1='\\[\\e[32m\\]bolt\\[\\e[0m\\]:\\[\\e[34m\\]\\w\\[\\e[0m\\]\\$ '";
  writeFileSync(join(dotDir, "bashrc"), writeBashrc(shellPrompt));
  writeFileSync(join(dotDir, "install.conf.yaml"), INSTALL_CONF);
  const secretsSh = join(dotDir, "scripts", "secrets.sh");
  writeFileSync(secretsSh, SECRETS_SH);
  if (!IS_WIN) chmodSync(secretsSh, 0o755);

  writeFileSync(
    join(staging, "secrets", ".secrets", "mysecrets.env"),
    parseSecrets(flags.secret),
  );
  const secretsTar = join(staging, "secrets.tar.gz");
  tarCreate(secretsTar, join(staging, "secrets"), [".secrets"]);
  const passFile = join(staging, "dotfiles-key.txt");
  writeFileSync(passFile, dotfilesKey);
  run("gpg", [
    "--batch",
    "--yes",
    "--pinentry-mode",
    "loopback",
    "--passphrase-file",
    passFile,
    "--symmetric",
    "--cipher-algo",
    "AES256",
    "-o",
    join(dotDir, "manifests", "secrets.gpg"),
    secretsTar,
  ]);
  rmSync(passFile);
  log("layer 2: dotfiles repo + secrets.gpg built");

  writeFileSync(
    join(wsDir, "README.md"),
    "# Workspace\n\nIf this file is readable inside a bolt at /workspace/README.md, Layer 3 cloned this repo.\n",
  );
  log("layer 3: workspace repo built");

  const httpsBase = `https://${gitHost}/${org}`;
  const sshBase = `git@${gitHost}:${org}`;
  const bootstrapUrl = `${httpsBase}/${bootstrapRepo}`;
  const dotfilesUrl = flags["dotfiles-public"]
    ? `${httpsBase}/${dotfilesRepo}`
    : `${sshBase}/${dotfilesRepo}.git`;
  const workspaceUrl = flags["workspace-public"]
    ? `${httpsBase}/${workspaceRepo}`
    : `${sshBase}/${workspaceRepo}.git`;

  const boltYaml = `mode: terminal
shell: ${shell}
bootstrap_repo: "${bootstrapUrl}"
dotfiles_repo: "${dotfilesUrl}"
workspace_repo: "${workspaceUrl}"
`;
  const boltYamlPath = join(workDir, "bolt.yaml");
  writeFileSync(boltYamlPath, boltYaml);

  gitInitCommit(bootDir, "add bootstrap.age");
  gitInitCommit(dotDir, "add dotfiles and secrets");
  gitInitCommit(wsDir, "add workspace README");

  let pushed = false;
  if (flags.push && !dryRun) {
    pushRepo(org, bootstrapRepo, bootDir, "public", gitHost);
    pushRepo(
      org,
      dotfilesRepo,
      dotDir,
      flags["dotfiles-public"] ? "public" : "private",
      gitHost,
    );
    pushRepo(
      org,
      workspaceRepo,
      wsDir,
      flags["workspace-public"] ? "public" : "private",
      gitHost,
    );
    ensureSshKey(stagePub);
    pushed = true;
  }

  printSummary({
    workDir,
    boltYamlPath,
    ageSecretLine,
    bootstrapUrl,
    dotfilesUrl,
    workspaceUrl,
    dotfilesKey,
    pushed,
    dryRun,
    org,
    bootstrapRepo,
    dotfilesRepo,
    workspaceRepo,
    bootDir,
    dotDir,
    wsDir,
    stagePub,
    keyName,
  });
}

function pushRepo(org, repo, dir, visibility, gitHost) {
  if (gitHost !== "github.com")
    fail(`--push supports github.com only; push ${repo} manually`);
  const exists =
    spawnSync("gh", ["repo", "view", `${org}/${repo}`], { stdio: "ignore" })
      .status === 0;
  if (exists) {
    const remotes = run("git", ["remote"], { cwd: dir, capture: true });
    if (!remotes.split(/\s+/).includes("origin"))
      run("git", ["remote", "add", "origin", `https://${gitHost}/${org}/${repo}.git`], {
        cwd: dir,
      });
    run("git", ["push", "-u", "origin", "main"], { cwd: dir });
  } else {
    run("gh", [
      "repo",
      "create",
      `${org}/${repo}`,
      `--${visibility}`,
      "--source",
      dir,
      "--remote",
      "origin",
      "--push",
    ]);
  }
  log(`pushed ${org}/${repo} (${visibility})`);
}

function ensureSshKey(pubPath) {
  const pub = readFileSync(pubPath, "utf8").trim();
  const listed = run("gh", ["ssh-key", "list"], { capture: true });
  const keyBody = pub.split(/\s+/)[1] || "";
  if (keyBody && listed.includes(keyBody)) {
    log("ssh public key already registered with GitHub");
    return;
  }
  run("gh", ["ssh-key", "add", pubPath, "--title", "quiver-bootstrap"]);
  log("registered ssh public key with GitHub");
}

function printSummary(c) {
  log("\n=== stack built ===\n");
  log(`work dir:   ${c.workDir}`);
  log(`bolt.yaml:  ${c.boltYamlPath}`);
  log(`bootstrap:  ${c.bootstrapUrl}  (must be PUBLIC)`);
  log(`dotfiles:   ${c.dotfilesUrl}`);
  log(`workspace:  ${c.workspaceUrl}`);
  log(`\nAGE private key (keep secret, never commit):\n  ${c.ageSecretLine}`);
  log(`DOTFILES_KEY (for future secret rotation): ${c.dotfilesKey}`);

  if (!c.pushed) {
    log("\nnext: push the three repos");
    if (c.dryRun) log("(dry-run: nothing was pushed)");
    log(
      `  gh repo create ${c.org}/${c.bootstrapRepo} --public  --source "${c.bootDir}" --remote origin --push`,
    );
    log(
      `  gh repo create ${c.org}/${c.dotfilesRepo}  --private --source "${c.dotDir}"  --remote origin --push`,
    );
    log(
      `  gh repo create ${c.org}/${c.workspaceRepo} --private --source "${c.wsDir}"   --remote origin --push`,
    );
    log(
      `  gh ssh-key add "${c.stagePub}" --title quiver-bootstrap   # so the bolt can clone private repos`,
    );
  }

  log("\nnext: create the bolt");
  log(
    `  quiver create <name> --config "${c.boltYamlPath}" --age-key "${c.ageSecretLine}"`,
  );
  log("\nverify inside the bolt:");
  log("  env | grep MY_SECRET");
  log("  cat /workspace/README.md");
}

main().catch((e) => fail(e.message));
