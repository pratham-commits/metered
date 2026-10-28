#!/usr/bin/env bash
# Person 1. The only supported way to publish an image.
#
# Usage: scripts/push.sh <service>
# service is one of: rider, driver, ride-request, matching, dispatch, trip-tracking, demand-sink
# Tag is the current git short SHA. Repository is
# <account>.dkr.ecr.ap-south-1.amazonaws.com/rideshare/<service>:<sha>
# Log in with aws ecr get-login-password. Build with the repo root as context and
# -f services/<service>/Dockerfile. Push that tag.
# Print the image line. The author pastes it into deploy/apps/<service>/deployment.yaml and commits.
# Do not kubectl set image. Argo CD rolls the pod from the git commit.
