#!/usr/bin/env bash
# Person 3. Build services/fare/dist/fare.zip for the linux/amd64 Lambda runtime.
#
# Use public.ecr.aws/sam/build-python3.12 to pip install psycopg[binary]==3.2.4.
# Copy handler.py and rideshare/__init__.py, fare.py, zones.py into the dist tree.
# Zip from inside dist so the paths are handler.py and rideshare/*.py at the zip root.
# Do not bundle boto3. The Lambda runtime already has it.
# Tell the platform maintainer when services/fare/dist/fare.zip exists so they can apply infra/lambda.
