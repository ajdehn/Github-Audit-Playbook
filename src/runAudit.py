from dotenv import load_dotenv
import controlTesting
import os
from utils import confirmDeleteFolder, load_config
from buildReport import generate_pdf_report

class Audit:
    """
    Initializes the audit instance with the provided attributes.
    """
    def __init__(self, org_name, start_date, end_date, gh_token, evidence_folder="tmp/audit_evidence", config_file_path="config.json"):
        self.gh_token = gh_token                                    # Authentication token to analyze the Github environment.
        self.org_name = org_name                                    # Github organization name (Ex. AuditOps)
        self.start_date = start_date                                # Start date of the audit period (YYYY-MM-DD)
        self.end_date = end_date                                    # Final date of the audit period (YYYY-MM-DD)
        self.evidence_folder = evidence_folder                      # Name of the evidence_folder
        self.config = load_config(config_file_path)                 # Control and sample exclusions

if __name__ == "__main__":
    # Load variables from .env file
    load_dotenv()
    audit = Audit(os.getenv("org_name"), os.getenv("start_date"), os.getenv("end_date"), os.getenv("github_token"))

    print("Running the Github Audit Playbook (maintained by AJ Dehn - AuditOps.io)\n")
    controls = []

    confirmDeleteFolder(audit.evidence_folder)
    controls.append(controlTesting.test_org_mfa_settings(audit, "C1000"))
    controls.append(controlTesting.test_branch_protection_rules(audit, "C2000"))
    controls.append(controlTesting.test_change_approvals(audit, "C2010"))
    controls.append(controlTesting.test_org_members_create_public_repo_settings(audit, "C2020"))
    #controls.append(controlTesting.test_authorized_oauth_apps(audit, "C2030"))
    #controls.append(controlTesting.test_personal_access_tokens(audit, "C2040"))
    #controls.append(controlTesting.test_repository_visibility(audit, "C2050"))

    generate_pdf_report(audit, controls, "tmp/github_audit_report.pdf")
