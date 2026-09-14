# LibreDWG converts AutoCAD DWG to DXF, which is what makes a drawing
# viewable in a browser — nothing renders DWG directly, and sending the
# drawings to a conversion service would mean handing INFN's drawings to a
# third party. Built from source because Debian carries no package for it.
# GPL-3: used as a command-line program, not linked into this application.
FROM python:3.11-slim AS libredwg

ARG LIBREDWG_VERSION=0.13.3

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates build-essential \
 && curl -fsSL "https://github.com/LibreDWG/libredwg/releases/download/${LIBREDWG_VERSION}/libredwg-${LIBREDWG_VERSION}.tar.gz" \
      -o /tmp/libredwg.tar.gz \
 && cd /tmp && tar xzf libredwg.tar.gz && cd "libredwg-${LIBREDWG_VERSION}" \
 && ./configure --disable-bindings --disable-python >/dev/null \
 && make -j"$(nproc)" >/dev/null \
 && make install >/dev/null \
 && rm -rf /tmp/libredwg*


FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/infn-argus/argus-knowledge-hub"
LABEL org.opencontainers.image.description="ARGUS Knowledge Hub — REST API (assets, tickets, documentation)"
LABEL org.opencontainers.image.licenses="INFN"


WORKDIR /app

# libkrb5-dev builds the gssapi wheel; libkrb5-3 and the GSSAPI module are
# what it needs at run time, for binding to a Kerberos-backed LDAP with a
# service keytab instead of a password.
RUN apt-get update && apt-get install -y \
    gcc \
    libkrb5-dev \
    libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*

# Just the converter and its library — the toolchain that built it stays in
# the builder stage.
COPY --from=libredwg /usr/local/bin/dwg2dxf /usr/local/bin/dwg2dxf
COPY --from=libredwg /usr/local/lib/libredwg.so* /usr/local/lib/
RUN ldconfig

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY alembic alembic
COPY alembic.ini .
COPY scripts scripts

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
