#!/usr/bin/env bash
# Rebuilds perfect-freehand.min.js: the npm package's CommonJS build wrapped as a classic script that sets
# window.perfectFreehand. Run by hand when an upgrade is wanted (node and npm on PATH); the app has no build
# step and nothing is fetched at run time. Needs the version in VERSION.txt.
set -euo pipefail
cd "$(dirname "$0")"
version="$(sed -n 's/^perfect-freehand \([0-9.]*\).*/\1/p' VERSION.txt)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
(cd "$work" && npm pack "perfect-freehand@$version" --silent >/dev/null && tar xzf ./*.tgz)
{
  echo "/*! perfect-freehand $version, MIT licence, see LICENSE beside this file. The npm CJS build wrapped as a classic script (build.sh). */"
  echo '(function(){var exports={};'
  sed '/^\/\/# sourceMappingURL/d' "$work/package/dist/cjs/index.js"
  echo ';window.perfectFreehand={getStroke:exports.getStroke,getStrokePoints:exports.getStrokePoints,getStrokeOutlinePoints:exports.getStrokeOutlinePoints};})();'
} > perfect-freehand.min.js
echo "wrote perfect-freehand.min.js"
