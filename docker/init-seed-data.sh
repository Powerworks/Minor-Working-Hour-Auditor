#!/bin/bash
set -x
cd /app
python3 -u setup_db.py
echo "setup_db.py exit code: $?"
