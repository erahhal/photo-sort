#!/usr/bin/env bash

python -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
DEFAULT_SHELL=$(getent passwd $USER | awk -F: '{print $NF}')
$DEFAULT_SHELL
