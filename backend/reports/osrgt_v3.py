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
    # 1. Create a Namespace object to simulate the parsed arguments
    # This allows us to use the dictionary from the JSON payload
    # The rest of the script can use 'parsed_args' as it did before.
    parsed_args = argparse.Namespace(**args_dict)

    # Set default values for any arguments not passed in the dictionary
    # to avoid errors. These match the defaults in the original command_parsed.py.
    if 'vuln' not in parsed_args: parsed_args.vuln = None
    if 'start' not in parsed_args: parsed_args.start = None
    if 'end' not in parsed_args: parsed_args.end = None
    if 'action' not in parsed_args: parsed_args.action = 'generate'
    if 'minify' not in parsed_args: parsed_args.minify = False
    if 'environment' not in parsed_args: parsed_args.environment = 'sec24prd'
    if 'loglevel' not in parsed_args: parsed_args.loglevel = 'info'
    if 'devoteam' not in parsed_args: parsed_args.devoteam = False
    if 'type' not in parsed_args: parsed_args.type = 2

    # 2. Validate required arguments
    if not hasattr(parsed_args, 'pentest') and not hasattr(parsed_args, 'vuln'):
        raise ValueError("You must provide a 'pentest' (UUID) or at least one 'vuln' (UUID)")
    if not hasattr(parsed_args, 'type'):
        raise ValueError("'type' must be provided (1, 2, or 3)")


    # 3. Your existing script logic, now using the 'parsed_args' object we created
    set_log_level(parsed_args.loglevel)
    config = ReportConfig(parsed_args)
    config.load_all_configuration()

    # This variable will store the final result to return to the Flask app
    final_report_path = None
    final_report_content = None

    if APIHandler.define_api(parsed_args) == "Secure24":
        data_collector = Secure24APIHandler(parsed_args, config)
        # The API key is now passed in the args_dict from main.py
        data_collector.api_key = parsed_args.api_key

        if hasattr(parsed_args, 'vuln') and parsed_args.vuln:
            logging.info("Generating vulnerability report(s) for specific UUID(s)")
            all_vuln_uuids = []
            for item in parsed_args.vuln:
                all_vuln_uuids.extend([uuid.strip() for uuid in item.split(',')])

            for vuln_uuid in all_vuln_uuids:
                if not vuln_uuid: continue
                logging.info(f"--- Preparing report for {vuln_uuid} ---")
                report_data = data_collector.prepare_single_vuln_report_data(vuln_uuid)
                if report_data:
                    report_builder = Builder(parsed_args, config, report_data)
                    # MODIFICATION: Instead of writing to a file, we get the content back
                    final_report_content, final_report_path = report_builder.build_and_return_report_for_vuln()
                else:
                    logging.warning(f"Skipping report generation for {vuln_uuid} due to missing data.")

        elif hasattr(parsed_args, 'pentest') and parsed_args.pentest:
            logging.info("Generating full pentest report")
            return_data = data_collector.prepare_report_builder()
            report_builder = Builder(parsed_args, config, return_data)
            # MODIFICATION: Instead of writing to a file, we get the content back
            final_report_content, final_report_path = report_builder.build_and_return_full_report()

    elif APIHandler.define_api(parsed_args) == "ServiceNow":
        print("ServiceNow logic not implemented")
        # Handle ServiceNow case if necessary

    if final_report_content and final_report_path:
        # We return the filename and its content to main.py
        # The filename is extracted from the full path
        filename = os.path.basename(final_report_path)
        return final_report_content, filename
    else:
        raise RuntimeError("Report generation failed, no content was produced.")
