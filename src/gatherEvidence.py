import os
from utils import saveJson, load_json_if_exists, callGithubApi

"""
Returns a list of all repositories in an organization's Github environment.
Args:
    audit: Class containing metadata for this specific audit.
Returns:
    list: All repositories in the Github environment.
"""
def get_repos(audit):
    save_file_path = os.path.join(audit.evidence_folder, "all_repos.json")
    url = f"https://api.github.com/orgs/{audit.org_name}/repos"
    
    # Paginate because orgs with many repos may exceed one page
    return callGithubApi(audit, save_file_path, url, paginate=True)

"""
Returns a list of MERGED pull requests for a specific repository within the date range.
Args:
    audit: Class containing metadata for this specific audit.
    repo_name: Name of the repository to search pull requests.
Returns:
    dict: Search results JSON from Github.
"""
def get_prs(audit, repo_name):
    save_file_path = os.path.join(audit.evidence_folder, repo_name, "all_prs.json")
    os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
    
    query = f"repo:{audit.org_name}/{repo_name} is:pr is:merged merged:{audit.start_date}..{audit.end_date}"
    url = "https://api.github.com/search/issues"
    
    return callGithubApi(audit, save_file_path, url, params={"q": query, "per_page": 100})

"""
Returns repository rulesets.
Args:
    audit: Class containing metadata for this specific audit.
    repo_name: Name of the repository.
Returns:
    dict or None: JSON from Github, or None if 404.
"""
def get_repo_rulesets(audit, repo_name):
    save_file_path = os.path.join(audit.evidence_folder, repo_name, "rulesets.json")
    os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
    
    url = f"https://api.github.com/repos/{audit.org_name}/{repo_name}/rulesets"
    return callGithubApi(audit, save_file_path, url, handle_404=True)

"""
Returns branch protection rules for a specific branch.
Args:
    audit: Class containing metadata for this specific audit.
    repo_name: Name of the repository.
    branch: Branch name (default "main").
Returns:
    dict or None: JSON from Github, or None if 404.
"""
def get_branch_protection(audit, repo_name, branch="main"):
    save_file_path = os.path.join(audit.evidence_folder, repo_name, "branch_protection_rules.json")
    os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
    
    url = f"https://api.github.com/repos/{audit.org_name}/{repo_name}/branches/{branch}/protection"
    return callGithubApi(audit, save_file_path, url, handle_404=True)

"""
Returns a JSON file describing who approved a pull request.
Args:
    audit: Class containing metadata for this specific audit.
    repo_name: Name of the repository.
    pr_number: Pull request number.
Returns:
    list: JSON list of reviews for the PR.
"""
def get_pr_reviews(audit, repo_name, pr_number):
    save_file_path = os.path.join(audit.evidence_folder, repo_name, "prs", str(pr_number), "reviews.json")
    os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
    
    url = f"https://api.github.com/repos/{audit.org_name}/{repo_name}/pulls/{pr_number}/reviews"
    return callGithubApi(audit, save_file_path, url)
