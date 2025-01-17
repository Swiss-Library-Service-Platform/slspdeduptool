# This script is used to deploy the environment for the project.
#
# There is two options to deploy the environment:
# 1. Simple deploy:
#    - Activate virtualenv
#    - Pull the last version of main branch
#    - Restart the Apache server

# 2. Full deploy:
#    - Activate virtualenv
#    - Pull the last version of main branch
#    - Update the required packages (virtualenv)
#    - Restart the Apache server

source dedupenv/bin/activate
python3 manage.py collectstatic --noinput

sudo systemctl stop apache2
sudo systemctl start apache2