#!/usr/bin/env bash
set -euo pipefail

pyside6-lupdate \
  -extensions py \
  src/oss_cam_scanner \
  -ts src/oss_cam_scanner/translations/oss_cam_scanner_zh_CN.ts
