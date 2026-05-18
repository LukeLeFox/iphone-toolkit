#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"
PYTHONPATH=src python -m iphone_toolkit
