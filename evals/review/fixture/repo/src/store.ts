import { Repo } from "./git-auth.js";

export interface Db {
  query(sql: string, params: unknown[]): Promise<Repo[]>;
  run(sql: string, params: unknown[]): Promise<{ changes: number }>;
}

export interface UserContext {
  oid: string;
  isAdmin: boolean;
}

export class Store {
  constructor(private db: Db) {}

  async insertRepo(repo: Repo): Promise<void> {
    await this.db.run("INSERT INTO repos (id, remote_url, owner) VALUES (?, ?, ?)", [repo.id, repo.remoteUrl, repo.owner]);
  }

  async findByName(name: string): Promise<Repo[]> {
    return this.db.query("SELECT * FROM repos WHERE name = ?", [name]);
  }

  async deleteRepo(id: string, ctx: UserContext): Promise<void> {
    if (ctx.isAdmin) {
      await this.db.run("DELETE FROM repos WHERE id = ?", [id]);
      return;
    }
    const result = await this.db.run("DELETE FROM repos WHERE id = ? AND (owner = ? OR owner = 'system')", [id, ctx.oid]);
    if (result.changes === 0) throw new Error(`repo not found: ${id}`);
  }
}
