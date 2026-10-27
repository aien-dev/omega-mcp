#!/usr/bin/env python3
"""Oracle for data/reference.json and data/examples/*.om (a verification tool, not part of the server).

Checks, against omega-mv at the pinned commit (read with `git show PIN:path`, never the worktree):
  1. the keyword set equals the compiler's keyword table (fn kw + fn kw2 in seed/omc/omc.om),
     re-derived here from the source, with the same keyword id and source line;
  2. every citation `omega-mv@<pin8> path:A[-B]` names lines A..B whose text contains its quote;
  3. every word, error and trap entry has the required members; every word's example contains the word;
  4. every example compiles with the pinned omc and meets its expectation (run in a bwrap sandbox);
  5. the compiler I/O errors 1 and 2 reproduce as described.
--self-test also runs three negative controls (a moved citation, a wrong example expectation, a missing
keyword) and requires each to be detected.
Exit 0 when every check passes; 1 with the failures listed otherwise.
"""
import argparse, copy, hashlib, json, os, re, subprocess, sys, tempfile

PIN = "e5b32567a7aff3ce594e3254a622a846a6cd190b"
OMC_SHA = "2c82480596bbdc50cda9626866209ef662d5834f278f839ff4ce0250c495029f"
REF_RE = re.compile(r"^omega-mv@" + PIN[:8] + r" ([A-Za-z0-9_./-]+):(\d+)(?:-(\d+))?$")
WORD_KEYS = ["table", "id", "category", "profile", "form", "arity", "types", "result", "summary", "citations", "example"]
ENTRY_KEYS = ["meaning", "cause", "fix", "citations"]


class Src:
    def __init__(self, repo):
        self.repo, self.cache = repo, {}

    def lines(self, path):
        if path not in self.cache:
            out = subprocess.run(["git", "-C", self.repo, "show", PIN + ":" + path], capture_output=True, check=True)
            self.cache[path] = out.stdout.decode().split("\n")
        return self.cache[path]


def kwtable(src):
    """(word, id, line, table) for every entry of fn kw / fn kw2, decoded like omc's packed words."""
    L = src.lines("seed/omc/omc.om")
    start = L.index("fn kw w ulong to ulong")
    out, packed, w, line, table = [], None, None, None, "kw"
    for i in range(start, len(L)):
        s = L[i]
        if s.startswith("fn kw2 "):
            table = "kw2"
        if s.startswith("fn ") and not s.startswith("fn kw"):
            break
        m = re.match(r"packed = or ulong (\d+) shl ulong (\d+) 8$", s)
        if m:
            packed = int(m[1]) | int(m[2]) << 8
            continue
        m = re.match(r"packed = or packed shl ulong (\d+) (\d+)$", s)
        if m:
            packed |= int(m[1]) << int(m[2])
            continue
        m = re.match(r"if eq w (\d+)$", s)
        if m:
            w, line = int(m[1]), i + 1
            continue
        if s == "if eq w packed":
            w, line = packed, i + 1
            continue
        m = re.match(r"ret (\d+)$", s)
        if m and w is not None:
            out.append((w.to_bytes(8, "little").rstrip(b"\0").decode(), int(m[1]), line, table))
            w = None
    return out


def norm(s):
    return " ".join(s.split())


def check_cites(src, where, cites, errs):
    if not isinstance(cites, list) or not cites:
        errs.append(f"{where}: no citations")
        return
    for c in cites:
        m = REF_RE.match(c.get("ref", ""))
        if not m:
            errs.append(f"{where}: bad citation ref {c.get('ref')!r}")
            continue
        path, a = m[1], int(m[2])
        b = int(m[3]) if m[3] else a
        try:
            L = src.lines(path)
        except subprocess.CalledProcessError:
            errs.append(f"{where}: {path} does not exist at the pin")
            continue
        if not (1 <= a <= b <= len(L)):
            errs.append(f"{where}: {path}:{a}-{b} outside the file ({len(L)} lines)")
            continue
        if norm(c.get("quote", "")) == "" or norm(c["quote"]) not in norm(" ".join(L[a - 1:b])):
            errs.append(f"{where}: {path}:{a}-{b} does not contain {c.get('quote')!r}")


def tokens(text):
    return set(re.sub(r"([()])", r" \1 ", text).split())


def sandbox_run(binary, timeout):
    cmd = ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
           "--ro-bind", binary, "/p", "--tmpfs", "/w", "--chdir", "/w", "/p"]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout
    except subprocess.TimeoutExpired:
        return "timeout", b""


def check_example(omc, eid, source, exp, errs, tmp):
    where = f"example {eid}"
    p = os.path.join(tmp, eid)
    r = subprocess.run([omc], input=source.encode(), capture_output=True, timeout=60)
    mode = exp.get("mode")
    if mode == "error":
        want = f"omc: line {exp['line']}: error {exp['code']}\n".encode()
        if r.returncode != exp["code"] or not r.stderr.startswith(want):
            errs.append(f"{where}: wanted error {exp['code']} line {exp['line']}, got rc {r.returncode} {r.stderr[:80]!r}")
        return
    if r.returncode != 0:
        errs.append(f"{where}: compile failed rc {r.returncode} {r.stderr[:80]!r}")
        return
    if mode == "compile":
        return
    with open(p, "wb") as f:
        f.write(r.stdout)
    os.chmod(p, 0o700)
    rc, out = sandbox_run(p, 20)
    if mode == "trap":
        if rc != 100 + exp["trap"]:
            errs.append(f"{where}: wanted trap {exp['trap']} (exit {100 + exp['trap']}), got {rc}")
    elif mode == "run":
        if rc != exp["exit"]:
            errs.append(f"{where}: wanted exit {exp['exit']}, got {rc} stdout {out[:60]!r}")
        if "stdout" in exp and out.decode("utf-8", "replace") != exp["stdout"]:
            errs.append(f"{where}: wanted stdout {exp['stdout']!r}, got {out[:80]!r}")
    else:
        errs.append(f"{where}: unknown mode {mode!r}")


def check(ref, exdir, src, omc, run_examples=True):
    errs = []
    table = kwtable(src)
    if len(table) != 177:
        errs.append(f"keyword table has {len(table)} entries, expected 177 at the pin")
    words = ref.get("words", {})
    want = {w: (i, line, t) for w, i, line, t in table}
    for w in sorted(set(want) - set(words)):
        errs.append(f"keyword {w!r} has no lookup entry")
    for w in sorted(set(words) - set(want)):
        errs.append(f"lookup entry {w!r} is not a compiler keyword")
    examples = ref.get("examples", {})
    for w, e in words.items():
        for k in WORD_KEYS:
            if k not in e:
                errs.append(f"word {w}: missing {k}")
        if w in want:
            i, line, t = want[w]
            if e.get("id") != i or e.get("table") != t:
                errs.append(f"word {w}: id/table {e.get('id')}/{e.get('table')} != {i}/{t}")
            first = (e.get("citations") or [{}])[0].get("ref", "")
            if first != f"omega-mv@{PIN[:8]} seed/omc/omc.om:{line}-{line + 1}":
                errs.append(f"word {w}: first citation {first!r} is not its keyword-table line {line}")
        check_cites(src, f"word {w}", e.get("citations"), errs)
        ex = e.get("example")
        if ex not in examples:
            errs.append(f"word {w}: example {ex!r} missing")
        elif os.path.exists(os.path.join(exdir, ex + ".om")):
            if w not in tokens(open(os.path.join(exdir, ex + ".om")).read()):
                errs.append(f"word {w}: example {ex} does not use the word")
    for sect, lo, hi, holes in (("errors", 1, 30, {25, 26}), ("traps", 1, 14, set())):
        d = ref.get(sect, {})
        keys = {str(k) for k in range(lo, hi + 1) if k not in holes}
        if set(d) != keys:
            errs.append(f"{sect}: keys {sorted(set(d) ^ keys)} differ")
        for k, e in d.items():
            for m in ENTRY_KEYS:
                if not e.get(m):
                    errs.append(f"{sect} {k}: missing {m}")
            check_cites(src, f"{sect} {k}", e.get("citations"), errs)
            ex = e.get("example")
            if ex is None:
                if not e.get("reproduce") and not e.get("example_note"):
                    errs.append(f"{sect} {k}: neither example, reproduce nor example_note")
                continue
            exp = examples.get(ex)
            if exp is None:
                errs.append(f"{sect} {k}: example {ex!r} missing")
            elif sect == "errors" and (exp.get("mode") != "error" or exp.get("code") != int(k)):
                errs.append(f"errors {k}: example {ex} expects {exp}")
            elif sect == "traps" and (exp.get("mode") != "trap" or exp.get("trap") != int(k)):
                errs.append(f"traps {k}: example {ex} expects {exp}")
    for t, e in ref.get("topics", {}).items():
        check_cites(src, f"topic {t}", e.get("citations"), errs)
        if "summary" not in e:
            errs.append(f"topic {t}: missing summary")
        if e.get("example") is not None and e["example"] not in examples:
            errs.append(f"topic {t}: example {e['example']!r} missing")
    files = {f[:-3] for f in os.listdir(exdir) if f.endswith(".om")}
    if files != set(examples):
        errs.append(f"example files and expectations differ: {sorted(files ^ set(examples))}")
    for eid in examples:
        if not re.fullmatch(r"[a-z0-9_]{1,63}", eid):
            errs.append(f"example id {eid!r} is not [a-z0-9_]{{1,63}}")
    if run_examples:
        with tempfile.TemporaryDirectory() as tmp:
            for eid in sorted(set(examples) & files):
                check_example(omc, eid, open(os.path.join(exdir, eid + ".om")).read(), examples[eid], errs, tmp)
            for k in ("1", "2"):
                rep = ref.get("errors", {}).get(k, {}).get("reproduce")
                if rep:
                    errs += check_reproduce(omc, int(k), tmp)
    return errs


def check_reproduce(omc, code, tmp):
    """error 1: stdin is a directory (read fails); error 2: stdout is /dev/full (write fails)."""
    if code == 1:
        d = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            r = subprocess.run([omc], stdin=d, capture_output=True)
        finally:
            os.close(d)
    else:
        p = os.path.join(tmp, "ok.om")
        open(p, "w").write("fn main to int\nret 0\nend\n")
        with open(p, "rb") as i, open("/dev/full", "wb") as o:
            r = subprocess.run([omc], stdin=i, stdout=o, stderr=subprocess.PIPE)
    if r.returncode != code or f"error {code}\n".encode() not in r.stderr:
        return [f"errors {code}: reproduce gave rc {r.returncode} {r.stderr!r}"]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--omega-src", required=True, help="a git clone of aien-dev/omega-mv containing the pin")
    ap.add_argument("--omc", required=True, help="the pinned omc binary")
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    ap.add_argument("--self-test", action="store_true", help="also run the negative controls")
    a = ap.parse_args()
    if hashlib.sha256(open(a.omc, "rb").read()).hexdigest() != OMC_SHA:
        print("FAIL omc is not the pinned binary")
        return 1
    src = Src(a.omega_src)
    raw = open(os.path.join(a.data, "reference.json"), "rb").read()
    ref = json.loads(raw)
    exdir = os.path.join(a.data, "examples")
    errs = check(ref, exdir, src, a.omc)
    if len(raw) > 393216:
        errs.append(f"reference.json is {len(raw)} bytes, over the server's 393216")
    for e in errs:
        print("FAIL", e)
    nw, ne = len(ref["words"]), len(ref["examples"])
    print(f"words {nw} errors {len(ref['errors'])} traps {len(ref['traps'])} topics {len(ref['topics'])} "
          f"examples {ne} bytes {len(raw)} failures {len(errs)}")
    rc = 1 if errs else 0
    if a.self_test:
        rc |= self_test(ref, exdir, src, a.omc)
    print("PASS" if rc == 0 else "FAIL")
    return rc


def self_test(ref, exdir, src, omc):
    rc = 0
    m1 = copy.deepcopy(ref)
    c = m1["words"]["add"]["citations"][0]
    c["ref"] = c["ref"].replace(":970-971", ":973-974")
    m2 = copy.deepcopy(ref)
    m2["examples"]["hello"]["exit"] = m2["examples"]["hello"]["exit"] + 1
    m3 = copy.deepcopy(ref)
    del m3["words"]["mapbind"]
    for name, mut, run in (("moved citation", m1, False), ("wrong expectation", m2, True), ("missing keyword", m3, False)):
        if run:
            m = copy.deepcopy(mut)
            m["examples"] = {"hello": mut["examples"]["hello"]}
            errs = []
            with tempfile.TemporaryDirectory() as tmp:
                check_example(omc, "hello", open(os.path.join(exdir, "hello.om")).read(), m["examples"]["hello"], errs, tmp)
        else:
            errs = check(mut, exdir, src, omc, run_examples=False)
        ok = bool(errs)
        print(f"negative control ({name}): {'DETECTED' if ok else 'MISSED'}: {errs[:1]}")
        rc |= 0 if ok else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
