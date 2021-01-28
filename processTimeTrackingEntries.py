# -*- coding: utf-8 -*-

# processTimeTrackingEntries.py - reads time tracking entries from the Toggl (https://www.toggl.com) REST-API and
# adds the time tracking entries as work logs to JIRA issues.
# Copyright 2018 Carsten Heidmann (carsten.heidmann@disy.net)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
# to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import json
import datetime
import dateutil.parser
import logging
import re
import math
import configparser
import getopt
import sys

from togglwrapper import Toggl
from jira import Worklog
from jira import JIRA, JIRAError

# TODO: Testen ausserhalb der IDE
# TODO: Remaining Estimate pro Worklog oder pro Projekt konfigurierbar machen (Tags?)
# TODO: Umgang mit Fehlern: Auflistung der Worklogeinträge, die nicht eingetragen wurden
# TODO: Hilfsklasse für das Ermitteln des eigenen Workspaces bei Toggl
# TODO: Automatisches Zuordnen der S'Up- und Planungs-Zeiten
# TODO: End-Time in Config auslagern (auf manchen Systemen wird im aktuellen Zustand die +02 für MEZ doppelt addiert)
# TODO: Problem bei gleicher Beschreibung in verschieden Toggl issues (Zeiten werden nicht richtig gebucht (Grundvermutung: Markierung als jira-processed zu langsam) Workarround: Alle Issues in Toggle unterschiedlich benenne
# TODO: Umgang mit gruppierten Issues ja/nein
# TODO: Umgang mit gruppierten Issues nur unter x min

_logger = logging.getLogger(__name__)


def read_configuration(config_file_name):
    configuration = {'configFile': None,
                     'jiraUser': None,
                     'jiraPassword': None,
                     'jiraUrl': None,
                     'jiraRePolicy': None,
                     'myTogglApiToken': None,
                     'myWorkspace': None,
                     'togglStartTime': None,
                     'useLogFile': False,
                     'logFile': None,
                     'logLevel': None,
                     'issue_number_regex_expression': None,
                     'groupTimeEntriesBy': None,
                     'max_days_go_back': None}

    # read configuration and exit if configuration options are missing

    config = configparser.ConfigParser()
    config.read(config_file_name)

    try:
        configuration['jiraUser'] = config.get("Jira", "user")
        configuration['jiraPassword'] = config.get("Jira", "password")
        configuration['jiraUrl'] = config.get("Jira", "url")
        if config.get("Jira", "remainingEstimatePolicy") == 'leave':
            configuration['jiraRePolicy'] = 'leave'
        elif config.get("Jira", "remainingEstimatePolicy") == 'auto':
            configuration['jiraRePolicy'] = 'auto'
        else:
            configuration['jiraRePolicy'] = 'auto'

        configuration['myTogglApiToken'] = config.get("Toggl", "apitoken")
        configuration['myWorkspace'] = config.get("Toggl", "workspace")
        configuration['issue_number_regex_expression'] = config.get("Toggl", "regex")
        configuration['groupTimeEntriesBy'] = config.get("Toggl", "groupTimeEntriesBy")

        if config.has_option("Common", "startdate"):
            configuration['togglStartTime'] = config.get("Common", "startdate")
        else:
            configuration['togglStartTime'] = (
                datetime.datetime.utcnow() - datetime.timedelta(int(config.get("Common", "maxdays")))).strftime(
                "%Y-%m-%dT%H:%M:%S+02:00")

        if config.get("Logging", "useLogFile") == 'true':
            configuration['useLogFile'] = True
            configuration['logFile'] = config.get("Logging", "file")
            configuration['logLevel'] = config.get("Logging", "level")
        else:
            configuration['useLogFile'] = False

    except configparser.NoOptionError as exception:
        print("Missing option in config.ini. Please refer to config_example.ini for the complete set of options.")
        print("Error message:")
        print(str(exception))
        exit()
    except configparser.NoSectionError as exception:
        print("Missing section in config.ini. Please refer to config_example.ini for the complete set of sections.")
        print("Error message:")
        print(str(exception))
        exit()

    return configuration


def extract_jira_issue_number(issue_name, issue_number_regex_expression):
    jira_issue_number = re.search(issue_number_regex_expression, issue_name)
    if jira_issue_number:
        return jira_issue_number.group(1)
    else:
        return None


def extract_jira_issue_numbers(project_list_response, issue_number_regex_expression):
    global _logger
    project_list = {}
    for project in project_list_response:
        issue_number = extract_jira_issue_number(project['name'], issue_number_regex_expression)
        if issue_number is not None:
            project_list[project['id']] = issue_number
        else:
            _logger.warning('The Toggl project with the name "{0}" contains no no valid JIRA issue number. Associated '
                            'time tracking entries will not be inserted in JIRA.'.format(str(project["name"])))
    return project_list


def is_json(myjson):
    try:
        json.loads(json.dumps(myjson))
    except ValueError:
        return False
    return True


def insert_jira_worklog(issue, start_time, duration, work_description, jira_re_policy, jira):
    if duration != '0m':
        return jira.add_worklog(issue, adjustEstimate=jira_re_policy, timeSpent=duration,
                                comment=work_description,
                                started=start_time)
    else:
        return None


def tag_timeentry_as_processed(time_entry_id, time_entry_description, toggl):
    global _logger
    # JSON snipppet for tagging time tracking entries which have been added successfully to JIRA
    payload_for_toggl_tag = {
        "time_entry": {
            "tags": ["jiraprocessed"]
        }
    }
    tagging_response = toggl.put(
        uri="/time_entries/{0}".format(str(time_entry_id)),
        data=payload_for_toggl_tag)
    if is_json(tagging_response):
        _logger.info(
            "The time entry with the id \"{0}\" (\"{1}\") has been tagged successfully in Toggl".format(
                str(time_entry_id), time_entry_description))
        return True
    return False


def tag_timeentry_as_error(time_entry_id, time_entry_description, toggl):
    global _logger
    # JSON snippet for marking a time tracking entry using a non-existing or archived project
    payload_for_toggl_error_tag = {
        "time_entry": {
            "tags": ["jiraerror"]
        }
    }
    tagging_response = toggl.put(
        uri="/time_entries/{0}".format(str(time_entry_id)),
        data=payload_for_toggl_error_tag)
    if is_json(tagging_response):
        _logger.info("The time entry with the id \"{0}\" (\"{1}\") has been tagged as"
                     "error in Toggl".format(str(time_entry_id), time_entry_description))
        return True
    return False


def tag_grouped_timeentry_as_error(time_entries, toggl):
    for time_entry in time_entries:
        tag_timeentry_as_error(time_entry['id'], time_entry['description'], toggl)


def main():
    global _logger
    config_file = "config.ini"
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:", ["configuration"])
    except getopt.GetoptError:
        print("processTimeTrackingEntries.py -c <configurationfile>")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-c", "--configuration"):
            config_file = arg

    configuration = read_configuration(config_file)

    if (configuration.get('useLogFile') == True):
        logging.basicConfig(filename=configuration['logFile'], level=configuration['logLevel'])
    else:
        logging.basicConfig(level=configuration['logLevel'])


    all_toggl_projects = {}

    toggl_end_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")

    #toggl = Toggl(configuration['myTogglApiToken'],version='v9')
    toggl = Toggl(configuration['myTogglApiToken'])

    if toggl.Workspaces.get_projects(configuration['myWorkspace']) is not None:
        all_toggl_projects = extract_jira_issue_numbers(toggl.Workspaces.get_projects(configuration['myWorkspace']),
                                                        configuration['issue_number_regex_expression'])

    new_time_tracking_entries = toggl.TimeEntries.get(start_date=configuration['togglStartTime'],
                                                      end_date=toggl_end_time)

    jira = JIRA(configuration['jiraUrl'], basic_auth=(configuration['jiraUser'], configuration['jiraPassword']))

    grouped_time_entries = {}

    for time_entry in new_time_tracking_entries:
        tags = time_entry.get('tags')
        if (tags is None) or ("jiraprocessed" not in tags):
            pid = time_entry.get('pid')
            description = time_entry['description'] if 'description' in time_entry else ''
            group_key = str(pid) + "_" + description

            start_time = dateutil.parser.parse(time_entry['start'])

            if configuration['groupTimeEntriesBy'] == 'day':
                group_key = group_key + '_' + str(start_time.timetuple().tm_yday)
            elif configuration['groupTimeEntriesBy'] == 'week':
                group_key = group_key + '_' + str(start_time.isocalendar()[1])
            else:
                group_key = group_key + '_' + str(start_time.isocalendar()[1])

            if group_key not in grouped_time_entries:
                grouped_time_entries[group_key] = {
                    "pid": pid,
                    "description": description,
                    "time_entries": []
                }
            error_flag = False
            if (time_entry.get('id') is None):
                error_flag = True
                _logger.warning(
                    'The time entry with the description "{1}" has has no id and cannot be transmitted to JIRA. Skipping next checks.'.format(
                        time_entry['description']))
            if (not error_flag and start_time is None):
                error_flag = True
                tag_timeentry_as_error(time_entry['id'], '(missing start time)', toggl)
                _logger.warning(
                    'The time entry with the id "{0}" and the description "{1}" has has no start time and cannot be transmitted to JIRA'.format(
                        str(time_entry['id']), time_entry['description']))
            if (not error_flag and time_entry.get('duration') is None):
                error_flag = True
                tag_timeentry_as_error(time_entry['id'], '(missing duration)', toggl)
                _logger.warning(
                    'The time entry with the id "{0}" and the description "{1}" has has no time entry and cannot be transmitted to JIRA'.format(
                        str(time_entry['id']), time_entry['description']))
            if (not error_flag and time_entry.get('description') is None):
                error_flag = True
                tag_timeentry_as_error(time_entry['id'], '(missing description)', toggl)
                _logger.warning(
                    'The time entry with the id "{0}" has has no description and cannot be transmitted to JIRA'.format(
                        str(time_entry['id'])))
            if not(error_flag):
                grouped_time_entries[group_key]["time_entries"].append({
                    "start_time": start_time,
                    "duration": time_entry['duration'],
                    "id": time_entry['id'],
                    "description": time_entry['description']
                })


        else:
            _logger.info(
                'The time entry with the id "{0}" and the description "{1}" has already been '
                'created as worklog in JIRA and subsequently tagged in Toggl'.format(
                    str(time_entry['id']), time_entry['description']))

    # when last Toggl time entry is running (duration is negative), all entries should be skipped.
    if (time_entry["duration"] < 0):
        _logger.error("Toggl is still running! No time entries will be processed. "
                        "Stop the current time entry and execute this script again!")
        return

    for key, grouped_time_entry in grouped_time_entries.items():
        if (len(grouped_time_entry["time_entries"]) > 0):
            start_time = min(time_entry["start_time"] for time_entry in grouped_time_entry["time_entries"])

            duration = sum(time_entry["duration"] for time_entry in grouped_time_entry["time_entries"])
            duration = str(round(duration / (float(60) * 15)) * 15) + "m"

            if (grouped_time_entry["pid"] is not None) and (all_toggl_projects.get(grouped_time_entry["pid"]) is not None):
                issue = jira.issue(all_toggl_projects[grouped_time_entry['pid']])
            elif extract_jira_issue_number(grouped_time_entry['description'],
                                           configuration['issue_number_regex_expression']) is not None:
                issue_number = extract_jira_issue_number(grouped_time_entry['description'],
                                                         configuration['issue_number_regex_expression'])
                try:
                    issue = jira.issue(issue_number)
                except JIRAError:
                    _logger.error("The issue {0} could not be found in JIRA.".format(str(issue_number)))
                    tag_grouped_timeentry_as_error(grouped_time_entry["time_entries"], toggl)
                    continue
            elif (grouped_time_entry["pid"] is not None) and (all_toggl_projects.get(grouped_time_entry["pid"]) is None):
                _logger.error(
                    "The project with the id {0} is not in the list of active projects.".format(
                        str(grouped_time_entry["pid"])))
                tag_grouped_timeentry_as_error(grouped_time_entry["time_entries"], toggl)
                continue
            else:
                _logger.error("No JIRA issue number could be extracted from time entry project or work description. "
                              "Therefore no worklog will be inserted in JIRA.")
                # taggingResponse = _toggl.put(
                #     uri="https://www.toggl.com/api/v8/time_entries/{0}".format(str(timeEntry['id'])),
                #     data=_payloadForTogglErrorTag)
                # if taggingResponse.status_code == 200:
                #     _logger.info(
                #      "The time entry with the id \"{0}\" has been tagged as error in Toggl".format(str(timeEntry['id'])))
                continue
            if issue is not None:
                jira_response = insert_jira_worklog(issue, start_time, duration, grouped_time_entry['description'],
                                                    configuration['jiraRePolicy'], jira)
                if isinstance(jira_response, Worklog):
                    for timeEntry in grouped_time_entry["time_entries"]:
                        _logger.info(
                            "A worklog for the time entry with the id \"{0}\" and the description \"{1}\" has been "
                            "created successfully".format(
                                str(timeEntry['id']), timeEntry['description']))
                        tag_timeentry_as_processed(timeEntry['id'], timeEntry['description'], toggl)
                else:
                    _logger.error('No JIRA worklog could be created.')
                    tag_grouped_timeentry_as_error(grouped_time_entry["time_entries"], toggl)
                    continue
            else:
                _logger.error('No JIRA issue could be created with the given information.')
                tag_grouped_timeentry_as_error(grouped_time_entry["time_entries"], toggl)
                continue
        else:
            grouped_time_entry["time_entries"]



if __name__ == "__main__":
    main()
