# Toggl-JIRA-Integration

This script allows you to conveniently track your time in Toggl (<https://www.toggl.com>) and push your time tracking entries as worklogs to JIRA (<https://www.atlassian.com/software/jira>).
The script has been developed with Python 3 and tested with JIRA 8.2.4.

The configuration options are (mostly) described in the config_example.ini file.

## Run in Docker container

Create and run a container based on the image build from the provided Dockerfile:

```
docker run \
  --rm \
  --mount type=bind,source="$(pwd)",target=/config \
  docker-registry.disy.net/disy/toggl-jira-integration
```

The image resulting from the provided Dockerfile is configured for amd64 architecture. A multiarch build is not available at the moment because Python does not provide a corresponding multiarch base image. You can however build your image by overwriting the image name and tag if you have a suitable base image (should be Debian based):
```
docker build --build-arg IMAGE_NAME=arm64v8/python --build-arg IMAGE_TAG=3.10-slim -t <myimage>:<mytag> .
```
