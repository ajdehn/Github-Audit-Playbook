import gatherEvidence
import os
import random
from utils import parse_dt, is_control_excluded, is_sample_excluded, callGithubApi
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# NOTE: Control results are set to "True" until an invalid control is identified.
@dataclass
class Control:
    control_id: str
    control_description: str
    test_procedures: List[str]
    test_attributes: List[str]
    audit: object
    table_headers: Optional[List[str]] = None
    include_sample_number: bool = False
    samples: List["Sample"] = field(default_factory=list)
    result: bool = True
    result_description: str = ""
    is_excluded: bool = False

    def __post_init__(self):
        # Set exclusion status AFTER object is created
        self.is_excluded = is_control_excluded(
            self.control_id,
            self.audit.config
        )

        if self.is_excluded:
            self.result = False
            self.result_description = "Control is excluded. See config.json"

    def __str__(self):
        return (
            f"control_id: {self.control_id}\n"
            f"control_description: {self.control_description}\n"
            f"is_excluded: {self.is_excluded}\n"
            f"result: {'Pass' if self.result else 'Fail'}\n"
            f"result_description: {self.result_description}\n"
        )

    def evaluate_all_samples(self):
        if self.is_excluded:
            return False
        
        # Remove excluded samples.
        in_scope_samples = [s for s in self.samples if not s.is_excluded]

        if not in_scope_samples:
            # Decide your policy here:
            return False  # safer default for audits

        return all(s.result for s in in_scope_samples)

# NOTE: Sample class will be used even when performing 100% testing (Ex. Branch Protection Rules).
# NOTE: Result is set to "False" until logic determines sample meets testing criteria.
@dataclass
class Sample:
    sample_id: Dict
    control_id: str
    result: bool = False
    is_excluded: bool = False
    comments: str = ""

    def __str__(self):
        return (
            f"sample_id: {self.sample_id}\n"
            f"result: {self.result}\n"
            f"comments: {self.comments}\n"
        )


def test_org_mfa_settings(audit, control_id):
    control_description = "The Github organization settings require users to enable MFA."
    test_procedures = [
        f"Retrieved the Github organization settings by calling: https://api.github.com/orgs/{audit.org_name}.",
        "Inspected 'org_settings.json' in the evidence folder to determine it is compliant with the test attributes below."        
    ]
    test_attributes = [
        "'two_factor_requirement_enabled' in org_settings.json is set to true."
    ]
    control = Control(control_id, control_description, test_procedures, test_attributes, audit)

    # Gather evidence.
    save_file_path = os.path.join(audit.evidence_folder, "org_settings.json")
    url = f"https://api.github.com/orgs/{audit.org_name}"
    org_settings = callGithubApi(audit, save_file_path, url)

    control.result = org_settings.get("two_factor_requirement_enabled")
    return control

def test_org_members_create_public_resources(audit, control_id):
    control_description = "The Github organization is configured to prevents members from creating public resources."
    test_procedures = [
        f"Retrieved the Github organization settings by calling: https://api.github.com/orgs/{audit.org_name}.",
        "Inspected 'org_settings.json' in the evidence folder to determine it is compliant with the test attributes below."
    ]
    test_attributes = [
        "'members_can_create_public_repositories' in org_settings.json is set to false.",
        "'members_can_create_public_pages' in org_settings.json is set to false."

    ]
    control = Control(control_id, control_description, test_procedures, test_attributes, audit)

    # Gather evidence.
    save_file_path = os.path.join(audit.evidence_folder, "org_settings.json")
    url = f"https://api.github.com/orgs/{audit.org_name}"
    org_settings = callGithubApi(audit, save_file_path, url)

    control.result = (
        not org_settings.get("members_can_create_public_repositories", True)
        and not org_settings.get("members_can_create_public_pages", True)
    )
    return control

# Run test and build report for change approvals.
def test_branch_protection_rules(audit, control_id):
    control_description = "Code repositories are configured to require an approval before the change is merged."
    test_procedures = [
        "Retrieved a list of all repositories in the Github organization.",
        "Worked with the engineering team to determine which repositories were in-scope for the audit.",
        "For each in-scope repository, retrieved the branch protection rules and rulesets.",
        "Inspected all in-scope repositories to determine if they were compliant with the test attributes below."
    ]
    test_attributes = [
        "An active ruleset OR branch protection rule is in enforced on the repository.",
        "Pull requests merging into the 'main' branch require at least one approval."
    ]
    table_headers = ["Repository Name", "Conclusion", "Comments"]
    control = Control(control_id, control_description, test_procedures, test_attributes, audit, table_headers = table_headers)

    # Get list of all repos. Paginate because orgs with many repos may exceed one page
    save_file_path = os.path.join(audit.evidence_folder, "all_repos.json")
    url = f"https://api.github.com/orgs/{audit.org_name}/repos"
    repos = callGithubApi(audit, save_file_path, url, paginate=True)

    # Audit Branch Protection Rules.
    for repo in repos:
        repo_name = repo["name"]
        # Gather evidence for each repo's branch protection rules.
        save_file_path = os.path.join(audit.evidence_folder, repo_name, "branch_protection_rules.json")
        os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
        # TODO: Make dynamic based on the name of the default branch.
        url = f"https://api.github.com/repos/{audit.org_name}/{repo_name}/branches/main/protection"
        branch_protection_rules = callGithubApi(audit, save_file_path, url, handle_404=True)


        # Gather evidence for each repo ruleset.
        save_file_path = os.path.join(audit.evidence_folder, repo_name, "rulesets.json")
        os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
        url = f"https://api.github.com/repos/{audit.org_name}/{repo_name}/rulesets"
        rulesets = callGithubApi(audit, save_file_path, url, handle_404=True)



        sample = Sample(
            sample_id = {"repo_name": repo_name},
            control_id=control_id
        )
        
        # Check if sample is in-scope
        if is_sample_excluded(control_id, sample, audit.config):
            sample.is_excluded = True
            sample.comments = "Sample excluded per config.json"
            control.samples.append(sample)
            continue
        # Sample is included. Evaluate rulesets and branch protection rules.
        sample = evaluate_branch_protection_rules(sample, branch_protection_rules, rulesets)
        control.samples.append(sample)
    # Document final control decision.
    
    control.result = control.evaluate_all_samples()
    return control


# Run test and build report for change approvals.
def test_change_approvals(audit, control_id):
    control_config = audit.config.get("control_config") or {}
    num_samples_per_repo = control_config.get("num_samples_per_repo", 15)
    control_description = "Code changes are approved by a separate user before they are deployed to production."
    test_procedures = [
        "Retrieved a list of all repositories in the Github organization.",
        "Worked with the engineering team to determine which repositories were in-scope for the audit.",
        f"For each in-scope repository, retrieved a list of merged pull requests.",
        f"Randomly sampled {num_samples_per_repo} PRs from each in-scope repo and tested for the attributes below."
    ]
    test_attributes = [
        "The pull request was approved before it was merged to the main branch.",
        "The pull request was opened and approved by separate users."
    ]
    table_headers = ["Sample Number", "Repository Name", "PR Number", "Conclusion", "Comments"]
    control = Control(control_id, control_description, test_procedures, test_attributes, audit, table_headers = table_headers, include_sample_number = True)

    # Get list of all repos. Paginate because orgs with many repos may exceed one page
    save_file_path = os.path.join(audit.evidence_folder, "all_repos.json")
    url = f"https://api.github.com/orgs/{audit.org_name}/repos"
    repos = callGithubApi(audit, save_file_path, url, paginate=True)

    for repo in repos:
        repo_name = repo["name"]
        # Gather evidence from each individual repo.
        save_file_path = os.path.join(audit.evidence_folder, repo_name, "all_prs.json")
        os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
        query = f"repo:{audit.org_name}/{repo_name} is:pr is:merged merged:{audit.start_date}..{audit.end_date}"
        url = "https://api.github.com/search/issues"
        all_prs = callGithubApi(audit, save_file_path, url, params={"q": query, "per_page": 100})

        total_prs = len(all_prs["items"])
        num_samples = min(num_samples_per_repo, total_prs) # Choose the lesser of len(prs) or audit.sample_size
        # Filter all_prs.json file down to a list of only PR numbers.
        all_pr_numbers = [pr["number"] for pr in all_prs["items"]]
        # Randomly select PRs for sampling. Sort to make final report cleaner.
        prs_to_sample = sorted(random.sample(all_pr_numbers, k=num_samples))
        # Save relevant evidence for each selected PR.
        pr_lookup = {pr["number"]: pr for pr in all_prs["items"]}
        for pr_number in prs_to_sample:
            pr = pr_lookup[pr_number]
            sample = evaluate_pr_approval(audit, pr, control_id)
            control.samples.append(sample)
    # Document final control decision.
    control.result = control.evaluate_all_samples()
    return control


def evaluate_pr_approval(audit, pr, control_id):
    repo_name = pr["repository_url"].split("/")[-1]
    pr_number = pr["number"]
    sample = Sample(
        sample_id={
            "repo_name": repo_name,
            "pr_number": pr_number
        },
        control_id=control_id
    )

    merged_at = parse_dt(pr["pull_request"]["merged_at"])
    sample.merged_at = merged_at
    sample.author = pr["user"]["login"]

    if not merged_at:
        sample.comments = "Invalid sample. PR was not merged."
        return sample

    save_file_path = os.path.join(audit.evidence_folder, repo_name, "prs", str(pr_number), "reviews.json")
    os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
    url = f"https://api.github.com/repos/{audit.org_name}/{repo_name}/pulls/{pr_number}/reviews"
    reviews = callGithubApi(audit, save_file_path, url)


    valid_approvals = [
        r for r in reviews
        if r["state"] == "APPROVED"
        and r.get("submitted_at")
        and parse_dt(r["submitted_at"]) < merged_at
        and not r.get("dismissed", False)
    ]

    if not valid_approvals:
        sample.result = False
        sample.comments = "No valid approvals before merge"
        return sample

    # NOTE: There is a valid approval based. Github functionality does not allow approvals post merge.
    approved_by_separate_user = False

    for r in valid_approvals:
        reviewer = r["user"]["login"]
        if reviewer != sample.author:
            approved_by_separate_user = True
            break

    sample.result = approved_by_separate_user

    if sample.result:
        sample.comments = "Valid approval before merge by non-author."
    elif not sample.approved_by_separate_user:
        sample.comments = "Self-approval."
    else:
        sample.comments = "PR was merged before code change was approved."

    return sample


def evaluate_branch_protection_rules(sample, branch_protection, rulesets):
    repo_name = sample.sample_id.get("repo_name")
    has_any_protection = False
    requires_approval = False

    # ---------------------------
    # 1. Evaluate classic branch protection
    # ---------------------------
    if branch_protection:
        has_any_protection = True

        pr_reviews = branch_protection.get("required_pull_request_reviews")
        if pr_reviews:
            if pr_reviews.get("required_approving_review_count", 0) >= 1:
                requires_approval = True

    # ---------------------------
    # 2. Evaluate rulesets (new GitHub model)
    # ---------------------------
    if rulesets:
        for ruleset in rulesets:
            if ruleset.get("enforcement") != "active":
                continue  # Ignore inactive rules

            has_any_protection = True

            for rule in ruleset.get("rules", []):
                # Look for PR approval requirement
                if rule.get("type") == "pull_request":
                    params = rule.get("parameters", {})
                    if params.get("required_approving_review_count", 0) >= 1:
                        requires_approval = True

    # ---------------------------
    # 3. Final evaluation
    # ---------------------------
    if not has_any_protection:
        sample.comments = "No branch protection rules or rulesets configured"
        return sample

    if not requires_approval:
        sample.comments = "Branch protection exists but does not require PR approval"
        return sample

    # PASS
    sample.result = True
    sample.comments = "Branch protection or ruleset requires PR approval"

    return sample

def test_authorized_oauth_apps(audit, control_id):
    """
    Control: Ensure only approved OAuth apps are authorized for the account/org.
    """
    control_description = "Only approved OAuth applications are authorized for the GitHub account."
    test_procedures = [
        "Retrieved the list of authorized OAuth apps via the GitHub API.",
        "Compared each authorized app against the approved applications list in the config."
    ]
    test_attributes = [
        "All OAuth apps must be approved and documented in the audit config.",
        "No unauthorized or unknown OAuth apps should exist."
    ]
    table_headers = ["OAuth App Name", "Conclusion", "Comments"]
    
    control = Control(control_id, control_description, test_procedures, test_attributes, audit, table_headers=table_headers)

    oauth_apps = gatherEvidence.get_authorized_oauth_apps(audit)  # Returns list of dicts with 'name' & 'id'

    approved_apps = audit.config.get("approved_oauth_apps", [])
    
    for app in oauth_apps:
        sample = Sample(
            sample_id={"app_name": app["name"], "app_id": app["id"]},
            control_id=control_id
        )
        if app["name"] in approved_apps:
            sample.result = True
            sample.comments = "Approved OAuth app"
        else:
            sample.result = False
            sample.comments = "Unauthorized OAuth app detected"
        control.samples.append(sample)

    control.result = control.evaluate_all_samples()
    return control


def test_personal_access_tokens(audit, control_id):
    """
    Control: Ensure personal access tokens (PATs) are valid, rotated, and scoped appropriately.
    """
    control_description = "All Personal Access Tokens (PATs) are valid, rotated, and minimally scoped."
    test_procedures = [
        "Retrieved all PATs associated with the account via the GitHub API.",
        "Checked each PAT for expiration date and assigned scopes against minimum required."
    ]
    test_attributes = [
        "No expired PATs exist.",
        "PAT scopes are restricted to minimum required permissions.",
        "All PATs are rotated per organizational policy."
    ]
    table_headers = ["Token Name", "Conclusion", "Comments"]

    control = Control(control_id, control_description, test_procedures, test_attributes, audit, table_headers=table_headers)

    pats = gatherEvidence.get_personal_access_tokens(audit)  # Returns list of dicts with 'name', 'expires_at', 'scopes'

    for token in pats:
        sample = Sample(
            sample_id={"token_name": token["name"]},
            control_id=control_id
        )
        expired = token.get("expires_at") and datetime.utcnow() > parse_dt(token["expires_at"])
        excessive_scope = any(scope not in audit.config.get("allowed_pat_scopes", []) for scope in token.get("scopes", []))

        if expired:
            sample.result = False
            sample.comments = "Token has expired"
        elif excessive_scope:
            sample.result = False
            sample.comments = f"Token has excessive scopes: {token['scopes']}"
        else:
            sample.result = True
            sample.comments = "Token is valid and appropriately scoped"
        
        control.samples.append(sample)

    control.result = control.evaluate_all_samples()
    return control


def test_repository_visibility(audit, control_id):
    """
    Control: Ensure no sensitive repositories are public.
    """
    control_description = "All sensitive repositories are private or restricted."
    test_procedures = [
        "Retrieved a list of all repositories in the organization/account.",
        "Checked repository visibility against the audit config to ensure sensitive repos are not public."
    ]
    test_attributes = [
        "No sensitive or classified repositories are public.",
        "Public repositories comply with the organization's data classification policy."
    ]
    table_headers = ["Repository Name", "Conclusion", "Comments"]

    control = Control(control_id, control_description, test_procedures, test_attributes, audit, table_headers=table_headers)

    # Get list of all repos. Paginate because orgs with many repos may exceed one page
    save_file_path = os.path.join(audit.evidence_folder, "all_repos.json")
    url = f"https://api.github.com/orgs/{audit.org_name}/repos"
    repos = callGithubApi(audit, save_file_path, url, paginate=True)

    sensitive_repos = audit.config.get("sensitive_repos", [])

    for repo in repos:
        sample = Sample(
            sample_id={"repo_name": repo["name"]},
            control_id=control_id
        )
        if repo["name"] in sensitive_repos and not repo.get("private", True):
            sample.result = False
            sample.comments = "Sensitive repository is public"
        else:
            sample.result = True
            sample.comments = f"Repository visibility is compliant ({'private' if repo.get('private') else 'public'})"
        control.samples.append(sample)

    control.result = control.evaluate_all_samples()
    return control
