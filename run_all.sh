#!/usr/bin/env bash
set -e
python3 analysis.py
python3 audit.py
python3 build_report.py
