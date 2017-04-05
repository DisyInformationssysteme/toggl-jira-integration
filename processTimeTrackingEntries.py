# -*- coding: utf-8 -*-

# processTimeTrackingEntries.py - reads time tracking entries from the Toggl (https://www.toggl.com) REST-API and
# adds the time tracking entries as work logs to JIRA issues.
# Copyright (C) 2017 Carsten Heidmann (carsten@heidmann.info)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import datetime
import dateutil.parser
import logging
import re
import math
import configparser

from togglwrapper import Toggl
from jira import Worklog
from jira import JIRA

# TODO: Testen ausserhalb der IDE
# TODO: Remaining Estimate pro Worklog oder pro Projekt konfigurierbar machen (Tags?)
# TODO: Umgang mit Fehlern: Auflistung der Worklogeinträge, die nicht eingetragen wurden
# TODO: Hilfsklasse für das Ermitteln des eigenen Workspaces bei Toggl
# TODO: Automatisches Zuordnen der S'Up- und Planungs-Zeiten
# TODO: End-Time in Config auslagern (auf manchen Systemen wird im aktuellen Zustand die +02 für MEZ doppelt addiert)
# TODO: Problem bei gleicher Beschreibung in verschieden Toggl issues (Zeiten werden nicht richtig gebucht (Grund vermutung: Markierung als jira-processed zu langsam) Workarround: Alle Issues in Toggle unterschiedlich benenne
# TODO: Umgang mit gruppierten Issues ja/nein
# TODO: Umgang mit gruppierten Issues nur unter x min

config = configparser.ConfigParser()
config.read("config.ini")

_jiraUser = None
_jiraPassword = None
_jiraUrl = None
_jiraRePolicy = None
_myTogglApiToken = None
_myWorkspace = None
_togglStartTime = None
_logFile = None
_logLevel = None
_groupTimeEntriesBy = None

# read configuration and exit if configuration options are missing
try:
    _jiraUser = config.get("Jira", "user")
    _jiraPassword = config.get("Jira", "password")
    _jiraUrl = config.get("Jira", "url")
    _jiraRePolicy = None
    if (config.get("Jira", "remainingEstimatePolicy") == 'leave'):
        _jiraRePolicy = 'leave'
    elif (config.get("Jira", "remainingEstimatePolicy") == 'auto'):
        _jiraRePolicy = 'auto'
    else:
        _jiraRePolicy = 'auto'

    _myTogglApiToken = config.get("Toggl", "apitoken")
    _myWorkspace = config.get("Toggl", "workspace")
    _issue_number_regex_expression = config.get("Toggl", "regex")
    _groupTimeEntriesBy = config.get("Toggl", "groupTimeEntriesBy")

    if config.has_option("Common", "startdate"):
        _togglStartTime = config.get("Common", "startdate")
    else:
        _maxDaysGoBack = int(config.get("Common", "maxdays"))
        _togglStartTime = (datetime.datetime.utcnow() - datetime.timedelta(_maxDaysGoBack)).strftime("%Y-%m-%dT%H:%M:%S+02:00")

    _logFile = config.get("Logging", "file")
    _logLevel = config.get("Logging", "level")

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


# JSON snipppet for tagging time tracking entries which have been added successfully to JIRA
_payloadForTogglTag = {
    "time_entry": {
        "tags": ["jiraprocessed"]
    }
}

# JSON snippet for marking a time tracking entry using a non-existing or archived project
_payloadForTogglErrorTag = {
    "time_entry": {
        "tags": ["nosuchprojecterror"]
    }
}

logging.basicConfig(filename=_logFile, level=_logLevel)
_logger = logging.getLogger('timetracking')

_togglEndTime = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")


def extract_jira_issue_number(issue_name):
    jira_issue_number = re.search(_issue_number_regex_expression, issue_name)
    if jira_issue_number:
        return jira_issue_number.group(1)
    else:
        return None


def extract_jira_issue_numbers(projectListResponse):
    projectList = {}
    for project in projectListResponse:
        issue_number = extract_jira_issue_number(project['name'])
        if issue_number is not None:
            projectList[project['id']] = issue_number
        else:
            _logger.warning('The Toggl project with the name "{0}" contains no no valid JIRA issue number. Associated '
                            'time tracking entries will not be inserted in JIRA.'.format(str(project["name"])))
    return projectList


def is_json(myjson):
    try:
        json_object = json.loads(myjson)
    except ValueError:
        return False
    return True


_toggl = Toggl(_myTogglApiToken)

_allTogglProjects = extract_jira_issue_numbers(_toggl.Workspaces.get_projects(_myWorkspace))

_newTimeTrackingEntries = _toggl.TimeEntries.get(start_date=_togglStartTime, end_date=_togglEndTime)

_jira = JIRA(_jiraUrl, basic_auth=(_jiraUser, _jiraPassword))


def insert_jira_worklog(issue, start_time, duration, work_description):
    if duration != '0m':
        return _jira.add_worklog(issue, adjustEstimate=_jiraRePolicy, timeSpent=duration,
                                 comment=work_description,
                                 started=start_time)
    else:
        return None


groupedTimeEntries = {}
for timeEntry in _newTimeTrackingEntries:
    tags = timeEntry.get('tags')
    if (tags is None) or (not "jiraprocessed" in tags):
        pid = timeEntry.get('pid')
        description = timeEntry['description'] if 'description' in timeEntry else ''
        group_key = str(pid) + "_" + description

        start_time = dateutil.parser.parse(timeEntry['start'])

        if (_groupTimeEntriesBy == 'day'):
            group_key = group_key + '_' + str(start_time.timetuple().tm_yday)
        elif (_groupTimeEntriesBy == 'week'):
            group_key = group_key + '_' + str(start_time.isocalendar()[1])
        else:
            group_key = group_key + '_' + str(start_time.isocalendar()[1])

        if group_key not in groupedTimeEntries:
            groupedTimeEntries[group_key] = {
                "pid": pid,
                "description": description,
                "time_entries": []
            }

        groupedTimeEntries[group_key]["time_entries"].append({
            "start_time": start_time,
            "duration": timeEntry['duration'],
            "id": timeEntry['id']
        })
    else:
        _logger.info(
            'The time entry with the id "{0}" has already been created as worklog in JIRA and subsequently tagged in Toggl'.format(
                str(timeEntry['id'])))

for key, groupedTimeEntry in groupedTimeEntries.items():
    jira_response = None
    issue = None
    start_time = min(timeEntry["start_time"] for timeEntry in groupedTimeEntry["time_entries"])

    duration = sum(timeEntry["duration"] for timeEntry in groupedTimeEntry["time_entries"])
    duration = str(math.ceil(duration / (float(60) * 15)) * 15) + "m"

    if (groupedTimeEntry["pid"] is not None) and (_allTogglProjects.get(groupedTimeEntry["pid"]) is not None):
        issue = _jira.issue(_allTogglProjects[groupedTimeEntry['pid']])
    elif extract_jira_issue_number(groupedTimeEntry['description']) is not None:
        issue = _jira.issue(extract_jira_issue_number(groupedTimeEntry['description']))
    elif (groupedTimeEntry["pid"] is not None) and (_allTogglProjects.get(groupedTimeEntry["pid"]) is None):
        _logger.error(
            "The project with the id {0} is not in the list of active projects.".format(str(groupedTimeEntry["pid"])))

        for timeEntry in groupedTimeEntry["time_entries"]:
            taggingResponse = _toggl.put(
                uri="https://www.toggl.com/api/v8/time_entries/{0}".format(str(timeEntry['id'])),
                data=_payloadForTogglErrorTag)
            if taggingResponse.status_code == 200:
                _logger.info(
                    "The time entry with the id \"{0}\" has been tagged as error in Toggl".format(str(timeEntry['id'])))
        break
    else:
        _logger.error("No JIRA issue number could be extracted from time entry project or work description. "
                      "Therefore no worklog will be inserted in JIRA.")
        break
    if issue is not None:
        jira_response = insert_jira_worklog(issue, start_time, duration, groupedTimeEntry['description'])
        if isinstance(jira_response, Worklog):
            for timeEntry in groupedTimeEntry["time_entries"]:
                _logger.info(
                    "A worklog for the time entry with the id \"{0}\" has been created successfully".format(
                        str(timeEntry['id'])))
                taggingResponse = _toggl.put(
                    uri="/time_entries/{0}".format(str(timeEntry['id'])),
                    data=_payloadForTogglTag)

                if is_json(str(taggingResponse)):
                    _logger.info(
                        "The time entry with the id \"{0}\" has been tagged successfully in Toggl".format(
                            str(timeEntry['id'])))
        else:
            _logger.error('No JIRA worklog could be created.')
            break
    else:
        _logger.error('No JIRA issue could be created with the given information.')
