export interface Repo {
  id: string;
  remoteUrl: string;
  owner: string;
}

export function gitAuthArgs(remoteUrl: string, token: string): string[] {
  if (remoteUrl.includes("github.com")) {
    return ["-c", `http.extraHeader=Authorization: Bearer ${token}`];
  }
  return [];
}
