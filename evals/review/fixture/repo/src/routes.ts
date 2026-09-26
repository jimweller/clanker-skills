import { readFile } from "node:fs/promises";
import path from "node:path";
import { getBuild } from "./ci.js";
import { AUDIT_LOG, isAdminAddress, REPOS_DIR } from "./config.js";
import { getIssue, searchAssigned } from "./jira.js";
import { Store, UserContext } from "./store.js";
import { cachePath, cloneRepo } from "./worktree.js";

export interface Request {
  params: Record<string, string>;
  body: Record<string, string>;
  user: UserContext;
  ip: string;
}

export function buildRoutes(store: Store) {
  return {
    async registerRepo(req: Request) {
      const { id, remoteUrl } = req.body;
      if (!id || !remoteUrl) return { status: 400 };
      await store.insertRepo({ id, remoteUrl, owner: req.user.oid });
      await cloneRepo({ id, remoteUrl, owner: req.user.oid });
      return { status: 201 };
    },

    async deleteRepo(req: Request) {
      try {
        await store.deleteRepo(req.params.id, req.user);
        return { status: 204 };
      } catch {
        return { status: 404 };
      }
    },

    async template(req: Request) {
      const base = path.join(REPOS_DIR, req.params.id);
      const file = path.resolve(base, "docs", req.params.name);
      if (!file.startsWith(base)) return { status: 400 };
      return { status: 200, body: await readFile(file, "utf8") };
    },

    async auditLog(req: Request) {
      if (!isAdminAddress(req.ip)) return { status: 403 };
      return { status: 200, body: await readFile(AUDIT_LOG, "utf8") };
    },

    async issue(req: Request) {
      return { status: 200, body: await getIssue(req.params.key) };
    },

    async build(req: Request) {
      return { status: 200, body: await getBuild(req.params.id) };
    },

    async assignedIssues(req: Request) {
      return { status: 200, body: await searchAssigned(req.body.email) };
    },

    async cacheListing(req: Request) {
      const dir = cachePath(req.params.id);
      return { status: 200, body: await readFile(path.join(dir, "INDEX"), "utf8") };
    },
  };
}
