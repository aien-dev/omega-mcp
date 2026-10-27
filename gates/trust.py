#!/usr/bin/env python3
"""Trust-boundary negative gate for omega-mcp (verification oracle; it is not part of the server).

It drives build/omega-mcp over MCP stdio JSON-RPC, exactly as an agent would, and sends four hostile
programs through the `run` tool:
  1 read      read a canary file under ~/.local/state and open ~/.local/state itself
  2 forkbomb  every process forks in an unbounded loop; plus a counting program (20 forks)
  3 loop      an effectively infinite loop (10^24 iterations), once against the wall clock, once against cpu
  4 write     write 10 GiB (10240 x 1 MiB) to a file in the sandbox and to stdout
Each attack must be refused or killed. Every row has a negative control run by a second server started
with --test-only-no-isolation, which must show the attack succeeding (bounded so the host stays safe:
the control never runs the unbounded fork bomb or the 10 GiB write), so a gate that cannot see the
attack fails. After every attack the gate checks that no sandboxed process outlived the reply.

  python3 gates/trust.py [--server build/omega-mcp] [--out evidence/trust-gate.json]
Exit 0 PASS, 1 FAIL. The protected paths /tmp/aien-gb10.lock, ~/.local/state/aien-q36 and
~/.local/state/aien-coordinator are never named by any program.
"""
import argparse, json, os, secrets, subprocess, sys, threading, time

HOME = os.path.expanduser("~")
STATE = os.path.join(HOME, ".local", "state")
CANDIR = os.path.join(STATE, "omega-mcp-gate")
CANARY = os.path.join(CANDIR, "canary")


def om_text(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


READ_SRC = f'''note trust gate 1: read a canary under ~/.local/state, then open ~/.local/state itself
text canary "{om_text(CANARY)}"
text sdir "{om_text(STATE)}"
global buf uchar 256
fn main to int
f = fopen canary 0 len canary 0 0
if ge f 0
r = read int f buf 0 256
if gt r 0
w = write 1 buf 0 ulong r
end
ret 10
end
d = fopen sdir 0 len sdir 0 0
if ge d 0
ret 20
end
ret 0
end
'''

BOMB_SRC = '''note trust gate 2: fork bomb; parent and every child fork in an unbounded loop
fn main to int
n = ulong 0
for i ulong 1000000000000
for j ulong 1000000000000
p = fork
if gt p 0
n = add n 1
end
end
end
ret int and n 1
end
'''

COUNT_SRC = '''note trust gate 2 (count): fork 20 children that sleep 2 s; exit status = forks that succeeded
fn main to int
n = int 0
for i ulong 20
p = fork
if eq p 0
z = sleepns 2000000000
exit 0
end
if gt p 0
n = add n 1
end
end
ret n
end
'''

LOOP_SRC = '''note trust gate 3: an effectively infinite loop (10^24 iterations)
fn main to int
x = ulong 0
for i ulong 1000000000000
for j ulong 1000000000000
x = add x 1
end
end
ret int and x 1
end
'''


def write_src(mib, to_file):
    open_line = ('f = int fopen big 0 len big 577 420\nif lt f 0\nret 3\nend\n' if to_file else 'f = int 1\n')
    return (f'note trust gate 4: write {mib} MiB in 1 MiB writes to {"a file in the working directory" if to_file else "stdout"}\n'
            'text big "big"\nglobal buf uchar 1048576\nfn main to int\n'
            'for i ulong 1048576\nput buf i 120\nend\n' + open_line +
            f'for i ulong {mib}\nw = write f buf 0 1048576\nif lt w 0\nret 4\nend\nend\nret 0\nend\n')


class Server:
    def __init__(self, path, noiso):
        args = [path] + (["--test-only-no-isolation"] if noiso else [])
        self.p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.n = 0
        self.log = []
        r = self.req("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "omega-mcp-trust-gate", "version": "1"}})
        assert r["result"]["serverInfo"]["name"] == "omega-mcp", r
        self.notify("notifications/initialized")

    def notify(self, method):
        self.p.stdin.write((json.dumps({"jsonrpc": "2.0", "method": method}) + "\n").encode())
        self.p.stdin.flush()

    def req(self, method, params):
        self.n += 1
        m = {"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}
        self.p.stdin.write((json.dumps(m) + "\n").encode())
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line:
            raise SystemExit(f"server closed stdout; stderr: {self.p.stderr.read().decode()}")
        r = json.loads(line)
        assert r.get("id") == self.n, r
        return r

    def run(self, src, timeout_ms):
        t0 = time.monotonic()
        r = self.req("tools/call", {"name": "run", "arguments": {"source": src, "timeout_ms": timeout_ms}})
        dt = time.monotonic() - t0
        sc = r["result"]["structuredContent"]
        return sc, dt

    def close(self):
        self.p.stdin.close()
        err = self.p.stderr.read().decode()
        rc = self.p.wait(30)
        return rc, err


def leftovers():
    """Processes of this user that look like a sandboxed program, its reaper or its bwrap."""
    out = subprocess.run(["ps", "-u", str(os.getuid()), "-o", "pid=,args="], capture_output=True, text=True).stdout
    bad = []
    for line in out.splitlines():
        pid, _, args = line.strip().partition(" ")
        if args == "/p" or args.startswith("/r reap") or (args.startswith("/usr/bin/bwrap --unshare-all") and "/r" in args):
            bad.append(line.strip())
    return bad


def summary(sc):
    e = sc.get("exit", {})
    return {"compile_ok": sc.get("compile", {}).get("ok"), "exit": e, "stdout": sc.get("stdout", "")[:120],
            "stdout_bytes": sc.get("stdout_bytes"), "isolation": sc.get("isolation")}


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--server", default=os.path.join(here, "..", "build", "omega-mcp"))
    ap.add_argument("--out", default=os.path.join(here, "..", "evidence", "trust-gate.json"))
    a = ap.parse_args()

    os.makedirs(CANDIR, mode=0o700, exist_ok=True)
    secret = "omega-mcp-canary-" + secrets.token_hex(8)
    with open(CANARY, "w") as f:
        f.write(secret + "\n")

    rows, fails = [], []

    def row(gate, case, mode, sc, dt, ok, want, mid_run=None):
        left = leftovers()
        if left:
            ok = False
        r = {"gate": gate, "case": case, "server": mode, "seconds": round(dt, 2), "want": want,
             "observed": summary(sc), "leftover_processes": left, "pass": ok}
        if mid_run is not None:
            r["mid_run_processes"] = mid_run
        rows.append(r)
        print(f"{'PASS' if ok else 'FAIL'} {gate:9} {case:28} {mode:7} {dt:6.2f}s exit={json.dumps(sc.get('exit'))} "
              f"stdout_bytes={sc.get('stdout_bytes')} leftovers={len(left)}", flush=True)
        if not ok:
            fails.append(f"{gate}/{case}/{mode}")

    iso = Server(a.server, False)
    ctl = Server(a.server, True)
    kind = lambda sc: sc.get("exit", {}).get("kind")

    # 1 read ~/.local/state
    sc, dt = iso.run(READ_SRC, 5000)
    row("read", "canary + state dir", "sandbox", sc, dt,
        kind(sc) == "normal" and sc["exit"].get("code") == 0 and secret not in sc.get("stdout", ""),
        "exit 0: canary and ~/.local/state both invisible, secret absent from stdout")
    sc, dt = ctl.run(READ_SRC, 5000)
    row("read", "canary + state dir (control)", "noiso", sc, dt,
        kind(sc) == "normal" and sc["exit"].get("code") == 10 and secret in sc.get("stdout", ""),
        "exit 10 and the secret on stdout (the gate sees a leak)")

    # 2 fork bomb. Sampled mid-run, leftovers() must see the sandbox (control for the leftover check)
    # and the bomb processes (/p) must stay within nproc 5.
    box = {}
    th = threading.Thread(target=lambda: box.update(r=iso.run(BOMB_SRC, 3000)))
    th.start()
    time.sleep(1.5)
    mid = leftovers()
    th.join()
    sc, dt = box["r"]
    nbomb = sum(1 for m in mid if m.split(" ", 1)[1] == "/p")
    row("forkbomb", "unbounded bomb", "sandbox", sc, dt,
        kind(sc) in ("limit", "signal") and dt < 15 and 1 <= nbomb <= 5,
        "stopped by a limit or the wall clock within 15 s; mid-run 1..5 bomb processes seen; none left",
        mid_run=mid)
    sc, dt = iso.run(COUNT_SRC, 10000)
    n_iso = sc.get("exit", {}).get("code")
    row("forkbomb", "count 20 forks", "sandbox", sc, dt,
        kind(sc) == "normal" and isinstance(n_iso, int) and n_iso <= 5,
        "at most 5 forks succeed (nproc 5)")
    sc, dt = ctl.run(COUNT_SRC, 10000)
    row("forkbomb", "count 20 forks (control)", "noiso", sc, dt,
        kind(sc) == "normal" and sc["exit"].get("code") == 20,
        "all 20 forks succeed without the limit")
    time.sleep(2.5)

    # 3 infinite loop
    sc, dt = iso.run(LOOP_SRC, 2000)
    row("loop", "wall clock 2 s", "sandbox", sc, dt,
        kind(sc) == "limit" and sc["exit"].get("limit") == "wall_clock" and dt < 6,
        "killed at the 2 s wall clock")
    sc, dt = iso.run(LOOP_SRC, 30000)
    row("loop", "cpu limit (wall 30 s)", "sandbox", sc, dt,
        kind(sc) == "limit" and sc["exit"].get("limit") == "cpu_time" and dt < 20,
        "killed by RLIMIT_CPU (10 s) before the 30 s wall clock")
    sc, dt = ctl.run(LOOP_SRC, 30000)
    row("loop", "cpu limit (control)", "noiso", sc, dt,
        kind(sc) == "limit" and sc["exit"].get("limit") == "wall_clock" and dt >= 29,
        "without prlimit only the 30 s wall clock stops it")

    # 4 10 GiB write
    sc, dt = iso.run(write_src(10240, True), 30000)
    row("write", "10 GiB to a file", "sandbox", sc, dt,
        kind(sc) == "limit" and sc["exit"].get("limit") == "file_size",
        "SIGXFSZ at the 1 MiB file-size limit")
    sc, dt = iso.run(write_src(10240, False), 30000)
    row("write", "10 GiB to stdout", "sandbox", sc, dt,
        kind(sc) == "limit" and sc["exit"].get("limit") == "file_size" and (sc.get("stdout_bytes") or 0) <= 1048576,
        "SIGXFSZ; at most 1 MiB reached the host capture file")
    sc, dt = ctl.run(write_src(8, False), 30000)
    row("write", "8 MiB to stdout (control)", "noiso", sc, dt,
        kind(sc) == "normal" and sc["exit"].get("code") == 0 and sc.get("stdout_bytes") == 8388608,
        "without the limit all 8 MiB are written")

    rc1, err1 = iso.close()
    rc2, err2 = ctl.close()
    os.remove(CANARY)
    os.rmdir(CANDIR)
    res = {"server": os.path.abspath(a.server), "rows": rows, "fails": fails,
           "server_exit": [rc1, rc2], "server_stderr": {"sandbox": err1, "noiso": err2},
           "verdict": "PASS" if not fails else "FAIL"}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1)
        f.write("\n")
    print(res["verdict"], f"{len(rows) - len(fails)}/{len(rows)} rows")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
