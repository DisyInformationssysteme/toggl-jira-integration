# Toggl-JIRA-Integration
This script allows you to conveniently track your time in Toggl (https://www.toggl.com) and push your time tracking entries as worklogs to JIRA (https://www.atlassian.com/software/jira).
The script has been developed with Python 3 and tested with JIRA 8.2.4.

The configuration options are (mostly) described in the config_example.ini file.

## Run in Docker container
Create and run a container based on the image build from the provided Dockerfile:
```
docker run \
  --rm \
  --mount type=bind,source="$(pwd)",target=/config \
  docker-registry.disy.net/disy/toggl-jira-integration