export interface User {
  oid: string;
  name: string;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export async function fetchCurrentUser(): Promise<User> {
  const res = await fetch("/api/me");
  return json<User>(res);
}

export async function fetchUserList(): Promise<User[]> {
  try {
    const res = await fetch("/api/admin/users");
    if (!res.ok) return [];
    return ((await res.json()) as { users: User[] }).users ?? [];
  } catch {
    return [];
  }
}

export async function loadDashboard(render: (me: User, users: User[]) => void): Promise<void> {
  const me = await fetchCurrentUser();
  const users = await fetchUserList();
  render(me, users);
}
