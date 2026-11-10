#!/usr/bin/env bash
# Rebuilds what is in this folder. Run by hand with network access; the result
# is committed, because the app is offline and fetches nothing at run time.
# Nothing in the app or the tests depends on this script.
#
#   nspell.js        nspell 2.1.5 (MIT) and is-buffer 2.0.5 (MIT) from npm, their
#                    CommonJS files wrapped one function each and joined by a
#                    require table into one ES module, nothing else changed.
#   en_AU.aff/.dic   LibreOffice's dictionaries (en/en_AU.* in the LibreOffice
#                    `dictionaries` repository, SCOWL-derived, permissive).
#   en_GB.aff/.dic   SCOWL's own hunspell-en_GB-ise 2020.12.07 from
#                    https://sourceforge.net/projects/wordlist/files/speller/
#                    (LibreOffice's en_GB is LGPL and not SCOWL-derived, so it
#                    is not used), renamed from en_GB-ise.*.
#   frequency.txt    https://app.aspell.net/create with spelling=US, GBs and AU,
#                    max_variant=1, diacritic=strip, at max_size 35, 40 and 50:
#                    a word's bucket is the smallest size it appears in, so the
#                    harper-worker's suggestions can be ranked by how common
#                    each is. Lowercased, possessives dropped.
set -euo pipefail
cd "$(dirname "$0")"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
(cd "$work" && npm pack nspell@2.1.5 is-buffer@2.0.5 >/dev/null)
echo "unpack both tarballs in $work, wrap each lib/*.js as defs[id] = function (module, exports) {...}"
echo "with require() calls rewritten to req(id), and export default req('./index.js'): see nspell.js's header."
for size in 35 40 50; do
  curl -fsS "https://app.aspell.net/create?max_size=$size&spelling=US&spelling=GBs&spelling=AU&max_variant=1&diacritic=strip&download=wordlist&encoding=utf-8&format=inline" -o "$work/size$size.txt"
done
echo "frequency.txt: '# 35' then those words, '# 40' then the words new at 40, '# 50' likewise, one per line."
