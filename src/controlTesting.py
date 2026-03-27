import gatherEvidence
import random
from utils import parse_dt
from datetime import datetime

class Control:
    def __init__(self, ctrl_id, ctrl_desc, test_procedures, test_attributes, table_headers=None, include_sample_number=False):
        self.ctrl_id = ctrl_id
        self.ctrl_desc = ctrl_desc
        self.test_procedures = test_procedures
        self.test_attributes = test_attributes
        self.table_headers = table_headers # NOTE: If test attributes aren't included, no table is required
        self.include_sample_number = include_sample_number       
        self.samples = []
        self.findings = []
        self.exclusions = []
        self.result = True  # NOTE: Set as 'True' by default. Will change to 'False' when a sample fails.

    def __str__(self):
        return (
                f"ctrl_id: {self.ctrl_id}\n"
                f"ctrl_desc: {self.ctrl_desc}\n"
                f"result: {'Pass' if self.result else 'Fail'}\n"
                f"include_sample_number: {self.include_sample_number}\n"
                f"test_attributes: {self.test_attributes}"
            )
"""
    NOTE: Sample class will be used even when performing 100% testing (Ex. Branch Protection Rules).
"""
class Sample:
    def __init__(self, sample_id, ctrl_id, test_attributes=None):
        self.sample_id = sample_id
        self.ctrl_id = ctrl_id
        self.result = False # NOTE: Set as 'False' by default. Will only change to 'True' after evaluation.
        self.comments = ""
    
    def __str__(self):
            return f"result: {self.result}\nsample_id: {self.sample_id}\ntesting_attributes: {self.testing_attributes}\ncomments:{self.comments}"    

# TODO: Implement exclusion logic.
class Exclusion:
    def __init__(self, exclusion_id, rationale, expiration_date):
        self.exclusion_id = exclusion_id
        self.rationale = rationale
        self.expiration_date = expiration_date

def test_org_mfa_settings(audit):
    ctrl_id = "IAM2"
    ctrl_desc = "Github organization settings require MFA to be enabled."
    test_procedures = [
        "Internal Audit (IA) obtained and inspected the org-wide MFA settings."
    ]
    test_attributes = [
        "two_factor_requirement_enabled was set to true."
    ]
    ctrl = Control(ctrl_id, ctrl_desc, test_procedures, test_attributes)
    org_settings = gatherEvidence.get_org_settings(audit)
    ctrl.result = org_settings.get("two_factor_requirement_enabled")
    return ctrl

# Run test and build report for change approvals.
def test_branch_protection_rules(audit):
    ctrl_id = "CM1"
    ctrl_desc = "Code repositories have branch protection rules enabled."
    test_procedures = [
        "Internal Audit (IA) obtained and inspected a list of all repositories in the Github organization.",
        "IA worked with the engineering team to determine which repositories were in-scope for the audit.",
        "For each in-scope repository, IA gathered a the branch protection rules and rulesets.",
        "IA inspected all in-scope rulesets testing checking for the test attributes below."
    ]
    test_attributes = [
        "An active ruleset OR branch protection rule is in enforced on the repository.",
        "Pull requests merging into the 'main' branch require at least one approval."
    ]
    table_headers = ["Sample Number", "Repository Name", "Conclusion", "Comments"]
    ctrl = Control(ctrl_id, ctrl_desc, test_procedures, test_attributes, table_headers = table_headers)

    # Get list of all repositories.
    repos = gatherEvidence.get_repos(audit)

    # Audit Branch Protection Rules.
    for repo in repos:
        branch_protection_rules = gatherEvidence.get_branch_protection(audit, repo["name"])
        rulesets = gatherEvidence.get_repo_rulesets(audit, repo["name"])
        sample = evaluate_branch_protection_rules(branch_protection_rules, rulesets, repo["name"], ctrl_id)
        ctrl.samples.append(sample)
    # Document final control decision.
    ctrl.result = all(s.result for s in ctrl.samples)
    return ctrl


# Run test and build report for change approvals.
def test_change_approvals(audit):
    ctrl_id = "CM2"
    ctrl_desc = "Code changes are approved by a separate user before they are deployed to production."
    test_procedures = [
        "Internal Audit (IA) obtained and inspected a list of all repositories in the Github organization.",
        "IA worked with the engineering team to determine which repositories were in-scope for the audit.",
        f"For each in-scope repository, IA gathered a list of merged pull requests (PR).",
        f"IA randomly sampled {audit.sample_size} PRs from each in-scope repo and tested for the attributes below."
    ]
    test_attributes = [
        "The PR was approved before it was merged to the main branch.",
        "The PR was opened and approved by separate users."
    ]
    table_headers = ["Sample Number", "Repository Name", "PR Number", "Conclusion", "Comments"]
    ctrl = Control(ctrl_id, ctrl_desc, test_procedures, test_attributes, table_headers = table_headers, include_sample_number = True)
    # Get list of all repos. 
    repos = gatherEvidence.get_repos(audit)
    # Gather evidence from each individual repo.
    for repo in repos:
        all_prs = gatherEvidence.get_prs(audit, repo["name"])
        total_prs = len(all_prs["items"])
        num_samples = min(audit.sample_size, total_prs) # Choose the lesser of len(prs) or audit.sample_size
        # Filter all_prs.json file down to a list of only PR numbers.
        all_pr_numbers = [pr["number"] for pr in all_prs["items"]]
        # Randomly select PRs for sampling. Sort to make final report cleaner.
        prs_to_sample = sorted(random.sample(all_pr_numbers, k=num_samples))
        # Save relevant evidence for each selected PR.
        pr_lookup = {pr["number"]: pr for pr in all_prs["items"]}
        for pr_number in prs_to_sample:
            pr = pr_lookup[pr_number]
            sample = evaluate_pr_approval(audit, pr, ctrl_id)
            ctrl.samples.append(sample)
    # Document final control decision.
    ctrl.result = all(s.result for s in ctrl.samples)
    return ctrl


def evaluate_pr_approval(audit, pr, ctrl_id):
    sample = Sample(
        sample_id={
            "repo_name": pr["repository_url"].split("/")[-1],
            "pr_number": pr["number"]
        },
        ctrl_id=ctrl_id
    )

    merged_at = parse_dt(pr["pull_request"]["merged_at"])
    sample.merged_at = merged_at
    sample.author = pr["user"]["login"]

    if not merged_at:
        sample.comments = "Invalid sample. PR was not merged."
        return sample

    reviews = gatherEvidence.get_pr_reviews(audit, sample.sample_id["repo_name"], pr["number"])

    valid_approvals = [
        r for r in reviews
        if r["state"] == "APPROVED"
        and r.get("submitted_at")
        and parse_dt(r["submitted_at"]) < merged_at
        and not r.get("dismissed", False)
    ]

    if not valid_approvals:
        sample.comments = "No valid approvals before merge"
        return sample

    sample.approved_before_merge = True

    for r in valid_approvals:
        reviewer = r["user"]["login"]
        if reviewer != sample.author:
            sample.approver = reviewer
            sample.approved_by_separate_user = True
            break

    sample.result = sample.approved_before_merge and sample.approved_by_separate_user

    if sample.result:
        sample.comments = "Valid approval before merge by non-author"
    elif not sample.approved_by_separate_user:
        sample.comments = "Self-approval"
    else:
        sample.comments = "PR was merged before code change was approved."

    return sample


def evaluate_branch_protection_rules(branch_protection, rulesets, repo_name, ctrl_id):
    sample = Sample(
        sample_id={"repo_name": repo_name},
        ctrl_id=ctrl_id
    )

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
