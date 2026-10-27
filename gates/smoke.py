#!/usr/bin/env python3
"""Stdio smoke test for omega-mcp (verification oracle; a minimal MCP client, not part of the server).

Starts build/omega-mcp, speaks newline-delimited JSON-RPC 2.0 over its stdin/stdout the way an MCP
client does, and records every line in both directions:
  initialize -> notifications/initialized -> tools/list -> tools/call compile hello.om ->
  tools/call run hello.om -> run (trap) -> compile (error 3) -> explain_error -> lookup,
plus protocol negatives (unknown method, unparseable line, unknown argument, unknown tool).

  python3 gates/smoke.py [--server build/omega-mcp] [--out evidence/smoke-transcript.jsonl]
Exit 0 PASS, 1 FAIL.
"""
import argparse, json, os, subprocess, sys

HELLO = 'text msg "hello\\n"\nfn main to int\nw = write 1 msg 0 len msg\nret 0\nend\n'
DIV0 = 'fn main to int\nz = int 0\nret div 7 z\nend\n'
BADNAME = 'fn main to int\nret x\nend\n'


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default=os.path.join(here, "..", "build", "omega-mcp"))
    ap.add_argument("--out", default=os.path.join(here, "..", "evidence", "smoke-transcript.jsonl"))
    a = ap.parse_args()
    p = subprocess.Popen([a.server], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log, fails = [], []

    def send(raw):
        log.append({"dir": "client->server", "line": raw})
        p.stdin.write((raw + "\n").encode())
        p.stdin.flush()

    def recv():
        line = p.stdout.readline().decode().rstrip("\n")
        log.append({"dir": "server->client", "line": line})
        return json.loads(line)

    def call(i, method, params=None):
        m = {"jsonrpc": "2.0", "id": i, "method": method}
        if params is not None:
            m["params"] = params
        send(json.dumps(m))
        r = recv()
        if r.get("id") != i or r.get("jsonrpc") != "2.0":
            fails.append(f"id {i}: bad envelope {r}")
        return r

    def check(name, ok):
        print(("PASS " if ok else "FAIL ") + name, flush=True)
        if not ok:
            fails.append(name)

    tool = lambda i, n, args: call(i, "tools/call", {"name": n, "arguments": args})

    r = call(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "omega-mcp-smoke", "version": "1"}})
    res = r.get("result", {})
    check("initialize: protocolVersion 2025-06-18, serverInfo omega-mcp, tools capability",
          res.get("protocolVersion") == "2025-06-18" and res.get("serverInfo", {}).get("name") == "omega-mcp"
          and "tools" in res.get("capabilities", {}))
    send(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    r = call(2, "tools/list", {})
    names = [t["name"] for t in r.get("result", {}).get("tools", [])]
    check("tools/list: compile, run, explain_error, lookup", names == ["compile", "run", "explain_error", "lookup"])

    sc = tool(3, "compile", {"source": HELLO})["result"]["structuredContent"]
    check("compile hello.om: ok, pinned compiler",
          sc.get("ok") is True and sc.get("compiler_sha256") == "2c82480596bbdc50cda9626866209ef662d5834f278f839ff4ce0250c495029f")

    r = tool(4, "run", {"source": HELLO})["result"]
    sc = r["structuredContent"]
    check("run hello.om: stdout 'hello\\n', exit normal 0, isError false",
          sc.get("stdout") == "hello\n" and sc.get("exit") == {"kind": "normal", "code": 0} and r.get("isError") is False)

    sc = tool(5, "run", {"source": DIV0})["result"]["structuredContent"]
    check("run div0: trap 2, exit 102", sc.get("exit", {}).get("kind") == "trap" and sc["exit"].get("trap") == 2
          and sc["exit"].get("exit_code") == 102)

    r = tool(6, "compile", {"source": BADNAME})["result"]
    sc = r["structuredContent"]
    check("compile unknown name: error 3 line 2 (a diagnostic is a tool result: isError false)",
          sc.get("ok") is False and sc.get("error", {}).get("code") == 3 and sc["error"].get("line") == 2
          and r.get("isError") is False)

    sc = tool(7, "explain_error", {"query": "omc: line 2: error 3"})["result"]["structuredContent"]
    check("explain_error 'omc: line 2: error 3': compile_error 3 with citations",
          sc.get("kind") == "compile_error" and sc.get("code") == 3 and len(sc.get("citations", [])) > 0)

    sc = tool(8, "lookup", {"query": "while"})["result"]["structuredContent"]
    check("lookup while: exact keyword", sc.get("match") == "keyword" and sc.get("name") == "while")

    r = call(9, "no/such/method", {})
    check("unknown method: -32601", r.get("error", {}).get("code") == -32601)
    send("not json{")
    r = recv()
    check("unparseable line: -32700, id null", r.get("error", {}).get("code") == -32700 and r.get("id") is None)
    r = tool(10, "lookup", {"word": "while"})
    check("unknown argument: -32602", r.get("error", {}).get("code") == -32602)
    r = tool(11, "format_disk", {})
    check("unknown tool: -32602", r.get("error", {}).get("code") == -32602)

    p.stdin.close()
    extra = p.stdout.read().decode()
    err = p.stderr.read().decode()
    rc = p.wait(30)
    check("no reply to the notification and clean exit 0 at end of input", extra == "" and rc == 0)
    log.append({"dir": "server stderr", "line": err})
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        for e in log:
            f.write(json.dumps(e) + "\n")
    print("PASS" if not fails else "FAIL", f"transcript {a.out}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
