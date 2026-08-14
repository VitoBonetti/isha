from dotenv import load_dotenv
from getpass import getpass
import os
import logging
import datetime
import requests
import html2text
import base64
import re
import json
from utils.secret_manager import get_secret


try:
    import imghdr
    def detect_image_type(data):
        return imghdr.what(None, h=data)
except ModuleNotFoundError:
    from PIL import Image
    from io import BytesIO

    def detect_image_type(data):
        try:
            with Image.open(BytesIO(data)) as img:
                return img.format.lower()
        except Exception:
            return None



class APIHandler:
    def __init__(self, parsed_args):
        self.environment = parsed_args.environment

    def define_api(self):
        if self.environment.lower()[0:3] == 'sec':
            return "Secure24"
        elif self.environment.lower()[0:3] == 'sno':
            return "ServiceNow"
        else:
            raise TypeError()


class Secure24APIHandler:
    def __init__(self, parsed_args, config):
        self.api_key = get_secret(os.environ.get("KISS_24_API_KEY_NAME"))
        self.api_url = str(os.environ.get("KISS_24_ENDPOINT"))
        self.web_url = config.environmentURL
        self.parsed_args = parsed_args
        self.config = config
        self.api_interface = None

    def prepare_single_vuln_report_data(self, vuln_uuid):
        """
        Prepares all necessary data for building a report for a single vulnerability.
        """
        vuln_data = self.getVulnFromUuid([vuln_uuid])
        if not vuln_data:
            logging.error(f"Could not retrieve data for vulnerability UUID: {vuln_uuid}")
            return None

        test_uuid = vuln_data[0]['test']['uuid']
        test_data_list = self.get_test_information(test_uuid)
        if not test_data_list:
            logging.error(f"Could not retrieve parent test data for vulnerability UUID: {vuln_uuid}")
            return None

        test_data = test_data_list[0]

        return self.report_prelogic(test_data, vuln_data)

    def prepare_report_builder(self):
        now = datetime.datetime.now()
        test_data_list = self.get_test_information(self.parsed_args.pentest)

        if not test_data_list:
            raise Exception("No test data returned for this UUID")

        test_data = test_data_list[0]
        vulns_data = self.get_vulns_from_test(self.parsed_args.pentest)

        if self.parsed_args.start:
            test_data['started_at'] = self.parsed_args.start
        else:
            test_data['started_at'] = (datetime.datetime.fromisoformat(test_data['started_at']).
                                       astimezone(datetime.timezone.utc).strftime('%d-%m-%Y'))

        if self.parsed_args.end:
            test_data['ended_at'] = self.parsed_args.end
        else:
            if not test_data['ended_at']:
                test_data['ended_at'] = datetime.datetime.today().strftime('%d-%m-%Y')
            else:
                test_data['ended_at'] = (datetime.datetime.fromisoformat(test_data['ended_at']).
                                         astimezone(datetime.timezone.utc).strftime('%d-%m-%Y'))

        test_start = datetime.datetime.strptime(test_data['started_at'], "%d-%m-%Y")
        test_end = datetime.datetime.strptime(test_data['ended_at'], "%d-%m-%Y")

        # initializing business days count
        test_duration = 0

        # looping through each day in the date range
        current_date = test_start
        while current_date <= test_end:
            # checking if the current day is a weekday
            if current_date.weekday() < 5:
                test_duration += 1
            # incrementing the current day by one day
            current_date += datetime.timedelta(days=1)

        # Setting Service Type
        if self.parsed_args.type == 1:
            test_data['service_type'] = "Adversary Simulation"
            test_data['service_lead'] = "Iuri Picolini Moro"
        if self.parsed_args.type == 2:
            test_data['service_type'] = "Black/Grey Box"
            test_data['service_lead'] = "Timothy Tjen A Looi"
        if self.parsed_args.type == 3:
            test_data['service_type'] = "White Box"
            test_data['service_lead'] = "Timothy Tjen A Looi"

        ## Mapping KISS24 values to Randstad pentest naming
        test_data['state'] = 'Final' if (test_data['state'] == 'Tested') else 'Concept'

        # to remove html tags
        config = html2text.HTML2Text()
        config.body_width = 0  # disable line wrapping
        _txt = config.handle(test_data['details'])

        # Getting SNow request ID
        service_now_request_id = re.search(r"ServiceNow Request ID: ([^\s\t\n\r]+)", _txt)
        if service_now_request_id:
            service_now_request_id = service_now_request_id.group(1)
        else:
            service_now_request_id = "N/A"
            print("[!] ServiceNow Request ID not found.")

        # Extract content after "[MANAGEMENT SUMMARY]" using regex
        management_summary_content = re.search(r'[\[{]MANAGEMENT SUMMARY[\]}].*?[\s\t\r\n]+(.*)', _txt,
                                               re.DOTALL | re.I)

        # Check if the regex match was successful
        if management_summary_content:
            management_summary_content = management_summary_content.group(1)
        else:
            management_summary_content = "To Do"
            print("[!] Management summary content not found.")

        assets_list = self.get_assets_from_test(self.parsed_args.pentest)
        scope_name = assets_list[0]['name'] if assets_list else "N/A"
        returned_array = {
            "pentestInformation": {
                "Name": test_data['id'],
                "Status": test_data['state'],
                "Year": str(now.year),
                "Start": test_data['started_at'],
                "End": test_data['ended_at'],
                "Authors": "Global Offensive Security Team",
                "ServiceType": test_data['service_type'],
                "ServiceLead": test_data['service_lead'],
                "ManagementSummary": management_summary_content,
                "Scope": scope_name,
                "LastModified": now.strftime("%Y-%m-%d"),
                "Opco": test_data['organisation']['name'],
                "Duration": "{} {}".format(test_duration, 'days' if test_duration > 1 else 'day'),
                "RequestID": service_now_request_id
            },
            "vulnerabilities": {}
        }

        for index, vuln_item in enumerate(vulns_data):
            vuln_enrichment = vuln_item

            import json
            logging.debug("Attachment block: %s", json.dumps(vuln_enrichment.get('attachments', {}), indent=2))

            if vuln_enrichment.get('attachments'):
                attachment_metadata = vuln_enrichment['attachments']
                attachment_enrichment = self.get_b64_attachment(attachment_metadata)
            else:
                attachment_enrichment = []

            # Extract Remediation Effort from memory
            vuln_uuid = vuln_item['uuid']
            custom_fields = getattr(self.parsed_args, 'custom_fields', {})
            fields_for_this_vuln = custom_fields.get(vuln_uuid, [])

            remediation_effort = "N/A"
            for field in fields_for_this_vuln:
                if field.get('custom_field', {}).get('name') == 'Remediation Effort':
                    val = field.get('value')
                    if val:
                        # Handle both strings and arrays correctly
                        remediation_effort = val if isinstance(val, str) else ", ".join(val)
                    break

            ## Mapping KISS24 values to Randstad vuln naming
            vuln_enrichment['state'] = 'Open' if (vuln_item['state'] == 'New') else vuln_item['state']

            ## Cleaning up styles from KITS24 details
            vuln_enrichment['details'] = re.sub('<span style=".*?">', '', vuln_enrichment['details'])
            vuln_enrichment['details'] = re.sub('</span>', '', vuln_enrichment['details'])

            returned_array['vulnerabilities'][index] = {
                "Name": vuln_item['id'],
                "UUID": vuln_item['uuid'],
                "Year": str(now.year),
                "Status": vuln_enrichment['state'],
                "Severity": vuln_enrichment['severity'],
                "Asset": (
                    vuln_enrichment['assets'][0]['name']
                    if 'assets' in vuln_enrichment and isinstance(vuln_enrichment['assets'], list) and vuln_enrichment['assets']
                    else "N/A"
                ),
                "Title": vuln_enrichment['description'],
                "Type": vuln_enrichment['vulnerability_type'],
                "Finding": vuln_enrichment['details'],
                "PublishedAt": vuln_enrichment['published_at'],
                "RemediationEffort": remediation_effort,
                "Impact": "",
                "Recommendation": "",
                "Attachments": attachment_enrichment,
                "LastModified": now.strftime("%Y-%m-%d")
            }
        return returned_array


    def report_prelogic(self, testData, vulnData):
        now = datetime.datetime.now()

        if self.parsed_args.start:
            testData['started_at'] = self.parsed_args.start
        else:
            testData['started_at'] = datetime.datetime.fromisoformat(testData['started_at']).astimezone(datetime.timezone.utc).strftime("%d-%m-%Y")

        if self.parsed_args.end:
            testData['ended_at'] = self.parsed_args.end
        else:
            if not testData['ended_at']:
                testData['ended_at'] = datetime.datetime.today().strftime("%d-%m-%Y")
            else:
                testData['ended_at'] = datetime.datetime.fromisoformat(testData['ended_at']).astimezone(datetime.timezone.utc).strftime("%d-%m-%Y")

        test_start = datetime.datetime.strptime(testData['started_at'], "%d-%m-%Y")
        test_end = datetime.datetime.strptime(testData['ended_at'], "%d-%m-%Y")

        # initializing business days count
        test_duration = 0

        # looping through each day in the date range
        current_date = test_start
        while current_date <= test_end:
            # checking if the current day is a weekday
            if current_date.weekday() < 5:
                test_duration += 1
            # incrementing the current day by one day
            current_date += datetime.timedelta(days=1)

        # Setting Service Type
        if self.parsed_args.type == 1:
            testData['service_type'] = "Adversary Simulation"
            testData['service_lead'] = "Iuri Piccoli Moro"
        if self.parsed_args.type == 2:
            testData['service_type'] = "Black/Grey Box"
            testData['service_lead'] = "Timothy Tjen A Looi"
        if self.parsed_args.type == 3:
            testData['service_type'] = "White Box"
            testData['service_lead'] = "Timothy Tjen A Looi"
        ## Mapping KISS24 values to Randstad pentest naming
        testData['state'] = 'Final' if (testData['state'] == 'Tested') else 'Concept'

        # Getting SNow request ID
        service_now_request_id = re.search(r"ServiceNow Request ID: ([^\s]+)", testData['details'])
        if service_now_request_id:
            service_now_request_id = service_now_request_id.group(1)
        else:
            service_now_request_id = "N/A"
            print("[!] ServiceNow Request ID not found.")

        # Extract content after "[MANAGEMENT SUMMARY]" using regex
        management_summary_content = re.search(r'\[MANAGEMENT SUMMARY\]\s+(.*)', testData['details'], re.DOTALL)

        # Check if the regex match was successful
        if management_summary_content:
            management_summary_content = management_summary_content.group(1)
        else:
            management_summary_content = "To Do"
            print("[!] Management summary content not found.")

        scope_name =  "N/A"

        if vulnData:
            scope_name = self.get_asset_from_vuln(vulnData[0]['uuid'])

        returnArray = {
            "pentestInformation":{
                "Name":testData['id'],
                "Status":testData['state'],
                "Year":str(now.year),
                "Start":testData['started_at'],
                "End":testData['ended_at'],
                "Authors":"Global Offensive Security Team",
                "ServiceType":testData['service_type'],
                "ServiceLead":testData['service_lead'],
                "ManagementSummary":management_summary_content,
                "Scope":scope_name,
                "LastModified": now.strftime("%Y-%m-%d"),
                "Opco":testData['organisation']['name'],
                "Duration": "{} {}".format(test_duration, 'days' if test_duration > 1 else 'day'),
                "RequestID":service_now_request_id
                },
            "vulnerabilities":{}
        }

        for index, vuln_item in enumerate(vulnData):
            vuln_enrichment = vuln_item

            import json
            logging.debug("Attachment block: %s", json.dumps(vuln_enrichment.get('attachments', {}), indent=2))

            if vuln_enrichment.get('attachments'):
                attachment_metadata = vuln_enrichment['attachments']
                attachment_enrichment = self.get_b64_attachment(attachment_metadata)
            else:
                attachment_enrichment = []

            # Extract Remediation Effort from memory
            vuln_uuid = vuln_item['uuid']
            custom_fields = getattr(self.parsed_args, 'custom_fields', {})
            fields_for_this_vuln = custom_fields.get(vuln_uuid, [])

            remediation_effort = "N/A"
            for field in fields_for_this_vuln:
                if field.get('custom_field', {}).get('name') == 'Remediation Effort':
                    val = field.get('value')
                    if val:
                        # Handle both strings and arrays correctly
                        remediation_effort = val if isinstance(val, str) else ", ".join(val)
                    break

            ## Mapping KISS24 values to Randstad vuln naming
            vuln_enrichment['state'] = 'Open' if (vuln_item['state'] == 'New') else vuln_item['state']

            ## Cleaning up styles from KITS24 details
            vuln_enrichment['details'] = re.sub('<span style=".*?">', '', vuln_enrichment['details'])
            vuln_enrichment['details'] = re.sub('</span>', '', vuln_enrichment['details'])

            asset_name = scope_name

            print(asset_name)

            returnArray['vulnerabilities'][index] = {
                "Name": vuln_item['id'],
                "UUID": vuln_item['uuid'],
                "Year": str(now.year),
                "Status": vuln_enrichment['state'],
                "Severity": vuln_enrichment['severity'],
                "Asset": asset_name,
                "Title": vuln_enrichment['description'],
                "Type": vuln_enrichment['vulnerability_type'],
                "Finding": vuln_enrichment['details'],
                "PublishedAt": vuln_enrichment['published_at'],
                "RemediationEffort": remediation_effort,
                "Impact": "",
                "Recommendation": "",
                "Attachments": attachment_enrichment,
                "LastModified": now.strftime("%Y-%m-%d")
            }
        return returnArray

    def get_assets_from_test(self, pentest_uuid):
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }
        body = {"tests": [pentest_uuid]}
        url = f"{self.api_url}assets"
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        return resp.json().get("items", [])

    def get_asset_from_vuln(self, vuln_uuid):
        """
        Fetches the asset information for a given vulnerability UUID.
        """
        logging.debug(f"Getting asset from API for vuln UUID: {vuln_uuid}")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }
        body = {"vulnerabilities": [vuln_uuid]}
        url = f"{self.api_url}assets"
        try:
            response = requests.post(url, headers=headers, json=body, timeout=30)
            if response.status_code == 200:
                assets = response.json().get("items", [])
                if assets:
                    return assets[0].get('name', "N/A")
            return "N/A"
        except requests.RequestException as e:
            logging.error(f"HTTP error occurred while fetching asset: {e}")
            return "N/A"

    def get_test_information(self, pentest):
        logging.debug("Getting test information from API")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }
        body = {"uuid": [pentest]}
        url = f"{self.api_url}tests"
        try:
            response = requests.post(url, headers=headers, json=body, timeout=30)
            if response.status_code == 200:
                return response.json().get("items", [])
            else:
                raise Exception("Cannot get test info from API")
        except requests.RequestException as e:
            raise Exception(f"HTTP error occurred: {e}")

    def get_vulns_from_test(self, pentest):
        logging.debug("Getting test information from WEB")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }
        body = {"tests": [self.parsed_args.pentest]}
        url = f"{self.api_url}vulnerabilities"

        try:
            response = requests.post(url, headers=headers, json=body, timeout=30)
            if response.status_code == 200:
                return response.json().get("items", [])
            else:
                raise Exception("Cannot get test info from API")
        except requests.RequestException as e:
            raise Exception(f"HTTP error occurred: {e}")

    def get_attachments(self, vuln_uuid):
        logging.debug(f"Getting attachment from API with the following UUID: {vuln_uuid}")
        headers = {
            "x-api-key": self.api_key
        }
        url = f"{self.api_url}attachments/{vuln_uuid}"
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.content
            else:
                logging.debug(f"Failed to fetch attachment {vuln_uuid}: {response.status_code}")
                return None
        except Exception as ex:
            logging.error(f"Exception raised: {ex}")
            return None

    def get_b64_attachment(self, attachment_metadata):
        b64_encoded_content = {}

        list_url = f"{self.api_url}attachments"

        try:
            response = requests.post(
                list_url,
                headers={"x-api-key": self.api_key},
                json=attachment_metadata["body"],
                timeout=30
            )
            if response.status_code != 200:
                logging.warning(f"Failed to fetch attachment list: {response.status_code}")
                return {}

            attachment_items = response.json().get("items", [])
            for attachment in attachment_items:
                logging.debug(f"Attachment raw item: {json.dumps(attachment, indent=2)}")
                attachment_uuid = attachment.get("uuid")
                print(attachment_uuid)
                if not attachment_uuid:
                    logging.warning("Attachment item missing UUID field")
                    continue

                binary_data = self.get_attachments(attachment_uuid)
                if binary_data:
                    image_type = detect_image_type(binary_data)
                    mime_type = f"image/{image_type or 'png'}"
                    b64 = base64.b64encode(binary_data).decode("utf-8")
                    b64_encoded_content[attachment_uuid] = f"data:{mime_type};base64,{b64}"

        except Exception as e:
            logging.error(f"[EXCEPTION FETCHING ATTACHMENTS LIST]: {e}")

        return b64_encoded_content

    def getVulnFromUuid(self, uuid_list):
        """
        Author: Andre Marques
        Developed at: 2024-06-06
        Retrieves vuln information by UUID

        No test UUID or parameter is needed. This is to be used
        whenever generating single vuln or multiple selections of
        vulnerabilities that belong to a test (or different tests)
        and generate a single report.
        """
        logging.info("Getting issues from a list of vulnerability UUIDs")
        aggregated = list()
        uuids = uuid_list
        headers = {
            "x-api-key": self.api_key
        }
        url = f"{self.api_url}vulnerabilities"
        for u in uuids:
            try:
                data = {"uuid": [u]}
                response = requests.post(url, headers=headers, json=data, timeout=30)
                if response.status_code == 200:
                    aggregated.extend(response.json().get("items", []))
                else:
                    logging.debug(f"Failed to fetch vuln information from API: {response.status_code}")
            except Exception:
                raise
        return aggregated  # Return aggregated collection of lists for each API request