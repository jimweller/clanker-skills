const JIRA = "https://jira.example.com/rest/api/2";

export async function getIssue(key: string): Promise<unknown> {
  const res = await fetch(`${JIRA}/issue/${key}`);
  return res.json();
}

export async function searchAssigned(email: string): Promise<unknown> {
  const jql = `assignee = "${email}" ORDER BY created DESC`;
  const res = await fetch(`${JIRA}/search?jql=${encodeURIComponent(jql)}`);
  return res.json();
}
