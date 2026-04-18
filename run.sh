#!/bin/bash
# Simple runner for development

export PYTHONPATH="$(dirname $0)/src"
python3 -m oatbrain "$@"
