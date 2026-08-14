import os
import argparse


class CommandParser:
    def __init__(self):
        self.args = None

    def command_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-a", "--action", help="Choose an action", choices=['generate', 'test'],
                            default='generate')
        parser.add_argument("--minify", action='store_true', help="When used along with -v, write only vulnerability information, excludes methodology sections and other info")
        parser.add_argument("-p", "--pentest", help="Test uuid")
        parser.add_argument("-v", "--vuln", help="One or more vulnerability UUIDs", nargs="+")
        parser.add_argument("-e", "--environment", help="Secure24 environment choice", choices=['sec24fac', 'sec24prd'],
                            default='sec24prd')
        parser.add_argument("-l", "--loglevel", help="Choose loglevel", choices=['info', 'debug', 'error'],
                            default='info')
        parser.add_argument("--devoteam", action="store_true", default=False, help="Assign pentest to DevoTeam")


        parser.add_argument("-t", "--type",
                            help="Choose a number from 1, 2, or 3: 1 - Adversary Simulation, 2 - "
                                 "Black/Grey Box, 3 - White Box", type=int, choices=[1, 2, 3], default=2)
        parser.add_argument("-sd", "--start", help="Override Start Date: DD-MM-YYYY")
        parser.add_argument("-ed", "--end", help="Override End Date: DD-MM-YYYY")

        self.args = parser.parse_args()

    def validate_command(self):
        if not self.args.pentest and not self.args.vuln:
            raise ValueError("You must provide a Test UUID (-p) or at least one Vulnerability UUID (-v)")

        if not self.args.type:
            raise ValueError("Service must be provided")
