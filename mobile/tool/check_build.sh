#!/usr/bin/env bash
# A69: a built bundle carries no provider credential, model prompt or provider endpoint.
# Usage: mobile/tool/check_build.sh <file or directory> (a web build, an unzipped APK or IPA).
set -euo pipefail
target="${1:?give the build output to scan}"
pattern='sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{30,}|api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis|/chat/completions|You are (a|an) [a-z]+ (assistant|model)|system prompt'
if grep -rEaoi "$pattern" "$target" | head -20 | grep .; then
  echo "FAIL: the build carries a credential, a prompt or a provider endpoint (see above)" >&2
  exit 1
fi
echo "ok: no credential, prompt or provider endpoint in $target"
