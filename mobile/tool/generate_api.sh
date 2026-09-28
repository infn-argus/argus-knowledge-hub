#!/usr/bin/env bash
# Regenerate the Dart API client from the committed field-client contract
# (backend/openapi/field-client.json, written by `python -m app.contract`).
# Needs Java and openapi-generator-cli 7.10.0 (OPENAPI_GENERATOR_JAR, or downloaded to .tool/).
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
jar="${OPENAPI_GENERATOR_JAR:-$here/.tool/openapi-generator-cli-7.10.0.jar}"
if [ ! -f "$jar" ]; then
  mkdir -p "$(dirname "$jar")"
  curl -sSfL -o "$jar" https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/7.10.0/openapi-generator-cli-7.10.0.jar
fi
rm -rf "$here/packages/argus_api"
# `path` (the resolver's query parameter) would shadow the generated local variable of that name.
java -jar "$jar" generate \
  -i "$here/../backend/openapi/field-client.json" \
  -g dart \
  -o "$here/packages/argus_api" \
  --parameter-name-mappings path=linkPath \
  --additional-properties=pubName=argus_api,pubDescription="Generated ARGUS field-client API",pubVersion=0.1.0 \
  --global-property=apiTests=false,modelTests=false,apiDocs=false,modelDocs=false >/dev/null
# Generated code is not edited by hand: a change comes from the contract. It must compile: the
# app's analyzer does not look inside a path dependency, so check it here.
rm -f "$here/packages/argus_api/.travis.yml" "$here/packages/argus_api/git_push.sh"
(cd "$here/packages/argus_api" && dart pub get >/dev/null && dart analyze --no-fatal-warnings >/dev/null)
echo "generated $here/packages/argus_api"
