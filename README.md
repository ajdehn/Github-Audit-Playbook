## About
This playbook was written by [AJ Dehn](https://www.linkedin.com/in/ajdehn/) founder of [AuditOps.io](https://www.auditops.io/). The goal of this project is to help auditors conduct **Github audits, without screenshots**.

## Benefits for Auditors:
* High quality, automated evidence collection generated directly from the Github API.
* Elimates the needs for sampling PR's. Samples can be made automatically using Python's [random](https://docs.python.org/3/library/random.html) library.

## Benefits for Clients:
* Time Savings: No more time wasted gathering screenshots of Github.
* Risk Mitigation: Performing in-depth audits protects your organization from real risk (lack of MFA, aged credentials, etc).

## Setup Instructions
1. Pre-requisites: Git and Python must already be installed.
2. Clone github repository.
3. Create a Fine Grained Person Access token in Github [LINK](https://github.com/settings/personal-access-tokens/new).
4. Token Setup Instructions:
   * Token Name: gh_evidence_collector
   * Description: Grants access for the audit team to pull evidence directly from Github.
   * Resource Owner: Select your Github organization in the dropdown.
   * Expiration: Decide how often you rotate the key based on your company policy. A good starting point is between 90 - 365 days.
5. Repository Access: I recommend selecting "All repositories". If you can't get those permissions, discuss with your engineering contacts to agree on which repos are in scope.
6. Add the following permissions:
    * Metadata (Read-only)
    * Administration (Read-only)
    * Pull requests (Read-only)
7. Create and populate the .env file.
```
org_name = "COMPANY_NAME"
github_token = "RANDOM_STRING_FROM_GITHUB"
start_date = "YYYY-MM-DD"
end_date = "YYYY-MM-DD"
samples_per_repo = 5 # Update for your organization.
```
8. Run the scan, `python src/runAudit.py`
