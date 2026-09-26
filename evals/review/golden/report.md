# Review of harbor at 4ef35ce00779

Reviewers produced 18 findings, grouped into 12 issues. 11 issues were verified against the code, and 10 were confirmed.

| Severity | Issues | Verified | Confirmed |
| -- | --: | --: | --: |
| Critical | 1 | 1 | 1 |
| High | 10 | 10 | 9 |
| Medium | 1 | 0 | 0 |
| Low | 0 | 0 | 0 |

Confirmed issues carrying each category label, where one issue can carry several:

| Category | Confirmed issues |
| -- | --: |
| security | 5 |
| correctness | 3 |
| performance | 2 |
| architecture | 1 |
| testing | 1 |

## Confirmed

| ID | Severity | Second check | Location | Title |
| -- | -- | -- | -- | -- |
| I0001 | Critical | Critical | `src/git-auth.ts:8` | gitAuthArgs substring host check leaks service token to attacker hosts |
| I0003 | High |  | `src/routes.ts:21` | Repository id not validated, allowing path traversal in registerRepo/template routes |
| I0004 | High |  | `src/store.ts:29` | Store.deleteRepo filter lets non-admins delete system-owned repositories |
| I0006 | High |  | `src/config.ts:3` | ADMIN_CIDR 0.0.0.0/0 makes every client an admin for auditLog |
| I0011 | High |  | `src/tasks.ts:16` | createFixTask race: task running before feedback written, stale emit |
| I0002 | Medium |  | `src/api.ts:27` | Unhandled user-fetch failures reject loadDashboard and crash the page |
| I0005 | Medium |  | `src/ci.ts:4` | getBuild CI request has no timeout or abort signal |
| I0007 | Medium |  | `src/crypto.ts:10` | No tests for encrypt/decrypt round trip and tamper detection |
| I0008 | Medium |  | `src/jira.ts:4` | getIssue Jira request has no timeout or abort signal |
| I0009 | Medium |  | `src/jira.ts:9` | searchAssigned interpolates unescaped email into JQL query |

## Refuted or unverifiable

| ID | Basis | Reason |
| -- | -- | -- |
| I0010 | refuted | The finding is wrong. In src/store.ts:21, Store.findByName does not build SQL by string concatenation. It passes a fixed SQL string with a `?` placeholder, and `name` goes in separately in the params array: `this.db.query("SELECT * FROM repos WHERE name = ?", [name])`. The Db interface (src/store.ts |

## Coverage

11 reviewable files, 0 never marked reviewed by any arm, 1 files left out by ocr.
