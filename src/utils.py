import json
import os
import shutil
import requests
from datetime import datetime, timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, LETTER
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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

"""
    Saves a json file to a specified path
"""
def saveJson(extract, filePath):
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
        save_file_path: Local path to save JSON evidence
        github_url: Github API endpoint
        params: Optional dictionary of query parameters
        paginate: If True, fetch all pages automatically
        handle_404: If True, return None instead of raising exception on 404

    Returns:
        dict or list: JSON data from API
"""
def callGithubApi(audit, save_file_path, github_url, params=None, paginate=False, handle_404=False):
    # Return cached evidence if it exists
    if os.path.exists(save_file_path):
        return load_json_if_exists(save_file_path)

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

        saveJson(all_data, save_file_path)
        return all_data

    else:
        res = requests.get(github_url, headers=headers, params=params)
        if handle_404 and res.status_code == 404:
            return None
        res.raise_for_status()
        json_data = res.json()
        saveJson(json_data, save_file_path)
        return json_data


def generate_pdf_report(audit, controls, filename="github_audit_report.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=letter,
    title="Github Audit Report", author="AJ Dehn", subject="Summarizes audit findings from Github")
    styles = getSampleStyleSheet()
    page_width, page_height = LETTER 

    elements = []

    # Add Report Title
    elements.append(Paragraph("Github Audit Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"<b>Date:</b> {datetime.now(timezone.utc).strftime("%Y-%m-%d")}", styles["Normal"]))
    elements.append(Spacer(1, 6))

    # Add controls to the report
    for control in controls:
        # Populate Control Description, Conclusion, Test Procedures, and Test Attributes
        elements.append(Paragraph(f"<b>Control Description:</b> {control.ctrl_desc}", styles["Normal"]))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"<b>Conclusion:</b> {"Pass" if control.result else "Fail"}", styles["Normal"]))
        elements.append(Spacer(1, 6))

        # Add test procedures (ordered list) to the report
        elements.append(Paragraph(f"<b>Test Procedures:</b>", styles["Normal"]))
        test_procedure_flowable_items = []
        for item in control.test_procedures:
            test_procedure_flowable_items.append(ListItem(Paragraph(item, styles["Normal"])))
        elements.append(ListFlowable(test_procedure_flowable_items, bulletType='1', start='1'))
        elements.append(Spacer(1, 12))

        # Add test attributes (unordered list) to the report
        elements.append(Paragraph(f"<b>Test Attributes:</b>", styles["Normal"]))
        test_attribute_flowable_items = []
        for item in control.test_attributes:
            test_attribute_flowable_items.append(ListItem(Paragraph(item, styles["Normal"])))
        elements.append(ListFlowable(test_attribute_flowable_items, bulletType='bullet'))
        elements.append(Spacer(1, 12))

        if control.table_headers:
            # Build audit results table
            table_data = []
            table_header_style = ParagraphStyle(name='TableHeader', fontSize=9, leading=11, alignment=1, spaceAfter=0)
            table_cell_style = ParagraphStyle(name='TableCell', fontSize=8, leading=10)
            
            headers_wrapped = [Paragraph(h, table_header_style) for h in control.table_headers]
            table_data.append(headers_wrapped)
            # Populate rows into audit results table
            sample_number = 1 # Only used if include_sample_number is True
            for sample in control.samples:
                wrapped_row = []
                if control.include_sample_number:
                    wrapped_row.append(sample_number)            
                for item in sample.sample_id:
                    wrapped_row.append(Paragraph(str(sample.sample_id.get(item)), table_cell_style))
                
                if sample.result:
                    wrapped_row.append("Pass")
                else:
                    control.result = False
                    fail_text = "Fail"
                    # Highlight text when change fails.     
                    wrapped_row.append(Paragraph(f'<font color="red">{fail_text}</font>'))
                    # Add comments when sample fails
                    wrapped_row.append(Paragraph(str(sample.comments), table_cell_style))
                table_data.append(wrapped_row)
                sample_number = sample_number + 1

            # Make table width = page width minus margins
            table_width = page_width - 2 * 72  # assuming 1-inch margins
            col_width = table_width / len(table_data[0])  # divide evenly across columns
            col_widths = [col_width] * len(table_data[0])
            # Create table
            table = Table(table_data, colWidths=col_widths)
            table.hAlign = "LEFT"
            # Style the table
            style = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),        
            ])
            table.setStyle(style)
            elements.append(table)
            # Add space after the table.
            elements.append(Spacer(1, 20))

    # Build PDF
    doc.build(elements)
    print(f"Report generated: {filename}")

def parse_dt(dt_str):
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
