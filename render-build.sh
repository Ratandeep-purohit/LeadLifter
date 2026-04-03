#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Create an empty db file if it doesn't exist
# touch crm_db.sqlite 

# Run database migrations
flask db upgrade
