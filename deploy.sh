#!/bin/bash

# This script is used to deploy the environment for the project.
#
# There is two options to deploy the environment:
# 1. Simple deploy (./deploy.sh):
#    - Activate virtualenv
#    - Pull the last version of main branch
#    - Restart the Apache server

# 2. Full deploy (./deploy.sh --update-env):
#    - Activate virtualenv
#    - Pull the last version of main branch
#    - Update the required packages (virtualenv)
#    - Restart the Apache server

# Activate virtualenv
source dedupenv/bin/activate

# Update the project
git pull

# Check if the user wants to update the environment
if [[ $1 == "--update-env" ]]; then
    pip install --upgrade -r requirements.txt
fi

# Collect static files in root static folder
python3 manage.py collectstatic --noinput

# Restart the Apache server
sudo systemctl stop apache2
sudo systemctl start apache2