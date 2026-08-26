import argparse
from reports.utils.log_levels import set_log_level
from reports.utils.config import ReportConfig
from reports.utils.api_handler import APIHandler, Secure24APIHandler
from reports.utils.builder import Builder
import logging
import os


def generate_html_report(args_dict):
    """
    Main function to generate the HTML report.
    Accepts a dictionary of arguments instead of parsing from the command line.
    """
    parsed_args = argparse.Namespace(**args_dict)

    if 'vuln' not in parsed_args: parsed_args.vuln = None
    if 'start' not in parsed_args: parsed_args.start = None
    if 'end' not in parsed_args: parsed_args.end = None
    if 'action' not in parsed_args: parsed_args.action = 'generate'
    if 'minify' not in parsed_args: parsed_args.minify = False
    if 'environment' not in parsed_args: parsed_args.environment = 'sec24prd'
    if 'loglevel' not in parsed_args: parsed_args.loglevel = 'info'
    if 'devoteam' not in parsed_args: parsed_args.devoteam = False
    if 'type' not in parsed_args: parsed_args.type = 2

    if not hasattr(parsed_args, 'pentest') and not hasattr(parsed_args, 'vuln'):
        raise ValueError("You must provide a 'pentest' (UUID) or at least one 'vuln' (UUID)")
    if not hasattr(parsed_args, 'type'):
        raise ValueError("'type' must be provided (1, 2, or 3)")

    set_log_level(parsed_args.loglevel)
    config = ReportConfig(parsed_args)
    config.load_all_configuration()

    if APIHandler.define_api(parsed_args) == "Secure24":
        data_collector = Secure24APIHandler(parsed_args, config)
        data_collector.api_key = parsed_args.api_key

        # --- FIX: Handle multiple vulnerabilities correctly by returning a list! ---
        if hasattr(parsed_args, 'vuln') and parsed_args.vuln:
            logging.info("Generating vulnerability report(s) for specific UUID(s)")
            all_vuln_uuids = []
            generated_reports = []

            for item in parsed_args.vuln:
                all_vuln_uuids.extend([uuid.strip() for uuid in item.split(',')])

            for vuln_uuid in all_vuln_uuids:
                if not vuln_uuid: continue
                logging.info(f"--- Preparing report for {vuln_uuid} ---")
                report_data = data_collector.prepare_single_vuln_report_data(vuln_uuid)
                if report_data:
                    report_builder = Builder(parsed_args, config, report_data)
                    final_content, final_path = report_builder.build_and_return_report_for_vuln()
                    generated_reports.append((final_content, os.path.basename(final_path)))
                else:
                    logging.warning(f"Skipping report generation for {vuln_uuid} due to missing data.")

            if not generated_reports:
                raise RuntimeError("Report generation failed, no content was produced.")
            return generated_reports

        # --- Standard Full Pentest Report ---
        elif hasattr(parsed_args, 'pentest') and parsed_args.pentest:
            logging.info("Generating full pentest report")
            return_data = data_collector.prepare_report_builder()
            report_builder = Builder(parsed_args, config, return_data)
            final_content, final_path = report_builder.build_and_return_full_report()

            if final_content and final_path:
                return final_content, os.path.basename(final_path)
            else:
                raise RuntimeError("Report generation failed, no content was produced.")

    elif APIHandler.define_api(parsed_args) == "ServiceNow":
        print("ServiceNow logic not implemented")