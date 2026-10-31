#!/bin/sh
# Runs the read-only catalogue inventory (scripts/catalogue_inventory.py) in the production API pod and copies
# the report to ./catalogue-inventory. Usage, from the repository root: sh backend/scripts/run_catalogue_inventory.sh
set -e
K="kubectl --kubeconfig $HOME/kubeconfigs/cloud-config.txt -n argus"
POD=$($K get pods -o name | grep argus-api | head -1 | cut -d/ -f2)
[ -n "$POD" ] || { echo "no argus-api pod found"; exit 1; }
echo "pod: $POD"
$K cp backend/scripts/catalogue_inventory.py "$POD:/tmp/catalogue_inventory.py" -c api
$K exec "$POD" -c api -- sh -c 'cd /app && python /tmp/catalogue_inventory.py --out /tmp/inv'
$K cp "$POD:/tmp/inv" ./catalogue-inventory -c api
ls -l catalogue-inventory
