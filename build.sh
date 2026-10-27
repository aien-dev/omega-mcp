#!/bin/sh
# Build omega-mcp with the pinned Omega compiler.
#   OMC=/path/to/omc ./build.sh        (default: $OMEGA_SRC/seed/out/omc, OMEGA_SRC default ../omega-mv)
# Output: build/omega-mcp, build/omc (copy of the pinned compiler), build/data/ (reference data).
# The unit is the concatenation listed in src/UNITS: the sha256 unit first (its `layout` must precede
# every fn; `export fn` becomes `fn` because a program unit has a `fn main`), then the JSON units,
# then the server units. The leading `om2` line opts the whole unit into profile OM-2.
set -eu
cd "$(dirname "$0")"
PIN=2c82480596bbdc50cda9626866209ef662d5834f278f839ff4ce0250c495029f
OMC=${OMC:-${OMEGA_SRC:-../omega-mv}/seed/out/omc}
got=$(sha256sum "$OMC" | cut -d' ' -f1)
if [ "$got" != "$PIN" ]; then
  echo "build.sh: $OMC has sha256 $got, expected the pin $PIN" >&2
  exit 2
fi
mkdir -p build
unit=build/omega-mcp.om
{
  printf 'om2\n'
  first=1
  while read -r f; do
    case "$f" in ''|'#'*) continue ;; esac
    if [ $first = 1 ]; then
      sed 's/^export fn /fn /' "$f" | grep -v '^om2$'
      first=0
    else
      cat "$f"
    fi
  done < src/UNITS
} > "$unit"
rc=0
"$OMC" < "$unit" > build/omega-mcp.new 2> build/omc.err || rc=$?
if [ $rc -ne 0 ]; then
  cat build/omc.err >&2
  echo "build.sh: omc refused the unit (exit $rc); line numbers refer to $unit" >&2
  rm -f build/omega-mcp.new
  exit 1
fi
chmod 755 build/omega-mcp.new
mv build/omega-mcp.new build/omega-mcp
cp "$OMC" build/omc.new && chmod 755 build/omc.new && mv build/omc.new build/omc
rm -rf build/data && cp -R data build/data
sha256sum build/omega-mcp build/omc
