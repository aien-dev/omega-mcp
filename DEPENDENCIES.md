# Dependencies

The server is first-party Omega (`src/*.om`, plus `vendor/omega-mv/` copied unchanged from
omega-mv@e5b32567). Everything below is a host tool. Versions are the ones the recorded evidence ran
with on Linux arm64 (Ubuntu 24.04 packages).

## Runtime (the server executes these)

| Tool | Version | What it does for us | Omega replacement |
|---|---|---|---|
| `/usr/bin/bwrap` | bubblewrap 0.9.0 (deb 0.9.0-1ubuntu0.3) | Builds the per-call sandbox: new user, mount, pid, net, ipc, uts and cgroup namespaces, cleared environment, read-only binds of the compiler or program and the reaper, a 16 MiB tmpfs working directory | A first-party Omega sandbox launcher using `clone`/`unshare`, `mount` and `pivot_root` host words, once omega-mv exposes namespace and mount words (not present at e5b32567) |
| `/usr/bin/prlimit` | util-linux 2.39.3 (deb 2.39.3-9ubuntu6.6) | Applies RLIMIT_CPU, AS, FSIZE, NPROC, NOFILE and CORE to the sandbox's pid before it is released | A `setrlimit`/`prlimit64` host word in omega-mv, after which the reaper sets its own limits |
| omc (pinned) | sha256 `2c82480596bbdc50cda9626866209ef662d5834f278f839ff4ce0250c495029f`, omega-mv e5b32567 | The compiler the `compile` and `run` tools invoke | none needed: it is the Omega compiler |

## Build

| Tool | Version | What it does for us | Omega replacement |
|---|---|---|---|
| `/bin/sh`, `sed`, `grep`, `cat`, `cp`, `sha256sum` (`build.sh`) | dash 0.5.12, GNU sed 4.9, GNU grep 3.11, GNU coreutils 9.4 | Concatenate `src/UNITS` into one unit, strip `export`, check the compiler pin, copy outputs | An Omega build program that reads `src/UNITS`, checks the pin with the vendored sha256 unit and writes the unit |

## Authoring and verification (never executed by the server)

| Tool | Version | What it does for us | Omega replacement |
|---|---|---|---|
| Python 3 (`tools/gen-reference.py`, `tools/ref_examples.py`) | 3.12.3 | Writes `data/reference.json` and `data/examples/*.om` from the pinned omega-mv source | An Omega generator over the same source; the data is reviewed and re-checked regardless |
| Python 3 (`tools/check-reference.py`) | 3.12.3 | Oracle: re-derives every entry from the pinned source and runs every example with the pinned omc | Kept as an independent oracle (it must not share code with the server) |
| Python 3 (`gates/smoke.py`, `gates/trust.py`) | 3.12.3 | Oracles: an MCP stdio client session and the trust-boundary gate | Kept as independent oracles |
| `ps` (procps) | procps-ng 4.0.4 | `trust.py` checks that no sandboxed process outlives a reply | Kept as an oracle |
