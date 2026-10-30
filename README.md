# omega-mcp   

[![Omega MCP on mcprush](https://mcprush.com/badge/omega-mcp/score.svg)](https://mcprush.com/to/omega-mcp?ref=badge)

An MCP server, written in Omega, that lets an agent compile and run Omega (`.om`) programs with the
pinned seeded compiler and look up the language. It speaks MCP (protocol version `2025-06-18`) as
newline-delimited JSON-RPC 2.0 over stdio.

Pin: omega-mv `e5b32567a7aff3ce594e3254a622a846a6cd190b`, omc sha256
`2c82480596bbdc50cda9626866209ef662d5834f278f839ff4ce0250c495029f`. `build.sh` refuses any other
compiler, and the server checks the sha256 of its compiler again at start-up.

## Tools

| Tool | Arguments | Result |
|---|---|---|
| `compile` | `source` | `ok`, binary size and sha256, or the compile error `{line, code, meaning, fix}` |
| `run` | `source`, `stdin`, `timeout_ms` (1..30000, default 5000) | compile result, capped stdout/stderr, and the exit: `normal`, `trap` (with its meaning), or the `limit` that stopped it (`cpu_time`, `file_size`, `wall_clock`, `killed`) |
| `explain_error` | `query`: an error code 1..30, an `omc: line N: error K` line, `trap T`, or an exit status 101..114 | meaning, cause, fix, a minimal example and citations into omega-mv@e5b32567 |
| `lookup` | `query`: a keyword or topic, or a substring | the entry (form, arity, types, result, example, citations), or up to 20 search hits |

A compile diagnostic is a successful tool result (`isError: false`); `isError` is true when nothing
could be run (sandbox failure, a refused compile stage) or when explain/lookup found no entry. Bad
arguments are JSON-RPC errors (`-32602`).

## Isolation

Each `compile` and `run` stage gets a fresh `/tmp/omega-mcp-<16 hex>` directory (mode 0700, removed
after the reply) and runs under `bwrap --unshare-all --clearenv`. The sandbox sees only the compiler
or the program (read-only), its in-sandbox reaper and a 16 MiB tmpfs working directory: no network,
no host files, an empty environment. `prlimit` applies the resource limits to the sandbox before it
starts, and the server kills the whole sandbox at the wall clock.

| Stage | CPU | Address space | File size | Processes | Wall clock |
|---|---|---|---|---|---|
| run | 10 s | 256 MiB | 1 MiB | 5 | `timeout_ms` (default 5 s, max 30 s) |
| compile | 20 s | 512 MiB | 16 MiB | 4 | 20 s |

Both stages also get 64 open files and no core dumps. `--test-only-no-isolation` turns all of this
off and exists only so the trust gate can prove it detects an escape; never give it to an agent.

## Build and use

```sh
OMEGA_SRC=/path/to/omega-mv ./build.sh      # omega-mv checkout at e5b32567 with seed/out/omc built
build/omega-mcp                              # reads JSON-RPC on stdin; logs one line per request on stderr
```

The server loads `data/reference.json` and `data/examples/` from beside its executable. Start-up
exit codes: 2 bad arguments, 3 compiler not the pin, 4 data missing, 5 `bwrap`/`prlimit` missing.
`mcp.json` is an example client configuration; point its `command` at your `build/omega-mcp`.

## Gates

```sh
python3 gates/smoke.py      # MCP client session; transcript in evidence/smoke-transcript.jsonl
python3 gates/trust.py      # trust boundary: 4 attacks plus negative controls; evidence/trust-gate.json
python3 tools/check-reference.py --omega-src $OMEGA_SRC --omc $OMEGA_SRC/seed/out/omc --self-test
```

`trust.py` sends, through the `run` tool, a read of a canary under `~/.local/state`, a fork bomb, an
infinite loop and a 10 GiB write, and requires each to be refused or killed with no process left
behind. A second server started with `--test-only-no-isolation` runs bounded versions of the same
attacks and must see them succeed, so a gate that cannot see an escape fails. `check-reference.py`
re-derives every keyword, error and trap entry from the pinned source, compiles and runs every example
with the pinned omc, and runs three negative controls.

These gates are host evidence on Linux arm64 (bubblewrap 0.9.0, util-linux 2.39.3); they say nothing
about other kernels or about a sandbox configuration other than the one in `src/sandbox.om`.

## Layout

- `src/*.om`: the server (`src/UNITS` lists the concatenation order; `build.sh` builds it)
- `vendor/omega-mv/`: sha256 and JSON units copied unchanged from omega-mv@e5b32567
- `data/`: reference data and example programs, written by `tools/gen-reference.py` and checked by
  `tools/check-reference.py`
- `gates/`, `evidence/`: verification oracles and their recorded results
- `DEPENDENCIES.md`: every host tool in the build, runtime and verification paths

License: Apache-2.0 (see `LICENSE` and `NOTICE`).

<!-- mcp-name: io.github.aien-dev/omega-mcp -->

## Human-Directed Agentic Engineering

Development follows Human-Directed Agentic Engineering (HDAE): humans define goals,
architecture, constraints, acceptance criteria, and stopping points; agents implement,
execute checks, diagnose failures, and revise within those boundaries. Human review
retains responsibility for claims, acceptance, and release decisions. This describes
the development method, not a change to runtime autonomy or historical evidence.

For the documented method and a systems-software case study, see Gregory M. Kurtzer
(2026), *Ginux: Building an Independent Kernel That Runs Linux Userspace through
Human-Directed Agentic Engineering*, technical report, v1, Zenodo,
<https://doi.org/10.5281/zenodo.23682548>.
