from dotenv import load_dotenv
import controlTesting
import random
import os
from utils import generate_pdf_report

class Audit:
    """
    Contains audit metadata.
    """
    def __init__(self, org_name, start_date, end_date, sample_size, gh_token, evidence_folder="tmp/audit_evidence"):
        """
        Initializes the audit instance with the provided four attributes.
        """
        self.gh_token = gh_token                # Authentication token to analyze the Github environment.
        self.org_name = org_name                # Github organization name (Ex. AuditOps)
        self.start_date = start_date            # Start date of the audit period (YYYY-MM-DD)
        self.end_date = end_date                # Final date of the audit period (YYYY-MM-DD)
        self.sample_size = sample_size          # Maxiumum number of samples per repo (Ex. 5)
        self.evidence_folder = evidence_folder  # Name of the evidence_folder

if __name__ == "__main__":
    # Load variables from .env file
    load_dotenv()
    audit = Audit(os.getenv("org_name"), os.getenv("start_date"), os.getenv("end_date"), 
    int(os.getenv("samples_per_repo")), os.getenv("github_token"))

    print("Running the Github Audit Playbook (maintained by AJ Dehn - AuditOps.io)")
    controls = []

    # Test branch protection rules
    controls.append(controlTesting.test_branch_protection_rules(audit))

    # Test change approvals
    controls.append(controlTesting.test_change_approvals(audit))

    generate_pdf_report(audit, controls, "tmp/github_audit_report.pdf")
