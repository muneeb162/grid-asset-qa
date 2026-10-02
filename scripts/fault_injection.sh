#!/usr/bin/env bash
# Fault injection: plant three realistic defects one at a time and confirm the suite catches each.
# A test suite that never fails is not proof of quality. This script proves these tests can fail.
# Usage: ./scripts/fault_injection.sh
set -u
cd "$(dirname "$0")/.."

backup() { cp app/models.py /tmp/models.py.bak; cp app/service.py /tmp/service.py.bak; }
restore() { cp /tmp/models.py.bak app/models.py; cp /tmp/service.py.bak app/service.py; }
trap restore EXIT

run_case() {
  local title="$1" file="$2" from="$3" to="$4"
  backup
  sed -i "s/${from}/${to}/" "$file"
  if cmp -s "$file" "/tmp/$(basename "$file").bak"; then
    echo "SKIPPED  $title (pattern not found, code may have changed)"; restore; return
  fi
  if python -m pytest -q -x -p no:cacheprovider >/tmp/fault.log 2>&1; then
    echo "MISSED   $title  <-- the suite has a gap here"
  else
    echo "CAUGHT   $title  by $(grep -m1 '^FAILED' /tmp/fault.log | cut -d' ' -f2)"
  fi
  restore
}

run_case "Swapped GeoJSON coordinates" app/service.py \
  '"coordinates": \[a.longitude, a.latitude\]' '"coordinates": [a.latitude, a.longitude]'
run_case "Off-by-one at the 60 kV boundary" app/models.py \
  'if voltage_kv < HIGH_VOLTAGE_FROM_KV:' 'if voltage_kv <= HIGH_VOLTAGE_FROM_KV:'
run_case "Resolved outage does not restore status" app/service.py \
  'self._assets\[outage.asset_id\].status = AssetStatus.IN_SERVICE' 'pass'
