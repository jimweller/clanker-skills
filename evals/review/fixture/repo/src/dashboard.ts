import { loadDashboard, User } from "./api.js";

export function mountDashboard(root: HTMLElement): void {
  root.textContent = "Loading...";
  void loadDashboard((me: User, users: User[]) => {
    root.textContent = `${me.name}: ${users.length} users`;
  });
}
