import json
import logging
import os

SERVICE_TYPE_MAP = {
    1: "adversarySimulation",
    2: "blackBox",
    3: "whiteBox"
}


class ReportConfig:
    def __init__(self, parsed_args):
        self.service = parsed_args.type
        self.config = None
        self.configFile = "configuration/config.json"
        self.environmentName = parsed_args.environment
        self.environmentURL = None
        self.commonIssues = None
        self.report_config = None

    def load_all_configuration(self):
        self.load_configuration_file()
        self.load_url_from_env()
        self.load_report_template()
        self.load_vuln_report_template()
        self.load_vuln_due_date()

    def load_configuration_file(self):
        with open(self.configFile, 'r') as f:
            self.config = json.load(f)

        # Map numeric service type to string key
        if isinstance(self.service, int) and self.service in SERVICE_TYPE_MAP:
            self.service = SERVICE_TYPE_MAP[self.service]

        if self.service not in self.config["reportTypes"]:
            raise ValueError(f"Invalid service type: {self.service}")

        self.report_config = self.config["reportTypes"][self.service]

    def load_url_from_env(self):
        logging.info(f"Loading URL for environment {self.environmentName}")
        self.environmentURL = self.config["environmentURLs"][self.environmentName]

    def load_report_template(self):
        logging.info("Loading report templates")
        templates = self.report_config["ReportPentestTemplates"]
        self.report_template_file = templates["reportTemplateFile"]
        self.risk_table_template_file = templates["riskTableTemplateFile"]
        self.finding_table_template_file = templates["findingTableTemplateFile"]
        self.finding_due_table_template_file = templates["findingDueTableTemplateFile"]
        self.finding_template_file = templates["findingTemplateFile"]
        self.methodology_file = templates["methodologyFile"]
        self.appendix_file = templates["appendixFile"]
        self.report_output_folder = self.report_config["ReportOutputFolder"]

    def load_vuln_report_template(self):
        logging.info("Loading vulnerability report templates")
        templates = self.report_config["ReportVulnTemplates"]
        self.report_vuln_template_file = templates["reportVulnTemplateFile"]
        self.finding_vuln_template_file = templates["findingVulnTemplateFile"]

    def load_vuln_due_date(self):
        logging.info("Loading time to solve days")
        due = self.config["dueDates"]
        self.info_sla = due["info"]
        self.low_sla = due["low"]
        self.medium_sla = due["medium"]
        self.high_sla = due["high"]
        self.critical_sla = due["critical"]
