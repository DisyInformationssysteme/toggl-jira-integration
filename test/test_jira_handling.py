import unittest
import processTimeTrackingEntries
import os
import logging


class JiraTest(unittest.TestCase):

    configuration = {}
    _logger = logging.getLogger(__name__)

    def setUp(self):
        self.configuration = processTimeTrackingEntries.read_configuration(
            os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config_test.ini'))

    def test_issue_extraction(self):
        global configuration
        self.assertIsNone(processTimeTrackingEntries.extract_jira_issue_number("FooBar", self.configuration['issue_number_regex_expression']))
        self.assertEqual("JIRA-4711", processTimeTrackingEntries.extract_jira_issue_number("JIRA-4711 - FooBar", self.configuration['issue_number_regex_expression']))

    def test_issue_extraction_from_jira_response(self):
        project_list_response = [
            {
                'id': 37984387,
                'wid': 309109,
                'cid': 17545244,
                'name': 'JIRTEST-1234 - Project 1',
                'billable': False,
                'is_private': True,
                'active': True,
                'template': False,
                'at': '2017-04-24T06:08:59+00:00',
                'created_at': '2017-04-24T06:08:59+00:00',
                'color': '0',
                'auto_estimates': False,
                'actual_hours': 6,
                'hex_color': '#06aaf5'
            },
            {
                'id': 36319838,
                'wid': 309109,
                'cid': 19159353,
                'name': 'JIRTEST-1235 - Project 2',
                'billable': False,
                'is_private': True,
                'active': True,
                'template': False,
                'at': '2017-04-05T06:19:08+00:00',
                'created_at': '2017-04-05T06:16:05+00:00',
                'color': '0',
                'auto_estimates': False,
                'actual_hours': 1,
                'hex_color': '#06aaf5'
            },
            {
                'id': 36116304,
                'wid': 309109,
                'cid': 19159353,
                'name': 'JIRTEST-4567 - Project 3',
                'billable': False,
                'is_private': True,
                'active': True,
                'template': False,
                'at': '2017-04-03T06:29:29+00:00',
                'created_at': '2017-04-03T06:29:29+00:00',
                'color': '0',
                'auto_estimates': False,
                'actual_hours': 3,
                'hex_color': '#06aaf5'
            },
            {
                'id': 35679782,
                'wid': 309109,
                'cid': 16226102,
                'name': 'JIRTEST-7878 - Project 4',
                'billable': False,
                'is_private': True,
                'active': True,
                'template': False,
                'at': '2017-03-29T06:53:11+00:00',
                'created_at': '2017-03-29T06:53:11+00:00',
                'color': '0',
                'auto_estimates': False,
                'hex_color': '#06aaf5'
            },
            {
                'id': 35679419,
                'wid': 309109,
                'cid': 16226102,
                'name': 'Project without issue number',
                'billable': False,
                'is_private': True,
                'active': True,
                'template': False,
                'at': '2017-03-29T06:51:38+00:00',
                'created_at': '2017-03-29T06:51:38+00:00',
                'color': '0',
                'auto_estimates': False,
                'hex_color': '#06aaf5'
            }
        ]
        project_list = processTimeTrackingEntries.extract_jira_issue_numbers(project_list_response, self.configuration['issue_number_regex_expression'])
        self.assertEquals(len(project_list), 4)


def main():
    unittest.main()

if __name__ == '__main__':
    main()