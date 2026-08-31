# Recommended GitHub repository metadata

Use these values to update the repository on GitHub. They cannot be changed from
a local git checkout, so apply them through the GitHub web UI or the `gh` CLI.

## Current repository

- Owner: `deepakaroraembedded-design`
- Repository: `ResumeRanker`
- URL: `https://github.com/deepakaroraembedded-design/ResumeRanker`

## Recommended settings

| Field | Recommended value |
|---|---|
| **Repository name** | `ResumeRanker` (already matches) or `resume-ranker` if you want the URL to match the package name |
| **Description** | `RESUME-RANKER — deterministic, explainable resume screening and scoring engine. Converts job descriptions + resumes into a ranked, evidence-backed shortlist with fairness guardrails. ` |
| **Website** | `https://github.com/deepakaroraembedded-design/ResumeRanker` (or a project docs site if you add one) |
| **Topics** | `resume-screening`, `ats`, `hiring`, `bias-detection`, `fairness`, `explainable-ai`, `nlp`, `job-descriptions`, `python`, `pydantic`, ` LGPL` |

## Recommended `gh` commands

If you have the `gh` CLI authenticated, run:

```bash
gh repo edit deepakaroraembedded-design/ResumeRanker \
  --description "RESUME-RANKER — deterministic, explainable resume screening and scoring engine. Converts job descriptions + resumes into a ranked, evidence-backed shortlist with fairness guardrails." \
  --homepage "https://github.com/deepakaroraembedded-design/ResumeRanker" \
  --add-topic "resume-screening,ats,hiring,bias-detection,fairness,explainable-ai,nlp,job-descriptions,python,pydantic,lgpl"
```

To add the metadata via the GitHub API (requires a token with `repo` scope):

```bash
OWNER=deepakaroraembedded-design
REPO=ResumeRanker
TOKEN=your_github_token

curl -L -X PATCH \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/$OWNER/$REPO" \
  -d '{
    "description": "RESUME-RANKER — deterministic, explainable resume screening and scoring engine. Converts job descriptions + resumes into a ranked, evidence-backed shortlist with fairness guardrails.",
    "homepage": "https://github.com/deepakaroraembedded-design/ResumeRanker",
    "topics": [
      "resume-screening",
      "ats",
      "hiring",
      "bias-detection",
      "fairness",
      "explainable-ai",
      "nlp",
      "job-descriptions",
      "python",
      "pydantic",
      "lgpl"
    ]
  }'
```

## Note on repository rename

The product/package name is `resume-ranker` (PyPI/CLI). If you want the GitHub
URL to match, rename the repository to `resume-ranker` and update your local
remote:

```bash
gh repo rename deepakaroraembedded-design/ResumeRanker --name resume-ranker
# or update the remote manually:
git remote set-url origin git@github.com:deepakaroraembedded-design/resume-ranker.git
```
