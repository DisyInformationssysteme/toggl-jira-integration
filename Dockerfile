FROM library/python:3.9-slim

COPY ./processTimeTrackingEntries.py /
RUN pip install --no-cache-dir python-dateutil togglwrapper jira

CMD ["python", "/processTimeTrackingEntries.py", "-c", "/config/config.ini"]