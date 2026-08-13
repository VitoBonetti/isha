import datetime
import logging
import os
import re
from helpers.helpers import (
    sort_vuln_by_severity,
    get_severity_as_html,
    html_status_resolved,
    calculate_due_date,
    slugify, )


def check_template_file(template_file_path):
    if not os.path.exists(template_file_path):
        raise FileNotFoundError(f"{template_file_path} does not exist")


class ReportBuilder:
    def __init__(self, report_file_path):
        self.report_file_path = report_file_path
        self.template_content = None

    def load_template(self):
        self.template_content = open(self.report_file_path, 'r').read()

    def replace_in_template(self, place_holder, replacement_value):
        self.template_content = self.template_content.replace(place_holder, replacement_value)

    def replace_img_in_template_b64(self, uuid, attachment):
        pattern = rf'(?:https?://|/files/attachment/)[^\s"\']*{re.escape(uuid)}'
        self.template_content = re.sub(pattern, attachment, self.template_content)

    def get_template_content(self):
        return self.template_content


class Builder:
    def __init__(self, parsed_args, config, data):
        self.vuln_issue = ""
        self.pentest_issue = ""
        self.performed_by_devoteam = ""
        self.parsed_args = parsed_args # Store for later use

        if parsed_args.devoteam:
            self.performed_by_devoteam = "      <p><b>Performed By:</b><br>Devo Team</p>"

        # 1. Assign data common to all report types
        self.pentest_issue = data['pentestInformation']

        # 2. Determine which report to build and set the correct templates
        if parsed_args.vuln:
            # This is a specific vulnerability report.
            self.vuln_issues = data['vulnerabilities']

            # Set self.vuln_issue only if there is exactly one vulnerability.
            if len(self.vuln_issues) == 1:
                self.vuln_issue = list(self.vuln_issues.values())[0]
            else:
                self.vuln_issue = None  # It's a multi-vulnerability report

            # Always use the vulnerability-specific templates when -v is present.
            self.report_template_file = config.report_vuln_template_file
            self.finding_template_file = config.finding_vuln_template_file
        else:
            # This is a full pentest report.
            self.vuln_issues = data['vulnerabilities']
            self.report_template_file = config.report_template_file
            self.finding_template_file = config.finding_template_file

        # 3. Handle the --minify flag by overriding the template selection if necessary.
        if parsed_args.minify:
            self.report_template_file = "Templates/Generic/TemplateReportMinify.html"
            self.finding_template_file = config.finding_vuln_template_file

        # 4. Load all other required templates and settings
        self.risk_table_template_file = config.risk_table_template_file
        self.finding_table_template_file = config.finding_table_template_file
        self.finding_due_table_template_file = config.finding_due_table_template_file
        self.methodology_file = config.methodology_file
        self.appendix_file = config.appendix_file

        # 5. Load SLA configuration
        self.info_sla = config.info_sla
        self.low_sla = config.low_sla
        self.medium_sla = config.medium_sla
        self.high_sla = config.high_sla
        self.critical_sla = config.critical_sla

        self.report_output_folder = config.report_output_folder
        self.report_template = ReportBuilder(self.report_template_file)

    def build_and_return_full_report(self):
        """
        Builds a full pentest report and returns its content and filename.
        """
        # 1. Run all the steps to build the report in memory.
        self.check_templates_and_output_folder()
        self.load_main_template()
        self.fill_report_with_pentest_issues()
        self.sort_vuln_by_severity()
        self.add_findings_to_report_template()
        self.add_risk_table_report_template()
        self.add_findings_table_report_template()
        self.add_methodology_template()
        self.add_findings_due_table_report_template()
        self.add_appendix()

        # 2. Get the final HTML content from the ReportBuilder instance.
        report_content = self.report_template.get_template_content()

        # 3. Generate the correct output filename.
        report_path = self.get_report_output_location()

        # 4. Return the content and the calculated path.
        return report_content, report_path

    def build_and_return_report_for_vuln(self):
        """
        Builds a single vulnerability report and returns its content and filename.
        """
        # 1. Run all the steps to build the report in memory.
        self.check_templates_and_output_folder()
        self.load_main_template()
        self.fill_report_with_pentest_issues()
        self.fill_report_template_with_vuln_issue()
        self.add_findings_to_report_template()

        # 2. Get the final HTML content from the ReportBuilder instance.
        report_content = self.report_template.get_template_content()

        # 3. Generate the correct output filename.
        report_path = self.get_report_output_location()

        # 4. Return the content and the calculated path.
        return report_content, report_path

    def check_templates_and_output_folder(self, *args, **kwargs):
        logging.info("Checking existence of template files and output folder")
        if self.vuln_issue:
            check_template_file(self.report_template_file)
            check_template_file(self.finding_template_file)
        elif self.pentest_issue:
            check_template_file(self.report_template_file)
            check_template_file(self.risk_table_template_file)
            check_template_file(self.finding_table_template_file)
            check_template_file(self.finding_due_table_template_file)
            check_template_file(self.finding_template_file)
        else:
            raise Exception("Generation type and template not found")

        if not os.path.exists(self.report_output_folder):
            raise NotADirectoryError(f"{self.report_output_folder} does not exist")

    def load_main_template(self):
        logging.info("Loading main template")
        self.report_template.load_template()

    def fill_report_with_pentest_issues(self):
        logging.info("Filling report template with pentest issue")
        self.report_template.replace_in_template('../Static/CSS/', 'Reports/Static/CSS/')
        self.report_template.replace_in_template('../Static/Images/', 'Reports/Static/Images/')
        pentest_data = self.pentest_issue
        self.report_template.replace_in_template("{YEAR}", pentest_data['Year'])
        self.report_template.replace_in_template("{APPLICATION_NAME}", pentest_data['Scope'])
        self.report_template.replace_in_template("{STATUS}", pentest_data['Status'])
        self.report_template.replace_in_template("{LAST_MODIFIED}", pentest_data['LastModified'])
        self.report_template.replace_in_template("{REFERENCE}", pentest_data['Name'])
        self.report_template.replace_in_template("{AUTHORS}", pentest_data['Authors'])
        self.report_template.replace_in_template("{START_DATE}", pentest_data['Start'])
        self.report_template.replace_in_template("{END_DATE}", pentest_data['End'])
        self.report_template.replace_in_template("{SERVICE_TYPE}", pentest_data['ServiceType'])
        self.report_template.replace_in_template("{SERVICE_LEAD}", pentest_data['ServiceLead'])
        self.report_template.replace_in_template("{PERFORMED_BY}", self.performed_by_devoteam)

        self.report_template.replace_in_template("{MANAGEMENT_SUMMARY}", pentest_data['ManagementSummary'])
        self.report_template.replace_in_template("{SCOPE_DESCRIPTION}", pentest_data['Scope'])
        self.report_template.replace_in_template("{DURATION}", pentest_data['Duration'])
        self.report_template.replace_in_template("{REQUEST_ID}", pentest_data['RequestID'])

        if "Randstad" in pentest_data['Opco']:
            self.report_template.replace_in_template("{OPCO}", pentest_data['Opco'])
        else:
            self.report_template.replace_in_template("{OPCO}", "Randstad " + pentest_data['Opco'])

    def sort_vuln_by_severity(self):
        logging.info("Sorting vuln issues by severity")
        self.vuln_issues = sort_vuln_by_severity(self.vuln_issues)

    def add_findings_to_report_template(self):
        logging.info("Adding findings to report template")
        filled_all_findings_template = ""

        for filled_finding in self.yield_filled_findings_template():
            filled_all_findings_template += filled_finding

        if not filled_all_findings_template:
            filled_all_findings_template = "No new vulnerabilities were found during the engagement."

        self.report_template.replace_in_template('{FINDINGS}', filled_all_findings_template)

    def yield_filled_findings_template(self):
        logging.info("Yielding findings as filled templates")

        # This handles both lists (full report) and dictionaries (single report)
        vulnerabilities = self.vuln_issues.values() if isinstance(self.vuln_issues, dict) else self.vuln_issues

        for finding_index, vuln in enumerate(vulnerabilities):
            current_finding_number = finding_index + 1

            if hasattr(self, "vuln_issues"):
                chapter = 4
                if "minify" in self.report_template_file.lower():
                    chapter = 1
            else:
                chapter = 3

            finding_template_builder = ReportBuilder(self.finding_template_file)
            finding_template_builder.load_template()
            finding_template_builder.replace_in_template('{FINDING_NUM}',
                                                         str("%d.%s" % (chapter, current_finding_number)))
            finding_template_builder.replace_in_template('{FINDING_SUBNUM1}',
                                                         str("%d.%s.1" % (chapter, current_finding_number)))
            finding_template_builder.replace_in_template('{FINDING_SEVERITY}', get_severity_as_html(vuln['Severity']))
            finding_template_builder.replace_in_template('{FINDING_COMPONENT}', vuln['Asset'])
            finding_template_builder.replace_in_template('{FINDING_TEAM}', "COMING SOON")
            finding_template_builder.replace_in_template('{FINDING_STATUS}', html_status_resolved(vuln['Status']))
            finding_template_builder.replace_in_template('{FINDING_REF}', vuln['Name'])
            finding_template_builder.replace_in_template('{FINDING_TITLE}', vuln['Title'])
            finding_template_builder.replace_in_template('{FINDING_DESCRIPTION}', vuln['Finding'])

            try:
                finding_template_builder.replace_in_template('{FINDING_DUE}', calculate_due_date(self, vuln))
            except UnboundLocalError as error:
                logging.info(f"Couldn't calculate date for '{vuln['Title']}' with severity '{vuln['Severity']}'. "
                             f"Due date set to -")

            if vuln['Attachments']:
                for uuid, attachment in vuln['Attachments'].items():
                    finding_template_builder.replace_img_in_template_b64(uuid, attachment)

            yield finding_template_builder.get_template_content()

    def add_risk_table_report_template(self):
        def severity_counter_output(s_counter):
            if s_counter == 0:
                s_counter = "No Findings"
            elif s_counter == 1:
                s_counter = "1 Finding"
            else:
                s_counter = f"{str(s_counter)} Findings"

            return s_counter

        logging.info("Adding risks  table to report template")

        risk_table = ""
        c_counter = h_counter = m_counter = l_counter = i_counter = 0
        for vuln in self.vuln_issues:
            if vuln['Severity'] == "Critical":
                c_counter = c_counter + 1
            if vuln['Severity'] == "High":
                h_counter = h_counter + 1
            if vuln['Severity'] == "Medium":
                m_counter = m_counter + 1
            if vuln['Severity'] == "Low":
                l_counter = l_counter + 1
            if vuln['Severity'] == "Info":
                i_counter = i_counter + 1

        c_counter = severity_counter_output(c_counter)
        h_counter = severity_counter_output(h_counter)
        m_counter = severity_counter_output(m_counter)
        l_counter = severity_counter_output(l_counter)
        i_counter = severity_counter_output(i_counter)

        risk_table_template_builder = ReportBuilder(self.risk_table_template_file)
        risk_table_template_builder.load_template()
        risk_table_template_builder.replace_in_template('{RISKSUMMARY_CRITICAL}', c_counter)
        risk_table_template_builder.replace_in_template('{RISKSUMMARY_HIGH}', h_counter)
        risk_table_template_builder.replace_in_template('{RISKSUMMARY_MEDIUM}', m_counter)
        risk_table_template_builder.replace_in_template('{RISKSUMMARY_LOW}', l_counter)
        risk_table_template_builder.replace_in_template('{RISKSUMMARY_INFO}', i_counter)

        risk_table += risk_table_template_builder.get_template_content()

        self.report_template.replace_in_template('{RISKS_SUMMARY}', risk_table)

    def add_findings_table_report_template(self):
        logging.info("Adding findings table to report template")
        findings_table = ""
        for vuln in self.vuln_issues:
            findings_table_template_builder = ReportBuilder(self.finding_table_template_file)
            findings_table_template_builder.load_template()
            findings_table_template_builder.replace_in_template('{FINDINGSUMMARY_TITLE}', vuln["Title"])
            findings_table_template_builder.replace_in_template('{FINDINGSUMMARY_SEVERITY}',
                                                                get_severity_as_html(vuln['Severity']))
            findings_table_template_builder.replace_in_template('{FINDINGSUMMARY_STATUS}',
                                                                html_status_resolved(vuln['Status']))
            try:
                findings_table_template_builder.replace_in_template('{FINDINGSUMMARY_DUE}',
                                                                    calculate_due_date(self, vuln))
            except UnboundLocalError as error:
                logging.info(f"Couldn't calculate date for '{vuln['Title']}' with severity '{vuln['Severity']}'. Due date set to -")
                findings_table_template_builder.replace_in_template('{FINDINGSUMMARY_DUE}', "-")

            findings_table += findings_table_template_builder.get_template_content()

        if not findings_table:
            findings_table_template_builder = ReportBuilder(self.finding_table_template_file)
            findings_table_template_builder.load_template()
            findings_table_template_builder.replace_in_template('{FINDINGSUMMARY_TITLE}', "No findings")
            findings_table_template_builder.replace_in_template('{FINDINGSUMMARY_SEVERITY}', "-")
            findings_table_template_builder.replace_in_template('{FINDINGSUMMARY_STATUS}', "-")
            findings_table_template_builder.replace_in_template('{FINDINGSUMMARY_DUE}', "-")
            findings_table = findings_table_template_builder.get_template_content()

        self.report_template.replace_in_template('{FINDINGS_SUMMARY}', findings_table)

    def add_methodology_template(self):
        logging.info("Adding methodology description report template")

        method_description = ""
        method_description_template_builder = ReportBuilder(self.methodology_file)
        method_description_template_builder.load_template()

        method_description += method_description_template_builder.get_template_content()

        self.report_template.replace_in_template('{METHODOLOGY}', method_description)

    def add_appendix(self):
        logging.info("Adding appendix to the report template")

        appendix_description = ""
        appendix_description_template_builder = ReportBuilder(self.appendix_file)
        appendix_description_template_builder.load_template()

        appendix_description += appendix_description_template_builder.get_template_content()

        self.report_template.replace_in_template('{APPENDIX}', appendix_description)

    def add_findings_due_table_report_template(self):
        logging.info("Adding findings due table to report template")

        findings_due_table = ""
        for vuln in self.vuln_issues:
            findings_due_table_template_builder = ReportBuilder(self.finding_due_table_template_file)
            findings_due_table_template_builder.load_template()
            findings_due_table_template_builder.replace_in_template('{FINDINGSUMMARY_TITLE}', vuln["Title"])
            findings_due_table_template_builder.replace_in_template('{FINDINGSUMMARY_SEVERITY}',
                                                                    get_severity_as_html(vuln['Severity']))
            try:
                findings_due_table_template_builder.replace_in_template('{FINDINGSUMMARY_DUE}',
                                                                        calculate_due_date(self, vuln))
            except UnboundLocalError as error:
                logging.info(f"Couldn't calculate date for '{vuln['Title']}' with severity '{vuln['Severity']}'"
                             f". Due date set to -")
                findings_due_table_template_builder.replace_in_template('{FINDINGSUMMARY_DUE}', "-")

            findings_due_table += findings_due_table_template_builder.get_template_content()

        if not findings_due_table:
            findings_due_table_template_builder = ReportBuilder(self.finding_due_table_template_file)
            findings_due_table_template_builder.load_template()
            findings_due_table_template_builder.replace_in_template('{FINDINGSUMMARY_TITLE}', "No findings")
            findings_due_table_template_builder.replace_in_template('{FINDINGSUMMARY_SEVERITY}', "-")
            findings_due_table_template_builder.replace_in_template('{FINDINGSUMMARY_DUE}', "-")

            findings_due_table += findings_due_table_template_builder.get_template_content()

        self.report_template.replace_in_template('{FINDINGS_DUE_SUMMARY}', findings_due_table)

    def get_report_vuln_output_location(self):
        report_name = f"{self.vuln_issue['Name']}-{self.vuln_issue['Title']}"
        report_status = self.vuln_issue['Status']

        now = datetime.datetime.now()
        output_file_name = f"{report_name}-{report_status}-{now.strftime('%Y-%m')}"
        output_file_name = f"{slugify(output_file_name)}.html"
        report_output_location = os.path.join(self.report_output_folder, output_file_name)

        return report_output_location

    def get_report_output_location(self):
        now = datetime.datetime.now()

        # Case 1: Report for a single, specific vulnerability
        if self.parsed_args.vuln and len(self.vuln_issues) == 1:
            # FIX: Access the first item of the list directly
            vuln = self.vuln_issues[0]
            report_name = f"{vuln['Name']}-{vuln['Title']}"
            report_status = vuln['Status']
            output_file_name = f"{report_name}-{report_status}-{now.strftime('%Y-%m')}"
        # Case 2: Full pentest report or a report for multiple vulnerabilities
        else:
            app_name = self.pentest_issue.get('Scope', None)
            report_name = self.pentest_issue['Name']
            report_status = app_name or self.pentest_issue['Status']

            suffix = ""
            if self.parsed_args.vuln:  # Add a suffix for multi-vuln reports
                suffix = "-vulnerability-report"

            output_file_name = f"{report_name}-{report_status}{suffix}-{now.strftime('%Y-%m')}"

        output_file_name = f"{slugify(output_file_name)}.html"
        return os.path.join(self.report_output_folder, output_file_name)

    def write_report_to_output_folder(self):
        report_output_location = self.get_report_output_location()
        logging.info(f"Writing report to output folder: {report_output_location}")

        template_content = self.report_template.get_template_content()

        with open(report_output_location, 'w', encoding='utf-8') as report_output_file:
            report_output_file.write(template_content)

    def fill_report_template_with_vuln_issue(self):
        logging.info("Filling report template with vulnerability-specific issue details")

        vuln_data = self.vuln_issue
        # FIX: Only replace vulnerability-specific placeholders
        self.report_template.replace_in_template("{VULN_NAME}", vuln_data['Title'])

