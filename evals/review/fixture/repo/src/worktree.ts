import { execFile } from "node:child_process";
import { promisify } from "node:util";
import path from "node:path";
import { REPOS_DIR, SERVICE_TOKEN } from "./config.js";
import { gitAuthArgs, Repo } from "./git-auth.js";

const exec = promisify(execFile);

export function cachePath(id: string): string {
  return path.resolve(REPOS_DIR, id);
}

export async function cloneRepo(repo: Repo): Promise<string> {
  const dest = cachePath(repo.id);
  await exec("git", [...gitAuthArgs(repo.remoteUrl, SERVICE_TOKEN), "clone", repo.remoteUrl, dest]);
  return dest;
}
