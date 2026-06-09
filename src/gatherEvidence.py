import os
from utils import call_github_api

def get_authorized_oauth_apps(audit):
    """
    Retrieves the list of authorized OAuth Apps for the authenticated user/org.
    Returns a list of dicts with 'name', 'id', 'client_id', 'created_at'.
    """
    save_file_path = os.path.join(audit.evidence_folder, "authorized_oauth_apps.json")

    # For organization installations
    url = f"https://api.github.com/orgs/{audit.org_name}/installations"

    installations = callGithubApi(audit, save_file_path, url, paginate=True)

    # Normalize into list of apps
    apps = []
    for inst in installations.get("installations", installations):
        app = inst.get("app", {})
        apps.append({
            "name": app.get("name"),
            "id": app.get("id"),
            "client_id": app.get("client_id"),
            "created_at": app.get("created_at")
        })
    
    return apps