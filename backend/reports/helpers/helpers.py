import datetime
import unicodedata
import re


def sort_vuln_by_severity(vuln_issues):
    severity_order = ['Critical', 'High', 'Medium', 'Low', 'Info']

    sorted_vuln_issues = []
    for severity in severity_order:
        for index, vuln in vuln_issues.items():
            if vuln['Severity'] == severity:
                sorted_vuln_issues.append(vuln)

    return sorted_vuln_issues


def get_severity_as_html(severity):
    if severity == 'Info':
        return "<span id='info-f'>Info</span>"
    if severity == 'Low':
        return "<span id='low-f'>Low</span>"
    if severity == 'Medium':
        return "<span id='medium-f'>Medium</span>"
    if severity == 'High':
        return "<span id='high-f'>High</span>"
    if severity == 'Critical':
        return "<span id='critical-f'>Critical</span>"

    return severity


def html_status_resolved(status):
    if status == 'Resolved':
        return "<span id='status_resolved_text'>Resolved</span>"

    return status


def calculate_due_date(config, vuln_issue):
    severity = vuln_issue['Severity']
    days_to_add = 0

    if severity == 'Info':
        days_to_add = config.info_sla
    if severity == 'Low':
        days_to_add = config.low_sla
    if severity == 'Medium':
        days_to_add = config.medium_sla
    if severity == 'High':
        days_to_add = config.high_sla
    if severity == 'Critical':
        days_to_add = config.critical_sla

    try:
        due_date = datetime.datetime.strptime(vuln_issue['PublishedAt'], "%Y-%m-%d %H:%M:%S")
    except:
        print(f"[!] Vuln {vuln_issue['Name']} is not published yet. Using Today's date as publish date.")
    due_date = datetime.date.today()

    while days_to_add > 0:
        due_date += datetime.timedelta(days=1)
        days_to_add -= 1
    return due_date.strftime("%d-%m-%Y")


def slugify(value, allow_unicode=False):
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '_', value)
    return re.sub(r'[-\s]+', '-', value).strip('-_')
