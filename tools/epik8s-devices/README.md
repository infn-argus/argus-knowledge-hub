# epik8s-devices

Turns a beamline's EPIK8s configuration into an inventory of equipment you
can read, correct, and then load into an ARGUS Knowledge Hub.

It runs on your machine, against files and repositories you already have.
It never writes to the control configuration: `deploy/values.yaml` deploys
the accelerator, and this only reads it.

## Why it is a separate tool

The control configuration is the record that works. The inventory is the
record that is incomplete. Pulling the first into the second automatically,
as a server-side import, produces a second parallel tree of objects that
nobody reconciles — which is exactly what happened the first time.

So the steps are separate and a person sits between them:

    scan    read the configuration        → devices.yaml, yours to correct
    match   propose which physical asset  → evidence, not decisions
    push    write into a hub workspace    → names the workspace first

## What a device is

One row per thing that can fail. The configuration is organised around
IOCs — software — but an IOC drives eight ion pumps, and it is a pump that
trips.

Each row carries what the configuration knows and says plainly what it
does not:

    key, name, pv                the handles
    device_class, vendor, model  what the equipment is
    element                      what it acts on: quadrupole, ion pump, slit
    system, zones                where it belongs
    connection                   direct, through a terminal server, or on
                                 the instrument itself — with host and port
    model_spec                   the ps:/motor: rating: polarity, current
                                 limits, ramp, velocity, resolution
    physical_asset, model_asset  empty, for you or `match` to fill
    needs                        what is missing from this row

## Where the classification comes from

Not from a table written here. `infn-epics-ioc/ibek-templates` already
states it in its directory tree:

    templates/<category>/<vendor>/<template>.yaml.j2
    templates/ps/ocem/ocem.yaml.j2          → Power Supply, OCEM
    templates/vac/agilent/agilent-vac.yaml.j2 → Vacuum, Agilent

so the catalogue is read from that repository and stays true as templates
are added. Point `--templates` at your checkout. Four templates have no
ibek file because the IOC runs on the instrument over ssh (Libera, STEMlab,
MRF); those have a built-in fallback. Anything else comes out with its
class empty and `needs` saying so, rather than guessed.

The element — what the device acts on — is read from the name, which at
LNF is a code: `QUATB002` is a quadrupole, `GUNSIP01` the gun's first
sputter-ion pump, `FI8-CAM-06` a camera in FI8. A name that matches no
convention gets no element rather than a wrong one.

## Use

    python -m epik8s_devices scan ../epik8-sparc/deploy/values.yaml \
        --templates ../infn-epics-ioc/ibek-templates \
        --out sparc-devices.yaml

    # or a spreadsheet to go through with the people who own the hardware
    python -m epik8s_devices scan ../epik8-sparc/deploy/values.yaml \
        --format csv --out sparc-devices.csv

    python -m epik8s_devices match sparc-devices.yaml \
        --hub https://assets-api.example.infn.it --token "$ARGUS_TOKEN"

    python -m epik8s_devices push sparc-devices.yaml \
        --hub https://assets-api.example.infn.it --token "$ARGUS_TOKEN" --dry-run

`push` asks you to type the workspace id before it writes anything. The
token decides the workspace, and a token for the wrong one is easy to have.

## Requirements

Python 3.9+, `pyyaml`. `match` and `push` also need network access to the
hub; `scan` needs nothing but the files.
