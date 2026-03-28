import json
import os
import shutil
import requests
from datetime import datetime, timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, LETTER
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, ListFlowable, ListItem, PageBreak
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

"""
    Render 2-column control summary table.
"""
def render_control_summary(control, page_width, label_style, value_style, list_style, center_style):
    test_procedures = [
        Paragraph(f"{i+1}. {item}", list_style)
        for i, item in enumerate(control.test_procedures)
    ]
    test_attributes = [
        Paragraph(f"• {item}", list_style)
        for item in control.test_attributes
    ]

    # Conclusion
    conclusion = Paragraph(
        f"<font color='{ 'green' if control.result else 'red' }'><b>{'Pass' if control.result else 'Fail'}</b></font>",
        value_style
    )

    # Build summary table
    table_data = [ 
        [Paragraph("Control ID", label_style), Paragraph(control.control_id, value_style)], 
        [Paragraph("Control Description", label_style), Paragraph(control.control_description, value_style)], 
        [Paragraph("Conclusion", label_style), conclusion], 
        [Paragraph("Test Procedures", label_style), test_procedures], 
        [Paragraph("Test Attributes", label_style), test_attributes],
    ]

    table_width = page_width - 2 * 72
    table = Table(table_data, colWidths=[table_width * 0.25, table_width * 0.75])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    return table

"""
    Render sample results table (if present).
"""
def render_sample_table(control, page_width, label_style, value_style, center_style):
    if not control.table_headers:
        return None

    table_data = []
    # Header row
    table_data.append([
        Paragraph(h, label_style) for h in control.table_headers
    ])
    for i, sample in enumerate(control.samples, 1):
        row = []
        if control.include_sample_number:
            row.append(Paragraph(str(i), center_style))
        row.extend([
            Paragraph(str(v), value_style)
            for v in sample.sample_id.values()
        ])

        # Result
        result_text = "Pass" if sample.result else "Fail"
        result_color = "green" if sample.result else "red"
        row.append(Paragraph(f"<font color='{result_color}'>{result_text}</font>", center_style))

        if not sample.result:
            # Fail control if one sample fails
            # TODO: Consider if this is necessary. I thought this would be completed in controlTesting.py
            control.result = False
            row.append(Paragraph(str(sample.comments), value_style))

        table_data.append(row)

    table_width = page_width - 2 * 72
    col_width = table_width / len(table_data[0]) # divide evenly across columns
    col_widths = [col_width] * len(table_data[0])
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    return table

def render_summary_page(controls, styles):
    """Build summary page with pass/fail counts."""
    total = len(controls)
    passed = sum(1 for c in controls if c.result)
    failed = total - passed

    elements = []

    elements.append(Paragraph("Audit Summary", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    summary_data = [
        ["Total Controls", str(total)],
        ["Passed", str(passed)],
        ["Failed", str(failed)],
    ]

    table = Table(summary_data, colWidths=[200, 100])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 24))

    return elements

def make_cell(text, style, color=None, align=None):
    """
    Helper to create consistently styled table cells.
    """
    if color:
        style = ParagraphStyle(
            name=f"{style.name}_colored",
            parent=style,
            textColor=color
        )
    if align is not None:
        style = ParagraphStyle(
            name=f"{style.name}_aligned",
            parent=style,
            alignment=align
        )
    return Paragraph(str(text), style)

def build_numbered_list(items, style):
    flowables = []
    for i, item in enumerate(items, 1):
        flowables.append(Paragraph(f"{i}. {item}", style))
    return flowables

def build_bullet_list(items, style):
    flowables = []
    for item in items:
        flowables.append(Paragraph(f"• {item}", style))
    return flowables


"""
Build audit report summarizing findings.

Structure:
    1. Header
    2. Summary Page
    3. Detailed Findings
        - Control Summary
        - Sample Findings
        - TODO: Exclusions (Option to select summary or detail version)
"""
def generate_pdf_report(audit, controls, filename="github_audit_report.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=letter,
    title="Github Audit Report", author="AJ Dehn", subject="Summarizes audit findings from Github")
    styles = getSampleStyleSheet()
    page_width, _ = LETTER
    elements = []

    # Styles
    label_style = ParagraphStyle(name="Label", fontSize=9, fontName="Helvetica-Bold")
    value_style = ParagraphStyle(name="Value", fontSize=9, fontName="Helvetica")
    list_style = ParagraphStyle(name="List", parent=value_style)
    center_style = ParagraphStyle(name="Center", parent=value_style, alignment=1)

    # ---------------------------
    # Header
    # ---------------------------
    elements.append(Paragraph("Github Audit Report", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(
        Paragraph(
            f"<b>Date:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            styles["Normal"]
        )
    )
    elements.append(Spacer(1, 12))

    # Summary Page
    elements.extend(render_summary_page(controls, styles))
    elements.append(PageBreak())

    # Detailed Findings
    for control in controls:
        elements.append(
            render_control_summary(
                control, page_width, label_style, value_style, list_style, center_style
            )
        )
        elements.append(Spacer(1, 16))

        sample_table = render_sample_table(
            control, page_width, label_style, value_style, center_style
        )

        if sample_table:
            elements.append(sample_table)
            elements.append(Spacer(1, 20))
        # Create new page for each control
        elements.append(PageBreak())

    doc.build(elements)
    print(f"Report generated: {filename}")


def parse_dt(dt_str):
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
