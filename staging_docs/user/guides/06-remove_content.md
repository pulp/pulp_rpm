# Remove Content

Removing content from Pulp entirely is slightly complicated for a number of architectural reasons.
First, repository-versions are immutable (so you can get back to any version and have all the content available). This means that it is not possible to remove content as long as there still exists a repo-version that "knows about it".
Second, Pulp deduplicates content. Artifacts can be shared across repositories - which means the repo being looked at, may not be the only one whose repo-versions still point to the content.

**The way content gets removed "from Pulp" is via the orphan cleanup task, which will look for Artifacts that don't belong to any repository-versions, and haven't been touched in a while, and removes them.**

## Removing Content

!!! warning
    Please, follow the script steps carefully and only if you know what you are doing because you risk losing data.

```bash
#!/usr/bin/env bash

# Remove content from repository
echo "Removing content from ${REPO_NAME}"
pulp rpm repository version destroy --repository $REPO_NAME

echo "Removing orphan rpm contents"
pulp orphan cleanup --content-hrefs $(pulp rpm content list | jq -cr '.|map(.pulp_href)') --protection-time 0

echo "Checking rpm contents"
pulp rpm repository content list --repository $REPO_NAME
```
