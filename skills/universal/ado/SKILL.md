---
name: ado
description: Azure DevOps operations via az CLI. Always when working with Azure Devops for repository management and pull requests.
user-invocable: false
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🔷

# Azure DevOps Operations

Use the `az` CLI and ADO REST API to interact with Azure DevOps resources.

## Prerequisites

Auth: `$AZURE_DEVOPS_EXT_PAT` (always set). No login needed.

Repo ops require ADO remote (`dev.azure.com` or `visualstudio.com`).

## Default Org and Project

The shell environment provides default values via `$ADO_DEFAULT_ORG` and `$ADO_DEFAULT_PROJECT`. Use these as fallbacks when org or project cannot be parsed from the git remote, or when operating outside a git repo.

```bash
org="${org:-$ADO_DEFAULT_ORG}"
project="${project:-$ADO_DEFAULT_PROJECT}"
```

Pass them to `az` commands via `--org "https://dev.azure.com/${org}"` and `--project "$project"`.

## URL Parsing

Azure DevOps remotes come in three formats. Parse org, project, and repo from the remote URL to construct web URLs and pass parameters to `az` commands.

```bash
remote_url=$(git remote get-url origin 2>/dev/null)
```

### Format 1: dev.azure.com HTTPS

Pattern: `https://dev.azure.com/{org}/{project}/_git/{repo}` or `https://{user}@dev.azure.com/{org}/{project}/_git/{repo}`

```bash
clean_url=$(echo "$remote_url" | sed 's|https://[^@]*@|https://|')
org=$(echo "$clean_url" | sed -n 's|https://dev\.azure\.com/\([^/]*\)/.*|\1|p')
project=$(echo "$clean_url" | sed -n 's|https://dev\.azure\.com/[^/]*/\([^/]*\)/_git/.*|\1|p')
repo=$(echo "$clean_url" | sed -n 's|.*/_git/\(.*\)|\1|p')
```

### Format 2: visualstudio.com

Pattern: `https://{org}.visualstudio.com/DefaultCollection/{project}/_git/{repo}`

```bash
clean_url=$(echo "$remote_url" | sed 's|https://[^@]*@|https://|')
org=$(echo "$clean_url" | sed -n 's|^https://\([^.]*\)\..*|\1|p')
project=$(echo "$clean_url" | sed -n 's|.*/DefaultCollection/\([^/]*\)/_git/.*|\1|p')
repo=$(echo "$clean_url" | sed -n 's|.*/_git/\(.*\)|\1|p')
```

### Format 3: SSH

Pattern: `git@ssh.dev.azure.com:v3/{org}/{project}/{repo}`

```bash
org=$(echo "$remote_url" | sed -n 's|git@ssh\.dev\.azure\.com:v3/\([^/]*\)/.*|\1|p')
project=$(echo "$remote_url" | sed -n 's|git@ssh\.dev\.azure\.com:v3/[^/]*/\([^/]*\)/.*|\1|p')
repo=$(echo "$remote_url" | sed -n 's|.*[^/]*/\([^/]*\)$|\1|p')
```

### Constructing Web URLs

URL-encode spaces in project names (`%20`), then build:

```text
base_url=https://dev.azure.com/{org}/{project}/_git/{repo}
pr_url={base_url}/pullrequest/{pr_id}
```

On macOS, open URLs with `open "$url"`.

---

## Browse

### Open Repo

Parse the remote URL, construct the web URL, and open it.

```bash
open "https://dev.azure.com/${org}/${project}/_git/${repo}"
```

### Open PR

```bash
open "https://dev.azure.com/${org}/${project}/_git/${repo}/pullrequest/${pr_id}"
```

---

## Projects

### List Projects

```bash
az devops project list --organization "https://dev.azure.com/${org}" --query "value[].{Name:name,ID:id,State:state}" -o table
```

### Show Project Details

```bash
az devops project show --project "$project" --organization "https://dev.azure.com/${org}"
```

### Get Project ID

```bash
az devops project show --project "$project" --organization "https://dev.azure.com/${org}" --query id -o tsv
```

---

## Repositories

### Create

```bash
az repos create \
  --name "<repo-name>" \
  --project "$project" \
  --org "https://dev.azure.com/${org}" \
  --output table \
  --query "{Name:name,Project:project.name,URL:webUrl}"
```

### Delete

Step 1: Look up the repository ID.

```bash
repo_id=$(az repos show \
  --repository "<repo-name>" \
  --project "$project" \
  --query id --output tsv)
```

Step 2: Delete by ID.

```bash
az repos delete \
  --id "$repo_id" \
  --project "$project" \
  --yes
```

### List

```bash
az repos list --organization "https://dev.azure.com/${org}" --project "$project" --query "[].{Name:name,ID:id,DefaultBranch:defaultBranch}" -o table
```

### Show

```bash
az repos show --repository <REPO_NAME> --organization "https://dev.azure.com/${org}" --project "$project"
```

### Get Clone URL

```bash
az repos show --repository <REPO_NAME> --organization "https://dev.azure.com/${org}" --project "$project" --query remoteUrl -o tsv
```

---

## Pull Requests (CLI)

All PR commands use JMESPath queries for structured output. The `base_url` variable is constructed from the parsed remote URL (see URL Parsing above).

### Create

```bash
az repos pr create \
  "$@" \
  --output table \
  --query "{PR:pullRequestId,Status:status,URL:join(\`\`,[\ \`${base_url}\`,\`/pullrequest/\`,to_string(pullRequestId)])}"
```

Common flags: `--title`, `--description`, `--source-branch`, `--target-branch`, `--reviewers`, `--auto-complete`, `--draft`

### List

```bash
az repos pr list \
  --output table \
  --query "[].{PR:pullRequestId,Title:title,Creator:createdBy.uniqueName,Created:creationDate,URL:join(\`\`,[\`${base_url}\`,\`/pullrequest/\`,to_string(pullRequestId)])}"
```

Common flags: `--status`, `--creator`, `--reviewer`, `--source-branch`, `--target-branch`

### Show

```bash
az repos pr show \
  --id <pr-id> \
  --output table \
  --query "{PR:pullRequestId,Title:title,Creator:createdBy.uniqueName,Created:creationDate,URL:join(\`\`,[\`${base_url}\`,\`/pullrequest/\`,to_string(pullRequestId)])}"
```

### Update

```bash
az repos pr update \
  --id <pr-id> \
  --output table \
  --query "{PR:pullRequestId,Status:status,URL:join(\`\`,[\`${base_url}\`,\`/pullrequest/\`,to_string(pullRequestId)])}"
```

Common flags: `--title`, `--description`, `--status`, `--auto-complete`, `--draft`

### Complete

Complete (merge) a pull request by setting status to completed with policy bypass.

```bash
az repos pr update \
  --id <pr-id> \
  --status completed \
  --bypass-policy true \
  --output table \
  --query "{PR:pullRequestId,Status:status,URL:join(\`\`,[\`${base_url}\`,\`/pullrequest/\`,to_string(pullRequestId)])}"
```

Additional flags: `--merge-commit-message`

Completion is async. The response will still show `active` status. Follow up with `az repos pr show --id <pr-id>` to confirm `status: completed` and `mergeStatus: succeeded`.

### Abandon

```bash
az repos pr update \
  --id <pr-id> \
  --status abandoned \
  --output table \
  --query "{PR:pullRequestId,Status:status,URL:join(\`\`,[\`${base_url}\`,\`/pullrequest/\`,to_string(pullRequestId)])}"
```

### Vote/Approve

```bash
az repos pr set-vote \
  --id <pr-id> \
  --vote approve
```

After voting, show the PR details:

```bash
az repos pr show \
  --id <pr-id> \
  --output table \
  --query "{PR:pullRequestId,Title:title,Creator:createdBy.uniqueName,Created:creationDate,URL:join(\`\`,[\`${base_url}\`,\`/pullrequest/\`,to_string(pullRequestId)])}"
```

Valid vote values: `approve`, `approve-with-suggestions`, `wait-for-author`, `reject`, `reset`

---

## PR Comments and Threads (REST API)

### Post Comment

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pullRequests/<PR_ID>/threads?api-version=7.0" \
  -H "Content-Type: application/json" \
  -d '{
    "comments": [{"parentCommentId": 0, "content": "Comment text here", "commentType": 1}],
    "status": 1
  }'
```

### Get Comments/Threads

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pullRequests/<PR_ID>/threads?api-version=7.0" \
  | jq '.value[] | {id: .id, status: .status, comments: [.comments[] | {author: .author.displayName, content: .content}]}'
```

### Search for Comment Containing Text

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pullRequests/<PR_ID>/threads?api-version=7.0" \
  | jq '.value[].comments[] | select(.content | contains("SEARCH_TEXT")) | {author: .author.displayName, content: .content}'
```

---

## Service Connections

### List

```bash
az devops service-endpoint list --organization "https://dev.azure.com/${org}" --project "$project" --query "[].{Name:name,Type:type,ID:id,Scheme:authorization.scheme}" -o table
```

### Show Details

```bash
az devops service-endpoint show --id <ENDPOINT_ID> --organization "https://dev.azure.com/${org}" --project "$project"
```

### Get by Name

```bash
az devops service-endpoint list --organization "https://dev.azure.com/${org}" --project "$project" --query "[?name=='<NAME>']" -o json
```

### Delete

```bash
az devops service-endpoint delete --id <ENDPOINT_ID> --organization "https://dev.azure.com/${org}" --project "$project" --yes
```

### Get WIF Details (REST API)

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/serviceendpoint/endpoints?api-version=7.1" \
  | jq ".value[] | select(.name == \"<NAME>\") | {issuer: .authorization.parameters.workloadIdentityFederationIssuer, subject: .authorization.parameters.workloadIdentityFederationSubject}"
```

### Authorize for All Pipelines (REST API)

```bash
SC_ID=$(az devops service-endpoint list --organization "https://dev.azure.com/${org}" --project "$project" --query "[?name=='<NAME>'].id" -o tsv)
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X PATCH \
  "https://dev.azure.com/${org}/${project}/_apis/pipelines/pipelinePermissions/endpoint/${SC_ID}?api-version=7.1-preview.1" \
  -H "Content-Type: application/json" \
  -d '{"allPipelines": {"authorized": true}}'
```

---

## Agent Pools

Pools are organization-level and shared across projects.

### List All

```bash
az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[].{Name:name,ID:id,PoolType:poolType,IsHosted:isHosted,Size:size}" -o table
```

### List by Name Pattern

```bash
az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[?contains(name, '<PATTERN>')].{Name:name,ID:id,PoolType:poolType,Size:size}" -o table
```

### Get Pool ID by Name

```bash
az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[?name=='<POOL_NAME>'].id" -o tsv
```

### Show Details

```bash
az pipelines pool show --organization "https://dev.azure.com/${org}" --pool-id <POOL_ID>
```

### Create (REST API)

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://dev.azure.com/${org}/_apis/distributedtask/pools?api-version=7.1" \
  -H "Content-Type: application/json" \
  -d '{"name": "<POOL_NAME>", "poolType": "automation", "isHosted": false, "autoProvision": false}'
```

### Delete (REST API)

```bash
POOL_ID=$(az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[?name=='<POOL_NAME>'].id" -o tsv)
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X DELETE \
  "https://dev.azure.com/${org}/_apis/distributedtask/pools/${POOL_ID}?api-version=7.1"
```

---

## Agents

Agents run within pools.

### List Agents in Pool

```bash
POOL_ID=$(az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[?name=='<POOL_NAME>'].id" -o tsv)
az pipelines agent list --organization "https://dev.azure.com/${org}" --pool-id $POOL_ID --query "[].{Name:name,ID:id,Status:status,Version:version}" -o table
```

### List Online Agents

```bash
POOL_ID=$(az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[?name=='<POOL_NAME>'].id" -o tsv)
az pipelines agent list --organization "https://dev.azure.com/${org}" --pool-id $POOL_ID --query "[?status=='online'].{Name:name,ID:id,Version:version}" -o table
```

### Show Agent Details

```bash
az pipelines agent show --organization "https://dev.azure.com/${org}" --pool-id <POOL_ID> --agent-id <AGENT_ID>
```

### Count Online Agents

```bash
POOL_ID=$(az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[?name=='<POOL_NAME>'].id" -o tsv)
az pipelines agent list --organization "https://dev.azure.com/${org}" --pool-id $POOL_ID --query "[?status=='online']" -o tsv | wc -l
```

---

## Queues

Queues are project-level references to organization-level pools. Pipeline authorization works on queues, not pools.

### List All

```bash
az pipelines queue list --organization "https://dev.azure.com/${org}" --project "$project" --query "[].{Name:name,QueueID:id,PoolID:pool.id}" -o table
```

### List by Name Pattern

```bash
az pipelines queue list --organization "https://dev.azure.com/${org}" --project "$project" --query "[?contains(name, '<PATTERN>')].{Name:name,QueueID:id,PoolID:pool.id}" -o table
```

### Get Queue ID for Pool

```bash
POOL_ID=$(az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[?name=='<POOL_NAME>'].id" -o tsv)
az pipelines queue list --organization "https://dev.azure.com/${org}" --project "$project" --query "[?pool.id==\`${POOL_ID}\`].id" -o tsv
```

### Create Queue for Pool (REST API)

```bash
POOL_ID=$(az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[?name=='<POOL_NAME>'].id" -o tsv)
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://dev.azure.com/${org}/${project}/_apis/distributedtask/queues?api-version=7.1" \
  -H "Content-Type: application/json" \
  -d '{"name": "<QUEUE_NAME>", "pool": {"id": '${POOL_ID}'}}'
```

### Authorize Queue for All Pipelines (REST API)

```bash
QUEUE_ID=$(az pipelines queue list --organization "https://dev.azure.com/${org}" --project "$project" --query "[?name=='<QUEUE_NAME>'].id" -o tsv)
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X PATCH \
  "https://dev.azure.com/${org}/${project}/_apis/pipelines/pipelinePermissions/queue/${QUEUE_ID}?api-version=7.1-preview.1" \
  -H "Content-Type: application/json" \
  -d '{"allPipelines": {"authorized": true}}'
```

### Authorize Queue for Specific Pipeline (REST API)

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X PATCH \
  "https://dev.azure.com/${org}/${project}/_apis/pipelines/pipelinePermissions/queue/<QUEUE_ID>?api-version=7.1-preview.1" \
  -H "Content-Type: application/json" \
  -d '{"pipelines": [{"id": <PIPELINE_ID>, "authorized": true}]}'
```

---

## Pipelines

### List All

```bash
az pipelines list --organization "https://dev.azure.com/${org}" --project "$project" --query "[].{Name:name,ID:id,Folder:folder,QueueStatus:queueStatus}" -o table
```

### List by Name Pattern

```bash
az pipelines list --organization "https://dev.azure.com/${org}" --project "$project" --name "<PATTERN>*" --query "[].{Name:name,ID:id}" -o table
```

### Show Details

```bash
az pipelines show --organization "https://dev.azure.com/${org}" --project "$project" --name <PIPELINE_NAME>
```

### Get Pipeline ID by Name

```bash
az pipelines list --organization "https://dev.azure.com/${org}" --project "$project" --query "[?name=='<PIPELINE_NAME>'].id" -o tsv
```

### Create

```bash
az pipelines create \
  --organization "https://dev.azure.com/${org}" \
  --project "$project" \
  --name <PIPELINE_NAME> \
  --repository <REPO_NAME> \
  --repository-type tfsgit \
  --branch main \
  --yml-path azure-pipelines.yml \
  --skip-first-run
```

### Delete

```bash
PIPELINE_ID=$(az pipelines list --organization "https://dev.azure.com/${org}" --project "$project" --query "[?name=='<PIPELINE_NAME>'].id" -o tsv)
az pipelines delete --id $PIPELINE_ID --organization "https://dev.azure.com/${org}" --project "$project" --yes
```

---

## Pipeline Runs (Builds)

### Run Pipeline

```bash
az pipelines run --organization "https://dev.azure.com/${org}" --project "$project" --name <PIPELINE_NAME>
```

### Run and Get Run ID

```bash
RUN_ID=$(az pipelines run --organization "https://dev.azure.com/${org}" --project "$project" --name <PIPELINE_NAME> --query id -o tsv)
echo "Run ID: $RUN_ID"
```

### Run with Variables

```bash
az pipelines run --organization "https://dev.azure.com/${org}" --project "$project" --name <PIPELINE_NAME> --variables "VAR1=value1" "VAR2=value2"
```

### List Recent Runs

```bash
az pipelines runs list --organization "https://dev.azure.com/${org}" --project "$project" --top 10 --query "[].{ID:id,Pipeline:definition.name,Status:status,Result:result,StartTime:startTime}" -o table
```

### List Runs for Specific Pipeline

```bash
PIPELINE_ID=$(az pipelines list --organization "https://dev.azure.com/${org}" --project "$project" --query "[?name=='<PIPELINE_NAME>'].id" -o tsv)
az pipelines runs list --organization "https://dev.azure.com/${org}" --project "$project" --pipeline-ids $PIPELINE_ID --query "[].{ID:id,Status:status,Result:result}" -o table
```

### Show Run Status

```bash
az pipelines runs show --organization "https://dev.azure.com/${org}" --project "$project" --id <RUN_ID> --query "{Status:status,Result:result}" -o json
```

### Watch Run Until Complete

```bash
RUN_ID=<RUN_ID>
while true; do
  STATUS=$(az pipelines runs show --organization "https://dev.azure.com/${org}" --project "$project" --id $RUN_ID --query status -o tsv)
  RESULT=$(az pipelines runs show --organization "https://dev.azure.com/${org}" --project "$project" --id $RUN_ID --query result -o tsv)
  echo "Status: $STATUS, Result: ${RESULT:-pending}"
  if [ "$STATUS" == "completed" ]; then break; fi
  sleep 10
done
```

---

## Build Logs

### Get Build Timeline (Stages/Jobs)

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/build/builds/<RUN_ID>/timeline?api-version=7.1" \
  | jq '.records[] | {name: .name, type: .type, state: .state, result: .result}'
```

### List Build Logs

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/build/builds/<RUN_ID>/logs?api-version=7.1" \
  | jq '.value[] | {id: .id, type: .type, lineCount: .lineCount}'
```

### Download Specific Log

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/build/builds/<RUN_ID>/logs/<LOG_ID>?api-version=7.1"
```

### Get Failed Step Logs

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/build/builds/<RUN_ID>/timeline?api-version=7.1" \
  | jq '.records[] | select(.result == "failed") | {name: .name, log: .log.url}'
```

---

## Git Operations (REST API)

For programmatic Git workflows (branches, commits, pushes) without a local clone.

### Get Repository by Name

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>?api-version=7.0" \
  | jq '{id: .id, name: .name, defaultBranch: .defaultBranch}'
```

### Get Branch Refs

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/refs?filter=heads/main&api-version=7.0" \
  | jq '.value[] | {name: .name, objectId: .objectId}'
```

### Get Main Branch Commit SHA

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/refs?filter=heads/main&api-version=7.0" \
  | jq -r '.value[0].objectId'
```

### Create Branch from Main

```bash
MAIN_SHA=$(curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/refs?filter=heads/main&api-version=7.0" \
  | jq -r '.value[0].objectId')

curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/refs?api-version=7.0" \
  -H "Content-Type: application/json" \
  -d '[{"name": "refs/heads/<BRANCH_NAME>", "oldObjectId": "0000000000000000000000000000000000000000", "newObjectId": "'${MAIN_SHA}'"}]'
```

### Delete Branch

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/refs?api-version=7.0" \
  -H "Content-Type: application/json" \
  -d '[{"name": "refs/heads/<BRANCH_NAME>", "oldObjectId": "<LAST_COMMIT_SHA>", "newObjectId": "0000000000000000000000000000000000000000"}]'
```

### Push a Commit (Add/Edit Files)

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pushes?api-version=7.0" \
  -H "Content-Type: application/json" \
  -d '{
    "refUpdates": [{"name": "refs/heads/<BRANCH_NAME>", "oldObjectId": "<BASE_COMMIT_SHA>"}],
    "commits": [{
      "comment": "Commit message here",
      "changes": [
        {
          "changeType": "edit",
          "item": {"path": "/path/to/file"},
          "newContent": {"content": "file content here", "contentType": "rawtext"}
        }
      ]
    }]
  }'
```

### Push Initial Commit (New Repository)

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pushes?api-version=7.0" \
  -H "Content-Type: application/json" \
  -d '{
    "refUpdates": [{"name": "refs/heads/main", "oldObjectId": "0000000000000000000000000000000000000000"}],
    "commits": [{
      "comment": "Initial commit",
      "changes": [
        {
          "changeType": "add",
          "item": {"path": "/README.md"},
          "newContent": {"content": "# Repo Title", "contentType": "rawtext"}
        }
      ]
    }]
  }'
```

### Push with Base64-Encoded Content

```bash
CONTENT_B64=$(echo -n "file contents here" | base64)
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pushes?api-version=7.0" \
  -H "Content-Type: application/json" \
  -d '{
    "refUpdates": [{"name": "refs/heads/<BRANCH>", "oldObjectId": "<SHA>"}],
    "commits": [{
      "comment": "Add file",
      "changes": [{
        "changeType": "add",
        "item": {"path": "/file.txt"},
        "newContent": {"content": "'${CONTENT_B64}'", "contentType": "base64encoded"}
      }]
    }]
  }'
```

---

## Pull Requests (REST API)

Alternative to `az repos pr` commands when more control is needed.

### Create

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pullrequests?api-version=7.0" \
  -H "Content-Type: application/json" \
  -d '{
    "sourceRefName": "refs/heads/<SOURCE_BRANCH>",
    "targetRefName": "refs/heads/main",
    "title": "PR Title",
    "description": "PR description"
  }' | jq '{pullRequestId: .pullRequestId, status: .status}'
```

### Get Details

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pullRequests/<PR_ID>?api-version=7.0" \
  | jq '{id: .pullRequestId, title: .title, status: .status, sourceRefName: .sourceRefName}'
```

### List

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pullrequests?api-version=7.0" \
  | jq '.value[] | {id: .pullRequestId, title: .title, status: .status}'
```

### Abandon

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X PATCH \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pullRequests/<PR_ID>?api-version=7.0" \
  -H "Content-Type: application/json" \
  -d '{"status": "abandoned"}'
```

### Complete (Merge)

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X PATCH \
  "https://dev.azure.com/${org}/${project}/_apis/git/repositories/<REPO_NAME>/pullRequests/<PR_ID>?api-version=7.0" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "lastMergeSourceCommit": {"commitId": "<LAST_COMMIT_SHA>"},
    "completionOptions": {"deleteSourceBranch": true, "mergeStrategy": "squash"}
  }'
```

---

## Code Search (REST API)

Search code across repositories. Uses the `almsearch.dev.azure.com` host, not `dev.azure.com`.

### Search in Project

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://almsearch.dev.azure.com/${org}/${project}/_apis/search/codesearchresults?api-version=7.1" \
  -H "Content-Type: application/json" \
  -d '{"searchText":"<TEXT>","$top":25}' \
  | jq '{count: .count, results: [.results[] | {repo: .repository.name, path: .path}]}'
```

### Search Across Org with Filters

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://almsearch.dev.azure.com/${org}/_apis/search/codesearchresults?api-version=7.1" \
  -H "Content-Type: application/json" \
  -d '{
    "searchText":"<TEXT>",
    "filters":{"Project":["<PROJECT>"],"Repository":["<REPO>"],"Branch":["main"],"Path":["/src"]},
    "$top":25
  }' \
  | jq '.results[] | {project: .project.name, repo: .repository.name, path: .path}'
```

Available filter keys: `Project`, `Repository`, `Branch`, `Path`, `CodeElement` (e.g. `["def","class"]`).

### Search Operators

The `searchText` field accepts ADO search syntax:

- `ext:go quiver-bolt` -- file extension filter
- `file:Makefile quiver-bolt` -- filename filter
- `def:MyFunction` -- function/method definitions
- `"exact phrase"` -- exact match
- `foo AND bar`, `foo OR bar`, `foo NOT bar` -- boolean

---

## Webhooks (REST API)

### List Service Hooks

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/${org}/_apis/hooks/subscriptions?api-version=7.0" \
  | jq '.value[] | {id: .id, eventType: .eventType, consumerActionId: .consumerActionId, publisherInputs: .publisherInputs}'
```

### Create Webhook for PR Events

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X POST \
  "https://dev.azure.com/${org}/_apis/hooks/subscriptions?api-version=7.0" \
  -H "Content-Type: application/json" \
  -d '{
    "publisherId": "tfs",
    "eventType": "git.pullrequest.created",
    "resourceVersion": "1.0",
    "consumerId": "webHooks",
    "consumerActionId": "httpRequest",
    "publisherInputs": {
      "projectId": "<PROJECT_ID>",
      "repository": "<REPO_ID>"
    },
    "consumerInputs": {
      "url": "<WEBHOOK_URL>"
    }
  }'
```

### Delete Webhook

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" -X DELETE \
  "https://dev.azure.com/${org}/_apis/hooks/subscriptions/<SUBSCRIPTION_ID>?api-version=7.0"
```

---

## Diagnostics

### Check ADO Infrastructure Health

```bash
echo "=== Service Connections ==="
az devops service-endpoint list --organization "https://dev.azure.com/${org}" --project "$project" --query "[].{Name:name,Type:type}" -o table

echo ""
echo "=== Agent Pools ==="
az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[].{Name:name,Size:size,IsHosted:isHosted}" -o table

echo ""
echo "=== Queues ==="
az pipelines queue list --organization "https://dev.azure.com/${org}" --project "$project" --query "[].{Name:name,QueueID:id}" -o table
```

### Check Agents in a Pool

```bash
POOL_ID=$(az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[?name=='<POOL_NAME>'].id" -o tsv)
if [ -n "$POOL_ID" ]; then
  az pipelines agent list --organization "https://dev.azure.com/${org}" --pool-id $POOL_ID --query "[].{Name:name,Status:status}" -o table
fi
```

### Wait for Agents to Come Online

```bash
POOL_ID=$(az pipelines pool list --organization "https://dev.azure.com/${org}" --query "[?name=='<POOL_NAME>'].id" -o tsv)
MAX_WAIT=300
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  ONLINE=$(az pipelines agent list --organization "https://dev.azure.com/${org}" --pool-id $POOL_ID --query "[?status=='online']" -o tsv | wc -l)
  if [ "$ONLINE" -gt 0 ]; then
    echo "Found $ONLINE online agent(s)"
    break
  fi
  echo "Waiting for agents... ($ELAPSED/${MAX_WAIT}s)"
  sleep 10
  ELAPSED=$((ELAPSED + 10))
done
```

---

## Key Concepts

### Pool vs Queue

- **Pools** are organization-level (shared across projects)
- **Queues** are project-level references to pools
- Pipeline authorization works on **queues**, not pools

### Workload Identity Federation

Service connections use WIF (OIDC). No secrets stored in ADO. Federated credentials are managed in App Registration.

### REST API vs CLI

Some operations require REST API (no CLI equivalent):

- Creating pools with specific settings
- Authorizing queues for pipelines
- Querying WIF subjects from service connections
- Git push operations (branches, commits)
- PR comment threads
- Webhooks
