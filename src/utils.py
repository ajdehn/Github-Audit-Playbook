import json
import os
import shutil
import requests
from datetime import datetime, timezone

def confirmDeleteFolder(folder_path):
    if os.path.exists(folder_path):
        confirm = input(f"Folder '{folder_path}' exists. Do you want to delete it? (y/N): ").strip().lower()
        
        if confirm == "y":
            shutil.rmtree(folder_path)
            print("Deleting old evidence folder.")
        elif confirm == "N":
            print("Using cached evidence.")
        else:
            print("Aborted. Folder not deleted.")

def load_config(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

"""
Returns True if the control is excluded.
"""
def is_control_excluded(test_id, config):
    for e in config["control_exclusions"].get(test_id, []):
        if is_exclusion_active(e):
            return True
    return False

"""
Returns True if exclusion is active.
"""
def is_exclusion_active(exclusion):
    today = datetime.utcnow().date()
    if exclusion.get("permanent"):
        return True
    exp_date = exclusion.get("expiration_date")
    if exp_date:
        exp_date = datetime.strptime(exp_date, "%Y-%m-%d").date()
        return exp_date >= today
    return False

def check_sample_exclusion(test_id, sample, config):
    if is_sample_excluded(test_id, sample, config):
        sample.is_excluded = True
        sample.comments = "Sample is excluded. See config.json"
        return sample
    return sample

"""
Returns True if a sample is excluded.
"""
def is_sample_excluded(test_id, sample, config):
    for e in config["sample_exclusions"].get(test_id, []):
        config_sample_id = e.get("sample_id", {})
        match_sample_id = sample.sample_id

        if all(match_sample_id.get(key) == value for key, value in config_sample_id.items()):
            if is_exclusion_active(e):
                return True

    return False

"""
    Saves a json file to a specified path
"""
def save_json(extract, filePath):
    # isolating out the directory path to the file and creating the directory
    brokenUpPath = filePath.split('/')
    dirPathToFile = '/'.join(brokenUpPath[:len(brokenUpPath) - 1])
    # Create file path if it doesn't already exist.
    if not os.path.exists(dirPathToFile):
        os.makedirs(dirPathToFile)

    with open(filePath, 'w') as f:
        json.dump(extract, f, indent=4, default=str)
    f.close()

def load_json_if_exists(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Invalid JSON file. File path {file_path}")
            return None
    return None

"""
    Fetches JSON data from Github API with caching, pagination, and optional 404 handling.

    Args:
        audit: Audit object containing gh_token and evidence_folder
        relative_path: file path describing where evidence should be saved in the evidence folder (e.g., repositories/[repo_name]/buckets.json)
        github_url: Github API endpoint
        params: Optional dictionary of query parameters
        paginate: If True, fetch all pages automatically
        handle_404: If True, return None instead of raising exception on 404

    Returns:
        dict or list: JSON data from API
"""
def call_github_api(audit, relative_path, github_url, params=None, paginate=False, handle_404=False):
    # Return cached evidence if it exists

    save_file_path = os.path.join(audit.evidence_folder, relative_path)
    if os.path.exists(save_file_path):
        return load_json_if_exists(save_file_path)
    
    os.makedirs(os.path.dirname(save_file_path), exist_ok=True)

    headers = {"Authorization": f"token {audit.gh_token}"}

    if paginate:
        all_data = []
        page = 1
        while True:
            page_params = params.copy() if params else {}
            page_params.update({"per_page": 100, "page": page})
            res = requests.get(github_url, headers=headers, params=page_params)
            
            if handle_404 and res.status_code == 404:
                return None
            res.raise_for_status()

            page_data = res.json()
            if not page_data:
                break

            all_data.extend(page_data)
            page += 1

        save_json(all_data, save_file_path)
        return all_data

    else:
        res = requests.get(github_url, headers=headers, params=params)
        if handle_404 and res.status_code == 404:
            return None
        res.raise_for_status()
        json_data = res.json()
        save_json(json_data, save_file_path)
        return json_data

def parse_dt(dt_str):
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))