#!/usr/bin/env bash
set -euo pipefail

pyside6-lrelease \
  src/oss_cam_scanner/translations/oss_cam_scanner_zh_CN.ts \
  -qm src/oss_cam_scanner/translations/oss_cam_scanner_zh_CN.qm
