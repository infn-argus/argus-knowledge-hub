# olog-to-argus

Sends a facility's Olog (Phoebus electronic logbook) entries to ARGUS Knowledge Hub, once a day. Each entry
becomes a **Logbook Entry** document in the facility's workspace: published, with its logbooks, tags, level,
properties and files, a link back to Olog, and relations to the equipment its text names. Ask ARGUS then
answers questions such as "what happened on the linac last Tuesday" from the logbook.

- An entry already in ARGUS and unchanged is left alone; an edited one (later `modifyDate`) becomes a new
  revision. Overlapping runs and retries are therefore safe.
- Each run looks back `LOOKBACK_DAYS` (default 2), so a missed night is caught by the next. An entry edited
  after that window is picked up only by a run with `--all`.
- Files are sent only when ARGUS does not have them yet.
- Standard library only: it runs in `python:3.11-slim` with nothing to install.

## In EPIK8s

The Phoebus services chart (`phoebus-services-chart`, olog service) runs it as the CronJob
`<release>-argus-upload`. In the beamline's `deploy/values.yaml`, under the `olog` service:

```yaml
argusUpload:
  enabled: true
  url: "https://<argus api host>"
  facility: "btf"
  entryUrl: "https://btf-webolog.example.org/logs/{id}"
  all: false          # true for the first run only
```

and once, the robot token (ARGUS: the workspace's administration → **Robot tokens** → *Daily logbook
upload*):

```bash
kubectl -n btf create secret generic argus-olog-upload --from-literal=token='argus_bot_…'
```

Send the logbook's history once, then let the schedule take over: a job made from the CronJob with
`OLOG_ALL=true`.

```bash
kubectl -n btf create job --from=cronjob/olog-argus-upload olog-argus-first-run --dry-run=client -o json \
  | python3 -c 'import json,sys; j=json.load(sys.stdin); c=j["spec"]["template"]["spec"]["containers"][0]; \
[e.update(value="true") for e in c["env"] if e["name"]=="OLOG_ALL"]; print(json.dumps(j))' \
  | kubectl -n btf apply -f -
kubectl -n btf logs -f job/olog-argus-first-run
```

(Or set `all: true` in the values for one night, then back to `false`.)

## By hand

```bash
OLOG_URL=http://olog.btf.svc:8080/Olog ARGUS_URL=https://<argus api host> ARGUS_TOKEN=argus_bot_… \
ARGUS_FACILITY=btf python olog_to_argus.py            # --all for every entry
```

It prints what it did (`created 12, updated 1, unchanged 40, rejected 0, files 3, failures 0`) and exits 1
when something failed.
