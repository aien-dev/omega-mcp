#!/usr/bin/env python3
"""Data-authoring generator (host tool, not part of the server): writes data/reference.json and
data/examples/*.om. Keyword ids, arities and citation lines come from the pinned omega-mv source through
the same decoder the oracle uses (tools/check-reference.py); tools/check-reference.py then re-verifies
every committed entry against that source and the pinned omc.

  python3 tools/gen-reference.py --omega-src <omega-mv checkout at e5b32567>
"""
import argparse, importlib.util, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ref_examples import EX

_ap = argparse.ArgumentParser()
_ap.add_argument("--omega-src", required=True)
_args = _ap.parse_args()
_s = importlib.util.spec_from_file_location("checkref", os.path.join(HERE, "check-reference.py"))
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)


def kwtable():
    return _m.kwtable(_m.Src(_args.omega_src))


OUT = os.path.join(HERE, "..", "data")
P = "omega-mv@e5b32567 "
OMG = "docs/one_layer/OMEGESE.md"
OMC = "seed/omc/omc.om"
MAP = "seed/host/MAPPING.md"
IRH = "src/compiler/osc_ir.h"


def c(path, lines, quote):
    return {"ref": f"{P}{path}:{lines}", "quote": quote}


TAB = {w: (i, line, t) for w, i, line, t in kwtable()}

# ---------------------------------------------------------------- words
W = {}


def word(name, cat, form, arity, types, result, summary, cites, example, profile="OM-1", notes=None):
    i, line, t = TAB[name]
    e = {"table": t, "id": i, "category": cat, "profile": profile, "form": form, "arity": arity,
         "types": types, "result": result, "summary": summary,
         "citations": [c(OMC, f"{line}-{line + 1}", f"ret {i}")] + cites, "example": example}
    if notes:
        e["notes"] = notes
    W[name] = e


INT_P = {"fd", "flags", "mode", "pid", "signal", "events", "domain", "kind", "protocol", "backlog", "target",
         "options", "level", "option", "whence", "op", "how", "mask", "pgid", "uid", "gid", "index_i"}
ULONG_P = {"off", "n", "capacity", "index"}
LONG_P = {"offset", "length", "interval", "pos"}


def host_types(params):
    out = []
    for p in params:
        if p in ("A", "B", "PATH", "OUT"):
            out.append(f"{p}: uchar array (sized, unsized view/edit, or text when only read)")
        elif p in INT_P:
            out.append(f"{p}: int")
        elif p in ULONG_P:
            out.append(f"{p}: ulong")
        elif p in LONG_P:
            out.append(f"{p}: long")
        else:
            raise SystemExit(f"untyped host parameter {p}")
    return out


HOST_HDR = c(OMG, "780-786", "Offsets, byte counts, capacities and argument indices are `ulong`")
HOST = [
    # name, OMEGESE line, form (as in the table), category, summary, example
    ("fopen", 790, "fopen A off n flags mode", "host-file", "Open a length-delimited path relative to the current directory; return the descriptor.", "files"),
    ("fclose", 791, "fclose fd", "host-file", "Close a descriptor.", "files"),
    ("fsync", 792, "fsync fd", "host-file", "Sync file data and metadata.", "files"),
    ("fdsync", 793, "fdsync fd", "host-file", "Sync file data only (fdatasync).", "files"),
    ("memfd", 794, "memfd A off n flags", "host-file", "Create an anonymous in-memory file (memfd_create); return its descriptor.", "files"),
    ("fchmod", 795, "fchmod fd mode", "host-file", "Set permissions on an open descriptor.", "files"),
    ("chmod", 796, "chmod A off n mode", "host-file", "Set permissions on a checked path (fchmodat, flags 0).", "files"),
    ("chown", 797, "chown A off n uid gid", "host-dir", "Set ownership on a checked path (fchownat, flags 0).", "dirs"),
    ("faccess", 798, "faccess A off n mode", "host-file", "Check access to a checked path (faccessat): mode 0/1/2/4.", "files"),
    ("getuid", 799, "getuid", "host-process", "Real user id of the process.", "dirs"),
    ("geteuid", 799, "geteuid", "host-process", "Effective user id of the process.", "dirs"),
    ("getgid", 799, "getgid", "host-process", "Real group id of the process.", "dirs"),
    ("getegid", 799, "getegid", "host-process", "Effective group id of the process.", "dirs"),
    ("fchdir", 800, "fchdir fd", "host-dir", "Change the working directory to an open directory descriptor.", "dirs"),
    ("getppid", 801, "getppid", "host-process", "Parent process id.", "procs"),
    ("setsid", 802, "setsid", "host-process", "Create a session and become its leader.", "procs"),
    ("getpgid", 803, "getpgid pid", "host-process", "Process group id of pid (0 = self).", "procs"),
    ("getsid", 804, "getsid pid", "host-process", "Session id of pid (0 = self).", "procs"),
    ("syncfs", 805, "syncfs fd", "host-file", "Sync the filesystem containing an open descriptor.", "files"),
    ("shutdown", 806, "shutdown fd how", "host-net", "Shut down part of a connected socket (how 0 read, 1 write, 2 both).", "sockets"),
    ("flock", 807, "flock fd op", "host-file", "Advisory whole-file lock (Linux flock); op 1 shared, 2 exclusive, 8 unlock, |4 nonblocking.", "files"),
    ("setpgid", 808, "setpgid pid pgid", "host-process", "Set a process's group (0 = self/own pid).", "procs"),
    ("umask", 809, "umask mask", "host-file", "Set the file-mode mask; return the previous mask.", "files"),
    ("fseek", 810, "fseek fd offset whence", "host-file", "Seek; return the resulting file offset.", "files"),
    ("ftrunc", 811, "ftrunc fd length", "host-file", "Set an open descriptor's length (ftruncate).", "files"),
    ("truncate", 812, "truncate A off n length", "host-file", "Set a checked path's length (truncate).", "files"),
    ("unlink", 813, "unlink A off n", "host-file", "Remove the named file.", "files"),
    ("makedir", 814, "makedir A off n mode", "host-dir", "Create a directory.", "dirs"),
    ("rmdir", 815, "rmdir A off n", "host-dir", "Remove an empty directory.", "dirs"),
    ("cwd", 816, "cwd A off capacity", "host-dir", "Write the current directory into writable bytes; the count includes the trailing zero.", "dirs"),
    ("chdir", 817, "chdir A off n", "host-dir", "Change the working directory to a checked, nonempty path.", "dirs"),
    ("readlnk", 818, "readlnk PATH off n OUT off capacity", "host-dir", "Read a symbolic link into writable output bytes; no zero byte is appended.", "dirs"),
    ("getdnts", 819, "getdnts fd A off n", "host-dir", "Write raw Linux getdents64 records; return bytes written.", "dirs"),
    ("fstat", 820, "fstat fd A off n", "host-file", "Write the 128-byte Linux ARM64 stat structure of an open descriptor.", "files"),
    ("stat", 821, "stat A off n B off capacity", "host-file", "Metadata for a checked path (newfstatat) into a 128-byte ARM64 stat structure.", "files"),
    ("lstat", 822, "lstat A off n B off capacity", "host-file", "As stat, without following a final symbolic link.", "files"),
    ("renames", 823, "renames A off n flags", "host-dir", "Rename the two paths of a packed list (renameat2); flag 1 refuses replacement.", "dirs"),
    ("link", 824, "link A off n", "host-dir", "Create a hard link from a packed two-path list (old, new).", "dirs"),
    ("symlnk", 825, "symlnk A off n", "host-dir", "Create a symbolic link from a packed two-path list (target text, link path).", "dirs"),
    ("monons", 826, "monons", "host-time", "Monotonic nanoseconds, for elapsed-time measurement.", "clock"),
    ("realns", 827, "realns", "host-time", "Realtime nanoseconds since the Unix epoch.", "clock"),
    ("sleepns", 828, "sleepns interval", "host-time", "Sleep for nonnegative nanoseconds; a negative interval traps 3.", "clock"),
    ("socknew", 829, "socknew domain kind protocol", "host-net", "Create a socket.", "sockets"),
    ("bind", 830, "bind fd A off n", "host-net", "Bind a socket to the address bytes of the slice.", "sockets"),
    ("connect", 831, "connect fd A off n", "host-net", "Connect using the address bytes of the slice.", "sockets"),
    ("listen", 832, "listen fd backlog", "host-net", "Listen for connections.", "sockets"),
    ("accept", 833, "accept fd flags", "host-net", "Accept a connection (accept4) without peer-address output; return the descriptor.", "sockets"),
    ("sockname", 834, "sockname fd A off n", "host-net", "Write the socket's address bytes; return the full address length.", "sockets"),
    ("sockopt", 835, "sockopt fd level option A off n", "host-net", "Set one allowlisted four-byte socket option.", "sockets"),
    ("recv", 836, "recv fd A off n flags", "host-net", "Receive into a writable slice.", "sockets"),
    ("send", 837, "send fd A off n flags", "host-net", "Send a slice; MSG_NOSIGNAL is added so a closed peer returns an error.", "sockets"),
    ("waitio", 838, "waitio fd events interval", "host-net", "Poll one descriptor: readiness bits, 0 on timeout, or negative errno.", "sockets"),
    ("peercred", 839, "peercred fd A off capacity", "host-net", "Read SO_PEERCRED (pid, uid, gid as little-endian int32) into at least 12 writable bytes.", "sockets"),
    ("pollfds", 840, "pollfds A off n interval", "host-net", "Poll packed eight-byte pollfd records in a writable slice.", "sockets"),
    ("sendmsg", 841, "sendmsg fd A off n flags", "host-net", "Send one checked payload through a private msghdr, no ancillary data.", "sockets"),
    ("fork", 842, "fork", "host-process", "Copy the process: 0 in the child, the child pid in the parent.", "procs"),
    ("getpid", 843, "getpid", "host-process", "The current process id.", "procs"),
    ("killpid", 844, "killpid pid signal", "host-process", "Send a signal; signal 0 checks existence and permission.", "procs"),
    ("waitpid", 845, "waitpid pid A off n options", "host-process", "Wait with wait4; write a four-byte status; return the pid.", "procs"),
    ("pipefds", 846, "pipefds A off n flags", "host-process", "Create a pipe (pipe2); write two little-endian 32-bit descriptors.", "procs"),
    ("dupfd", 847, "dupfd fd target flags", "host-process", "Duplicate onto a chosen descriptor (dup3).", "procs"),
    ("execprog", 848, "execprog A off n", "host-process", "Replace the process using a packed argument list and an empty environment; returns only on failure.", "procs"),
    ("argcnt", 849, "argcnt", "host-process", "Argument count, including the executable name.", "argsenv"),
    ("argread", 850, "argread index A off capacity", "host-process", "Copy one argument's bytes without a terminator; return its length.", "argsenv"),
    ("envcnt", 851, "envcnt", "host-process", "Number of environment entries.", "argsenv"),
    ("envread", 852, "envread index A off capacity", "host-process", "Copy one environment entry without its terminator; return its length.", "argsenv"),
    ("random", 853, "random A off n flags", "host-time", "Fill a writable byte slice from getrandom; return the bytes written.", "clock"),
]
for name, line, form, cat, summ, exid in HOST:
    params = form.split()[1:]
    quote = f"`{form}`" if name not in ("getuid", "geteuid", "getgid", "getegid") else f"`{name}`"
    notes = None
    if name == "argread" or name == "envread":
        params = ["index"] + params[1:]
    if name == "pwrite":
        pass
    word(name, cat, form, len(params), host_types(params), "long",
         summ + " Program mode only; failure is minus the Linux errno.",
         [c(OMG, str(line), quote), HOST_HDR], exid)

# pread / pwrite are in section 9.5
PRW_NOTE = ("At the pin (omega-mv e5b32567) omc checks writability the wrong way round for these two words: "
            "pwrite refuses a text or view source with error 20 and pread accepts a text destination (the kernel "
            "then returns -14 EFAULT). Pass a global or new array to pwrite; never pass a text to pread.")
word("pread", "host-file", "pread fd A off n pos", 5, host_types(["fd", "A", "off", "n", "pos"]), "long",
     "Read n bytes at file position pos into A[off..] without moving the descriptor offset; bytes read or -errno.",
     [c(OMG, "482-483", "`pread fd A off n pos` / `pwrite fd A off n pos` (pos long)")], "files", notes=PRW_NOTE)
word("pwrite", "host-file", "pwrite fd A off n pos", 5, host_types(["fd", "A", "off", "n", "pos"]), "long",
     "Write A[off..off+n-1] at file position pos without moving the descriptor offset; bytes written or -errno.",
     [c(OMG, "482-483", "`pread fd A off n pos` / `pwrite fd A off n pos` (pos long)")], "files", notes=PRW_NOTE)

# device words (seed/host/MAPPING.md)
DEV = [
    ("devctl", 11, "devctl fd request A off n", ["fd: int", "request: uint literal (FIONREAD 21531 or an NVRM request)", "A: writable uchar array", "off: ulong", "n: ulong"], "long",
     "Checked Linux ioctl on an allowlisted request with its exact encoded size.", "mapping"),
    ("mapnew", 12, "mapnew fd offset bytes access mode", ["fd: int (-1 for anonymous)", "offset: ulong", "bytes: ulong", "access: int literal 1 or 3", "mode: int literal 1, 2, 33 or 34"], "long (handle)",
     "Map a file or anonymous memory; a positive owned handle or negative errno.", "mapping"),
    ("mapdrop", 13, "mapdrop handle", ["handle: long"], "long", "Unmap an owned mapping; 0 or negative errno.", "mapping"),
    ("mapread", 14, "mapread handle offset A off n", ["handle: long", "offset: ulong", "A: writable uchar array", "off: ulong", "n: ulong"], "long",
     "Copy n bytes from the mapping into A; return n.", "mapping"),
    ("mapwrite", 15, "mapwrite handle offset A off n", ["handle: long", "offset: ulong", "A: uchar array (text and views accepted)", "off: ulong", "n: ulong"], "long",
     "Copy n bytes from A into a writable mapping; return n.", "mapping"),
    ("devcall", 16, "devcall fd request H hoff 32 P poff n", ["fd: int", "request: uint literal (RM_ALLOC or RM_CONTROL)", "H: writable uchar array", "hoff: ulong", "32: header length", "P: writable uchar array", "poff: ulong", "n: ulong (at most 16383)"], "long",
     "Checked NVIDIA RM_ALLOC / RM_CONTROL call with a private header and a bounded parameter span.", "mapping"),
    ("uvmctl", 17, "uvmctl fd command A off n", ["fd: int", "command: uint literal from the UVM allowlist", "A: writable uchar array", "off: ulong", "n: ulong (the request's exact payload length)"], "long",
     "Allowlisted Linux UVM ioctl with its exact writable payload.", "mapping"),
    ("mapaddr", 18, "mapaddr handle", ["handle: long"], "ulong", "Base address of an owned live mapping or reservation (no access through it).", "mapping"),
    ("mapget", 19, "mapget handle offset width", ["handle: long", "offset: ulong", "width: int literal 4 or 8"], "ulong",
     "One aligned 32- or 64-bit load from a readable mapping.", "mapping"),
    ("mapset", 20, "mapset handle offset width value", ["handle: long", "offset: ulong", "width: int literal 4 or 8", "value: ulong"], "long",
     "One aligned 32- or 64-bit store into a writable mapping; returns 0.", "mapping"),
    ("maphold", 21, "maphold address bytes", ["address: ulong (at least 64 KiB, span below 1 TiB)", "bytes: ulong"], "long (handle)",
     "Reserve an unused page-aligned span (PROT_NONE, MAP_FIXED_NOREPLACE).", "mapping"),
    ("mapbind", 22, "mapbind handle fd offset access", ["handle: long", "fd: int", "offset: ulong", "access: int literal 1 or 3"], "long",
     "Bind a shared file or device mapping over a whole owned reservation.", "mapping"),
]
for name, line, form, types, res, summ, exid in DEV:
    word(name, "device", form, len(form.split()) - 1, types, res,
         summ + " Program mode only.", [c(MAP, str(line), f"`{form}`")], exid)

# types
TYPES = [("bool", None, "1-bit truth value: true 1, false 0", 1, "control"),
         ("uchar", None, "unsigned 8-bit", 1, "ints"), ("u8", "uchar", "unsigned 8-bit", 1, "ints"),
         ("ushort", None, "unsigned 16-bit", 2, "ints"), ("u16", "ushort", "unsigned 16-bit", 2, "ints"),
         ("uint", None, "unsigned 32-bit", 4, "ints"), ("u32", "uint", "unsigned 32-bit", 4, "ints"),
         ("ulong", None, "unsigned 64-bit", 8, "ints"), ("u64", "ulong", "unsigned 64-bit", 8, "ints"),
         ("byte", None, "signed 8-bit", 1, "ints"), ("i8", "byte", "signed 8-bit", 1, "ints"),
         ("short", None, "signed 16-bit", 2, "ints"), ("i16", "short", "signed 16-bit", 2, "ints"),
         ("int", None, "signed 32-bit", 4, "hello"), ("i32", "int", "signed 32-bit", 4, "ints"),
         ("long", None, "signed 64-bit", 8, "ints"), ("i64", "long", "signed 64-bit", 8, "ints")]
for name, alias, desc, size, exid in TYPES:
    signed = desc.startswith("signed")
    cite = (c(OMG, "447", "`true` and `false` are the bool numbers 1 and 0.") if name == "bool" else
            c(OMG, "433-434", "(byte 8,") if signed else
            c(OMG, "431", "(uchar 8, ushort 16, uint 32, ulong 64 bits)"))
    summ = f"Type word: {desc} integer, sizeof {size}." if name != "bool" else "Type word: bool (true 1, false 0), sizeof 1; never an array element."
    if alias:
        summ = f"Alias of {alias} (same keyword id): {desc}, sizeof {size}."
    if name != "bool":
        summ += (" Signed add/sub/mul/neg/div/shl trap 1 on overflow." if signed else " Arithmetic wraps modulo 2^width.")
    word(name, "type", f"{name} VALUE  (conversion) | NAME {name}  (parameter) | to {name}  (result)", 1,
         ["VALUE: any integer, float or bool value"], name if not alias else alias,
         summ + " As a prefix it converts a value, trapping 5 when out of range.",
         [cite, c(OMG, "439", "A conversion `<type> v` traps 5 when the value is outside the new type.")], exid)

OPS = [("add", "a + b", "431", "Unsigned add, sub, mul, shl, neg, not wrap modulo 2^width", "ints"),
       ("sub", "a - b", "431", "Unsigned add, sub, mul, shl, neg, not wrap modulo 2^width", "arith"),
       ("mul", "a * b", "431", "Unsigned add, sub, mul, shl, neg, not wrap modulo 2^width", "arith"),
       ("div", "a / b, rounding toward zero; divisor 0 traps 2", "435", "div and rem trap 2 when the divisor is 0.", "arith"),
       ("rem", "remainder with the sign of the dividend; divisor 0 traps 2", "435", "div and rem trap 2 when the divisor is 0.", "ints"),
       ("and", "bitwise and (bool and for bools; eager)", "440-441", "the two values of an op", "arith"),
       ("or", "bitwise or (bool or for bools; eager)", "440-441", "the two values of an op", "arith"),
       ("xor", "bitwise exclusive or", "440-441", "the two values of an op", "arith"),
       ("shl", "shift left; amount outside 0..width-1 traps 7", "437", "A shift amount outside 0 .. width - 1 traps 7", "arith"),
       ("shr", "shift right (arithmetic for signed); amount outside 0..width-1 traps 7", "437", "shr of a signed value keeps the sign.", "arith")]
for name, desc, line, quote, exid in OPS:
    word(name, "operator", f"{name} A B", 2, ["A: number type T", "B: the same type T"], "T",
         f"Binary operator: {desc}. Both operands have one type (no implicit conversion, error 7).",
         [c(OMG, line, quote)], exid)
for name, desc in (("eq", "equal"), ("ne", "not equal"), ("lt", "less than"), ("le", "less or equal"),
                   ("gt", "greater than"), ("ge", "greater or equal")):
    word(name, "operator", f"{name} A B", 2, ["A: number type T", "B: the same type T"], "bool",
         f"Comparison: {desc} (unsigned or signed by the operands' type; IEEE for floats).",
         [c(OMG, "567", "comparisons `eq ne lt le gt ge`")], "arith")
word("neg", "operator", "neg A", 1, ["A: number type T"], "T",
     "Negation: wraps for unsigned types, traps 1 for the signed minimum, IEEE for floats.",
     [c(OMG, "433", "Signed add, sub, mul, neg, div and shl trap 1")], "arith")
word("not", "operator", "not A", 1, ["A: integer type T or bool"], "T",
     "Bitwise complement of an integer; logical not of a bool.",
     [c(OMG, "431", "Unsigned add, sub, mul, shl, neg, not wrap modulo 2^width")], "arith")

D = "data"
word("get", D, "get A i | get P field [i]", 2, ["A: array", "i: integer index"], "element type",
     "Read element i of an array (or a struct/layout field). A constant index outside is error 21; a run-time one traps 3.",
     [c(OMG, "471", "`get A i` reads element i")], "arrays")
word("len", D, "len A", 1, ["A: array or text"], "ulong", "Length of an array as a ulong.",
     [c(OMG, "471", "`len A` is A's length as a ulong.")], "hello")
word("read", D, "read fd A off n", 4, ["fd: int", "A: writable uchar array", "off: ulong", "n: ulong"], "long",
     "Read n bytes from fd into A[off..]; bytes read or minus errno. Slice outside A traps 3.",
     [c(OMG, "478", "`read fd A off n` and `write fd A off n` (fd int, off and n ulong)")], "files")
word("write", D, "write fd A off n", 4, ["fd: int", "A: uchar array or text", "off: ulong", "n: ulong"], "long",
     "Write A[off..off+n-1] to fd; bytes written or minus errno. Slice outside A traps 3.",
     [c(OMG, "478", "`read fd A off n` and `write fd A off n` (fd int, off and n ulong)")], "hello")
word("true", D, "true", 0, [], "bool", "The bool value 1.", [c(OMG, "447", "`true` and `false` are the bool numbers 1 and 0.")], "control")
word("false", D, "false", 0, [], "bool", "The bool value 0.", [c(OMG, "447", "`true` and `false` are the bool numbers 1 and 0.")], "control")
word("view", D, "NAME view T N | NAME view T *  (parameter) | view A  (argument)", 3, ["T: element type", "N: length or * (OM-2 unsized)"], "-",
     "Read-only array parameter of exact type and length; writing through it is error 20.",
     [c(OMG, "464", "A parameter `NAME view T N` or `NAME edit T N`")], "arrays")
word("edit", D, "NAME edit T N | NAME edit T *  (parameter) | edit A  (argument)", 3, ["T: element type", "N: length or * (OM-2 unsized)"], "-",
     "Writable array parameter of exact type and length; a global is never passed (error 19).",
     [c(OMG, "464", "A parameter `NAME view T N` or `NAME edit T N`")], "arrays")

S = "structure"
word("fn", S, "fn NAME (PARAM TYPE)* to TYPE|void [inline]", 3, ["NAME: up to 63 characters", "PARAM: up to 8 characters, at most 6 slots"], "-",
     "Start a function; `end` closes it. `fn main` makes a whole Linux program (program mode).",
     [c(OMG, "54", "a function; `end` closes it"), c(OMG, "402", "A program with a line `fn main` is a whole Linux program")], "hello")
word("to", S, "fn ... to TYPE|void", 1, ["TYPE: a scalar type or void"], "-", "Introduces a function's result type.",
     [c(OMG, "54", "to <type> | void")], "hello")
word("end", S, "end", 0, [], "-", "Closes fn, if/else, while, for, struct and layout blocks. A missing end is error 15.",
     [c(OMG, "54", "`end` closes it")], "hello")
word("if", S, "if COND / [else] / end", 1, ["COND: bool"], "-", "Conditional block.",
     [c(OMG, "57", "if <cond> / else / end")], "control")
word("else", S, "else", 0, [], "-", "Second arm of an if block.", [c(OMG, "57", "if <cond> / else / end")], "control")
word("while", S, "while COND [bound N] / end", 1, ["COND: bool", "N: 1..999999"], "-",
     "Loop while COND holds; past N iterations (default 1000000) it traps 4.",
     [c(OMG, "58", "while <cond> [bound N] / end")], "control")
word("bound", S, "while COND bound N", 1, ["N: integer literal or constant 1..999999"], "-",
     "Iteration limit of a while loop; exceeding it traps 4.",
     [c(OMG, "58", "N 1..999999, default 1000000; past N iterations: trap 4")], "control")
word("for", S, "for NAME TYPE COUNT [unroll] / end", 3, ["NAME: new counter", "TYPE: integer type", "COUNT: number or value of TYPE"], "-",
     "Counted loop: NAME = 0 .. COUNT-1.",
     [c(OMG, "59", "for <name> <type> <count> / end")], "control")
word("ret", S, "ret [VALUE]", 1, ["VALUE: the function's result type (none for void)"], "-",
     "Return from the function; ends the path (a later line in the block is error 17).",
     [c(OMG, "65", "ret [<value>]")], "hello")
word("=", S, "NAME = VALUE", 2, ["NAME: new or existing name of the same type", "VALUE: any value"], "-",
     "Bind or overwrite a name (the = may be left out).",
     [c(OMG, "55", "<name> = <value>")], "hello")
word("(", S, "( VALUE )", 1, ["VALUE: any value"], "VALUE's type", "Grouping: returns exactly the value inside; adds no code.",
     [c(OMG, "589", "`(` and `)` are separate words")], "calls")
word(")", S, "( VALUE )", 1, ["VALUE: any value"], "VALUE's type", "Closes a group; a missing ) is error 16.",
     [c(OMG, "589", "`(` and `)` are separate words")], "calls")
word("void", S, "fn ... to void", 0, [], "-", "A function that returns no value; ret without a value or reaching end returns.",
     [c(OMG, "420", "`to void` makes a void function")], "arrays")

ST = "statement"
word("global", ST, "global NAME T N", 3, ["NAME: up to 8 characters", "T: element type", "N: 1..16777216"], "-",
     "A zero-filled pool of N elements in the program image. Program mode only; never passed as an argument (error 19).",
     [c(OMG, "454", "`global NAME T N`: a pool of N elements (1 .. 16777216)")], "arrays")
word("text", ST, 'text NAME "bytes"', 2, ["NAME: up to 8 characters", "bytes: escapes \\n \\t \\\\ \\\""], "-",
     "A read-only uchar array holding the quoted bytes. Program mode only.",
     [c(OMG, "457", '`text NAME "bytes"`: a read-only array of uchar')], "hello")
word("put", ST, "put A i v | put P field [i] v", 3, ["A: writable array", "i: integer index", "v: element type"], "-",
     "Store v at element i. Into a view or text: error 20.",
     [c(OMG, "66", "put <array> <index> <value>")], "arrays")
word("free", ST, "free  (refused)", 0, [], "-",
     "Reserved and always refused with error 9: arrays are given back when their function returns (decision 24).",
     [c(OMG, "462", "There is no `free`: nothing is given back by hand (decision 24), and the word is refused (error 9)."),
      c(OMC, "8530-8531", "if or or or eq c 77 eq c 78 eq c 79 eq c 81")], "free_refused")
word("own", ST, "own  (refused)", 0, [], "-",
     "Reserved word from the om4 draft; as a statement omc refuses it with error 9.",
     [c(OMC, "8530-8531", "if or or or eq c 77 eq c 78 eq c 79 eq c 81")], "own_refused")
word("exit", ST, "exit v", 1, ["v: int"], "-", "End the program with status v modulo 256; ends the path.",
     [c(OMG, "484", "`exit v` (v int) ends the program with status v modulo 256.")], "exit")
word("note", ST, "note ...", 0, [], "-", "A comment line: nothing after the first word is read.",
     [c(OMG, "486", "`note ...` is a line the translator does not read beyond its first word.")], "hello")
word("new", ST, "NAME = new T N v | NAME = new STRUCT v1 .. vn", 3, ["T: element type", "N: length", "v: initial element value"], "array",
     "A local array of N elements, each v, on the stack; only in a function's outermost block (error 9).",
     [c(OMG, "460", "`NAME = new T N v`: a local array of N elements, each v, on the stack")], "arrays")
word("break", ST, "break", 0, [], "-", "Leave the innermost loop; outside a loop error 9.",
     [c(OMG, "61", "leave the innermost loop; outside a loop: error 9.")], "control")
word("trap", ST, "trap N", 1, ["N: 1..14"], "-", "Stop with trap code N: program mode exits 100 + N.",
     [c(OMG, "67", "trap <code 1..14>         stop with that code")], "trapword")
word("continue", ST, "continue", 0, [], "-", "Jump to the next iteration (a while's head, a for's increment).",
     [c(OMG, "63", "jump to the next iteration")], "control")
word("const", ST, "const NAME TYPE LITERAL", 3, ["NAME: up to 8 characters", "TYPE: integer or float type", "LITERAL: value of TYPE"], "-",
     "A named typed constant, usable as a value, array length, for count, while bound or trap code.",
     [c(OMG, "608", "`const NAME TYPE LITERAL` at top level defines a named value before use.")], "consts")

word("struct", "struct", "struct Name field type [len] ... end", 3, ["fields: 1..16, at most 64 eight-byte cells"], "-",
     "A record type of eight-byte cells, declared on one line before the first fn.",
     [c(OMG, "502", "`struct Name field type [len] ... end`, one line, before the first `fn`.")], "structs")
word("sizeof", "struct", "sizeof T | sizeof STRUCT", 1, ["T: scalar type or struct"], "ulong",
     "Size in bytes; a compile-time constant.", [c(OMG, "597", "`sizeof T` is the size in bytes of a scalar type")], "structs")
word("offsetof", "struct", "offsetof STRUCT field", 2, ["STRUCT: struct name", "field: field name"], "ulong",
     "Byte offset of a field; a compile-time constant.", [c(OMG, "599", "`offsetof S f` is the byte offset of field `f`")], "structs")

F = "float"
word("f32", F, "f32 VALUE | 1.5f32", 1, ["VALUE: integer or float value"], "f32", "IEEE-754 binary32 type and conversion.",
     [c(OMG, "552", "`f32` and `f64` are IEEE-754 binary32 and binary64.")], "floats")
word("f64", F, "f64 VALUE | 1.5f64", 1, ["VALUE: integer or float value"], "f64", "IEEE-754 binary64 type and conversion.",
     [c(OMG, "552", "`f32` and `f64` are IEEE-754 binary32 and binary64.")], "floats")
word("bitcast", F, "bitcast T VALUE", 2, ["T: type of the same width", "VALUE: f32/i32/u32 or f64/i64/u64"], "T",
     "Reinterpret the bits of a same-width value.", [c(OMG, "577", "`bitcast T value` reinterprets a value of the same width")], "floats")
for name, form, ar, summ in (("fsqrt", "fsqrt X", 1, "IEEE square root."), ("fabs", "fabs X", 1, "Absolute value."),
                              ("fmin", "fmin A B", 2, "IEEE minNum (FMINNM)."), ("fmax", "fmax A B", 2, "IEEE maxNum (FMAXNM).")):
    word(name, F, form, ar, ["X: f32 or f64" if ar == 1 else "A, B: one float type"], "the operand type", summ,
         [c(OMG, "571", "Intrinsics `fsqrt x` and `fabs x` take one float; `fmin a b` and `fmax a b` take two of one float")], "floats")

O2 = "OM-2"
OM2 = c(OMG, "644-645", "rotr rotl unroll inline fresh abstract seal open holds layout field at little big part out")
for name, form, ar, types, res, summ, line, quote, exid in [
    ("rotr", "rotr X N", 2, ["X: unsigned type T", "N: T"], "T", "Rotate right; N outside 0..w-1 traps 7.", "669", "`rotr x n` and `rotl x n`", "om2_rotate"),
    ("rotl", "rotl X N", 2, ["X: unsigned type T", "N: T"], "T", "Rotate left; N outside 0..w-1 traps 7.", "669", "`rotr x n` and `rotl x n`", "om2_rotate"),
    ("unroll", "for i T K unroll", 0, ["K: number 1..64"], "-", "Compile the loop body K times with a constant counter.", "673", "`for i T K unroll`", "om2_unroll"),
    ("inline", "fn NAME ... to T inline", 0, [], "-", "Compile every call of the function in place.", "677", "`fn NAME ... to T inline`", "om2_unroll"),
    ("fresh", "NAME edit T N fresh", 0, ["N: at most 64"], "-", "Incoming elements are unspecified; every read needs a prior write (error 27).", "716", "A parameter `s edit T N fresh`", "om2_fresh"),
    ("abstract", "abstract NAME T [ops W ...]", 2, ["T: uint or ulong", "W: rotr rotl and or xor"], "-", "Declare an abstract type made only by seal in NAMEmk.", "726", "`abstract NAME T [ops W ...]`", "om2_abstract"),
    ("seal", "seal NAME v", 2, ["NAME: abstract type", "v: its base type T"], "NAME", "Make an abstract value; only inside the function NAMEmk (else error 28).", "728", "A value of it is made only by `seal NAME v`", "om2_abstract"),
    ("open", "open v", 1, ["v: abstract value"], "base type T", "The base value of an abstract value.", "730", "`open v` gives the T value.", "om2_abstract"),
    ("holds", "holds NAME dup32", 2, ["NAME: ulong abstract type"], "-", "Run-time invariant on every seal: high 32 bits equal low 32 (trap 10).", "727", "`holds NAME dup32`", "om2_abstract"),
    ("ops", "abstract NAME T ops W ...", 1, ["W: rotr rotl and or xor"], "-", "The operations allowed on an abstract type.", "726", "[ops W ...]", "om2_abstract"),
    ("layout", "layout NAME SIZE / field ... / end", 2, ["NAME: up to 8 bytes", "SIZE: 1..4096"], "-", "An external byte layout over a uchar array of SIZE bytes.", "703", "`layout NAME SIZE`", "om2_layout"),
    ("field", "field F T [COUNT] at OFF little|big", 5, ["T: integer type", "COUNT: 1..4096", "OFF: byte offset"], "-", "One field of a layout.", "703", "`field F T [COUNT] at OFF little|big`", "om2_layout"),
    ("at", "field F T at OFF ...", 1, ["OFF: byte offset"], "-", "Introduces a layout field's byte offset.", "703", "at OFF little|big", "om2_layout"),
    ("little", "field ... at OFF little", 0, [], "-", "Little-endian layout field.", "703", "at OFF little|big", "om2_layout"),
    ("big", "field ... at OFF big", 0, [], "-", "Big-endian layout field (REV on load/store).", "703", "at OFF little|big", "om2_layout"),
    ("part", "part A o k", 3, ["A: array name", "o: ulong", "k: ulong"], "view/edit of k elements", "Elements o..o+k-1 of A, only as an argument for an unsized parameter.", "750", "`part A o k` (o, k ulong; another type is error 7)", "om2_part"),
    ("out", "NAME out T N", 2, ["T: element type", "N: length"], "-", "A parameter written by the unit; inside it is an edit of T N.", "758", "A parameter `NAME out T N`", "om2_out"),
    ("export", "export fn NAME ...", 0, [], "-", "Mark a function-mode entry (no fn main).", "762", "`export fn NAME ...` at top level", "om2_export"),
]:
    word(name, O2, form, ar, types, res, summ + " OM-2 units only (first line `om2`).", [c(OMG, line, quote), OM2], exid, profile="OM-2")

missing = sorted(set(TAB) - set(W))
extra = sorted(set(W) - set(TAB))
assert not missing and not extra, (missing, extra)

# ---------------------------------------------------------------- errors
G15 = "seed/omc/gate15.sh"
ERR = {
    1: ("stdin read failed", "The compiler could not read its input (stdin is not readable, e.g. a directory).", "Give omc a readable source file on stdin.", 12005, None),
    2: ("stdout write failed", "The compiler could not write the binary (stdout is full or closed).", "Write omc's stdout to a regular file with space.", 8166, None),
    3: ("unknown name or field", "A word is used as a name but nothing of that name is in scope (or a struct has no such field).", "Declare the name first, or fix its spelling.", 2104, (OMG, "514", "An unknown field is error 3.")),
    4: ("line ends early", "The line stops before a required operand or word.", "Supply the missing operand (see the word's form).", 2743, (OMG, "503", "error 4 if the line ends before `end`")),
    5: ("extra words", "Words remain on the line after a complete statement.", "Remove the extra words or split the line.", 2785, (OMG, "938", "trailing words (error 5)")),
    6: ("malformed number", "A number has a non-digit character, more than 20 digits or a bad hex form.", "Write a plain decimal (or OM-2 lowercase 0x hex) number.", 1504, (OMG, "445", "more than 20 digits, or a character that is not a digit, is error 6")),
    7: ("type mismatch", "Two values of an operation, an assignment or a call argument have different types; there are no implicit conversions.", "Convert explicitly with a type word, e.g. `add int a int b`.", 2077, (OMG, "440-441", "or the line is refused (error 7).")),
    8: ("out of range", "A literal is outside its type, or a count/bound/trap code is out of its range.", "Use a value inside the type's range or a wider type.", 1815, (OMG, "443-444", "it must be a")),
    9: ("word not allowed here", "The word is not permitted in this position: break/continue outside a loop, new outside the outermost block, free/own/global/text as a statement, a seventh parameter slot, recursion in function mode.", "Move the statement to a valid position or use the documented alternative.", 2686, (OMG, "61", "outside a loop: error 9.")),
    10: ("duplicate name", "A name already in scope, a function or a struct is declared again.", "Choose a new name.", 2369, (OMG, "424-425", "A new name")),
    11: ("ambiguous bare number", "A number appears where no context gives it a type.", "Prefix it with a type word, e.g. `x = int 5`.", 2609, (OMG, "442", "A bare number takes the type the place needs.")),
    12: ("register pool exhausted", "More than 16 values are live at once in a function.", "Split the function or reuse names so fewer values are live.", 2410, (OMG, "492", "A function that needs more than the 16 registers it hands out is error 12.")),
    13: ("name too long", "A variable, text, global or constant name has more than 8 characters (functions allow 63).", "Shorten the name to at most 8 characters.", 2089, (OMG, "423", "Function names may have up to 63 characters; other names up to 8 (error 13).")),
    14: ("capacity exceeded", "A compiler table is full: too many names/globals, struct fields or cells, break sites, fresh arrays, unroll growth.", "Reduce the count below the documented capacity.", 524, (OMG, "490", "Input over a capacity is refused with error 14, never overrun")),
    15: ("missing end", "The input ends inside an open block.", "Add the missing `end`.", 6671, (OMG, "944", "Missing function `end` is error 15.")),
    16: ("syntax error or unknown word", "A line does not start with a known statement form, or a type/length position holds something else.", "Check the word's spelling and form with lookup.", 746, (OMG, "453", "a pool written without its length is refused (error 16)")),
    17: ("line after a path end", "A line follows ret, break, continue, trap or exit in the same block and can never run.", "Delete the unreachable line or move it before the path end.", 6405, (OMG, "61-62", "(a later line in the same block is error 17)")),
    18: ("missing ret", "A function with a result type can reach its end without a ret.", "Add a ret on every path (or make the function void).", 7609, (OMG, "421", "A function with a return type whose `end` can be reached is error 18.")),
    19: ("global passed or same array twice", "A global is passed as an argument, or one array is passed twice in a call.", "Copy the global into a local array (new) or pass distinct arrays.", 3772, (OMG, "467-468", "A global is")),
    20: ("write to a read-only array", "put, read or an edit argument targets a view or a text.", "Write into a local, global or edit array instead.", 3777, (OMG, "465", "A view is read-only; `put`, `read` into it, or passing it as edit is error 20.")),
    21: ("constant index out of range", "A literal index is outside the array or field.", "Use an index below the length.", 3687, (OMG, "472", "A number index must be inside A when om4 reads it (error 21)")),
    22: ("bad text literal", "A text literal has an unknown escape or no closing quote.", "Use only \\n \\t \\\\ \\\" escapes and close the quote.", 627, (OMG, "458-459", "any other escape, or a quote missing its end,")),
    23: ("size capacity", "An array is over 16777216 elements, globals over 1 GiB or local arrays over 4 MiB.", "Use a smaller array.", 2696, (OMG, "461", "at most 4 MiB of local arrays (error 23)")),
    24: ("branch displacement out of range", "A conditional branch target is misaligned or more than 2^18 words away.", "Split very large functions or programs; this is reached only by programs with about 1 MiB of code between a branch and its target.", 2468, (OMC, "2463-2464", "else error 24 before any artifact is accepted")),
    27: ("fresh element read before write (OM-2 init)", "A fresh parameter element is read before it is definitely written, or the array is passed on.", "Write every element before reading it (put with a number index).", 9622, (OMG, "720", "else error 27, `obligation=init`, on the get line")),
    28: ("abstract constructor violation (OM-2 ctor)", "seal outside the NAMEmk constructor, or a bad holds predicate.", "Seal only inside the function named NAME followed by mk.", 9187, (OMG, "729-730", "a `seal` anywhere else is")),
    29: ("layout violation (OM-2 layout)", "Layout SIZE outside 1..4096, a field past SIZE or overlapping an earlier field.", "Keep every field inside SIZE and non-overlapping.", 9747, (OMG, "706", "SIZE outside 1..4096 or a `layout` after the first `fn` is error 29")),
    30: ("contract syntax (OM-2)", "Misplaced requires/ensures/invariant, result outside a value postcondition, or a forbidden predicate operation.", "Put contracts first in the function or loop body and use only pure integer/bool operations.", 3894, (OMG, "1177-1178", "Compiler error **30** means misplaced")),
}
ERRS = {}
for k, (meaning, cause, fix, line, doc) in ERR.items():
    cites = [c(OMC, str(line), f"fail {k}"), c(OMC, "292-293", "fn fail code ulong to void")]
    if doc:
        cites.append(c(*doc))
    e = {"meaning": meaning, "cause": cause, "fix": fix, "citations": cites}
    if k == 1:
        e["example"] = None
        e["reproduce"] = "omc < /   (stdin is a directory: the read fails, exit 1, stderr 'omc: line 1: error 1')"
    elif k == 2:
        e["example"] = None
        e["reproduce"] = "omc < ok.om > /dev/full   (the write fails with ENOSPC, exit 2)"
    elif k == 24:
        e["example"] = None
        e["example_note"] = "No minimal example: it needs about 1 MiB of machine code between a branch and its target."
    else:
        e["example"] = f"e{k:02d}"
    if k in range(3, 24):
        e["citations"].append(c(G15, "85", "codes 3..23; 1 and 2 are compiler I/O"))
    ERRS[str(k)] = e

# ---------------------------------------------------------------- traps
TR = {1: ("OVERFLOW", "checked signed arithmetic out of range", "Signed add/sub/mul/neg/div/shl produced a value outside the type.", "Use a wider type, check the range first, or use an unsigned type if wrapping is intended.", (OMG, "433", "Signed add, sub, mul, neg, div and shl trap 1")),
      2: ("DIV0", "division by zero", "div or rem with a divisor of 0.", "Check the divisor before dividing.", (OMG, "435", "div and rem trap 2 when the divisor is 0.")),
      3: ("BOUNDS", "index or slice out of bounds", "A run-time index is not below the length, or a host/read/write slice is outside its array.", "Check the index against len A, or fix off/n.", (OMG, "473", "traps 3 when it is not below the length")),
      4: ("LOOP_BOUND", "loop exceeded its bound", "A while ran more than its bound (default 1000000) iterations.", "Fix the loop condition or raise bound N (at most 999999).", (OMG, "58", "past N iterations: trap 4")),
      5: ("CAST", "checked conversion out of range", "A conversion `T v` got a value outside T.", "Check the range before converting, or convert to a wider type.", (OMG, "439", "A conversion `<type> v` traps 5 when the value is outside the new type.")),
      6: ("OOM", "stack pool exhausted", "A call or local array would go below the fixed 8 MiB stack (deep recursion).", "Bound the recursion or use a loop / smaller local arrays.", (OMG, "426-427", "a call or a local array that would go below it traps")),
      7: ("SHIFT", "shift or rotate amount out of range", "A shift or rotate amount is outside 0..width-1.", "Check the amount against the width.", (OMG, "437", "A shift amount outside 0 .. width - 1 traps 7")),
      8: ("RUNTIME", "runtime invariant broken", "A runtime invariant (double release, bad handle) failed; checked native code raises it only through `trap 8`.", "Find the explicit trap 8 in the program.", (IRH, "176", "OSC_TRAP_RUNTIME = 8")),
      9: ("REQUIRES", "precondition failed", "A requires clause was false on entry.", "Call the function only with arguments that satisfy its requires clauses.", (OMG, "1173", "False `requires` uses existing trap **9** (program exit **109**)")),
      10: ("ENSURES", "postcondition or invariant failed", "An ensures, invariant or holds check was false.", "Fix the function body or loop so the stated property holds.", (OMG, "1174", "`ensures` or `invariant` uses existing trap **10** (exit **110**).")),
      11: ("ARENA_FULL", "arena allocation over capacity", "An OSC arena allocation exceeded the arena's capacity; native program mode raises it only through `trap 11`.", "Find the explicit trap 11 in the program.", (IRH, "183", "OSC_TRAP_ARENA_FULL = 11")),
      12: ("STALE", "stale versioned handle", "A handle whose generation no longer matches its slot; native program mode raises it only through `trap 12`.", "Find the explicit trap 12 in the program.", (IRH, "185", "OSC_TRAP_STALE = 12")),
      13: ("POOL_FULL", "pool allocation with every slot live", "An OSC pool allocation found no free slot; native program mode raises it only through `trap 13`.", "Find the explicit trap 13 in the program.", (IRH, "186", "OSC_TRAP_POOL_FULL = 13")),
      14: ("RETIRED", "pool slot retired at the maximum generation", "An OSC pool allocation found only retired slots; native program mode raises it only through `trap 14`.", "Find the explicit trap 14 in the program.", (IRH, "187", "OSC_TRAP_RETIRED = 14"))}
TRAPS = {}
for k, (name, meaning, cause, fix, doc) in TR.items():
    TRAPS[str(k)] = {"name": name, "meaning": meaning, "cause": cause, "fix": fix,
                     "citations": [c(*doc), c(OMG, "406", "A trap in program mode ends the program with exit status 100 + the trap code")],
                     "example": "contract_fail" if k == 9 else f"t{k:02d}"}

# ---------------------------------------------------------------- topics
TOP = {
    "requires": {"form": "requires BOOL", "summary": "OM-2 precondition: part of a function's prefix, checked on entry; false traps 9.",
                 "details": "Clauses run in declaration order after parameter binding. Predicates are pure: integer/bool operations, conversions, len and array reads only.",
                 "citations": [c(OMG, "1128", "`requires BOOL` and `ensures BOOL` form a function's prefix"), c(OMG, "1173", "False `requires` uses existing trap **9**")], "example": "contract_fail"},
    "ensures": {"form": "ensures BOOL", "summary": "OM-2 postcondition: checked on every normal return; `result` names the returned value; false traps 10.",
                "details": "Not run on exit or a trap. A parameter means its current value at return.",
                "citations": [c(OMG, "1133", "Postconditions execute in declaration order on **every normal return**")], "example": "contracts"},
    "invariant": {"form": "invariant BOOL", "summary": "OM-2 loop invariant: the prefix of a while or for body, checked at the loop head; false traps 10.",
                  "details": "Runs on entry, every backedge and before the final false condition.",
                  "citations": [c(OMG, "1146", "`invariant BOOL` forms the prefix of a `while` or `for` body")], "example": "contracts"},
    "result": {"form": "result", "summary": "OM-2: the returned value, available only inside ensures clauses (elsewhere error 30).",
               "details": "It has the declared return type; the caller receives the same value after the checks.",
               "citations": [c(OMG, "1137", "The read-only name `result` is available only in value postconditions.")], "example": "contracts"},
    "om2": {"form": "om2 | om2 diag | om2 fmt", "summary": "First line that opts a unit into profile OM-2 (rotate, unroll, inline, layout, abstract types, contracts, unsized views).",
            "details": "Leading blank and note lines are skipped; in an OM-1 unit the om2 line is error 16.",
            "citations": [c(OMG, "642-643", "when the next line is exactly `om2`")], "example": "om2_rotate"},
    "exit_status": {"summary": "Program exit status: main's value modulo 256; a trap N exits 100 + N; exit v exits v modulo 256.",
                    "details": "An explicit exit 101..114 cannot be told apart from a trap by status alone.",
                    "citations": [c(OMG, "404-405", "main's value modulo 256"), c(OMG, "406", "exit status 100 + the trap code")], "example": "exit"},
    "packed_list": {"summary": "Host-word argument lists: little-endian u16 count, then per record a u16 length and the bytes.",
                    "details": "At most 4096 bytes, count 1..64; zero bytes, truncation or trailing bytes trap 3. Used by execprog, renames, link, symlnk.",
                    "citations": [c(OMG, "896", "A packed list is a little-endian `u16` count followed by that many records")], "example": "dirs"},
    "paths": {"summary": "Host paths are length-delimited byte slices of at most 4095 bytes; embedded zero bytes trap 3.",
              "details": "Relative paths resolve against the current directory (AT_FDCWD).",
              "citations": [c(OMG, "857", "Paths are at most 4095 bytes.")], "example": "files"},
    "host_words": {"summary": "Native host words: Linux system calls with checked slices; results are long, negative errno on failure.",
                   "details": "They do not form a sandbox: they run with the process's permissions. Program mode only.",
                   "citations": [c(OMG, "775-778", "These operations do not form a sandbox")], "example": "files"},
    "compile_errors": {"summary": "omc writes `omc: line N: error K` to stderr and exits with K; use explain_error for any K.",
                       "details": "Codes 1..24 and 27..30 exist at the pin; 25 and 26 are unused.",
                       "citations": [c(OMC, "292-293", "fn fail code ulong to void")], "example": "e03"},
    "traps": {"summary": "Run-time traps 1..14 end a program with exit 100 + code.",
              "details": "Codes are part of the observable semantics and are never renumbered.",
              "citations": [c(IRH, "165-166", "Trap codes are part of the observable semantics")], "example": "t02"},
    "contracts": {"summary": "OM-2 contracts: requires, ensures and invariant clauses checked at run time (traps 9 and 10).",
                  "details": "Compiler error 30 covers misplaced contracts, unavailable result and impure predicates.",
                  "citations": [c(OMG, "1177-1178", "Compiler error **30** means misplaced")], "example": "contracts"},
}

# ---------------------------------------------------------------- tools (MCP definitions)
SRC = {"type": "string", "description": "Omega (.om) source text of one unit"}
TOOLS = [
    {"name": "compile", "title": "Compile Omega source",
     "description": "Compile Omega (.om) source with the pinned seeded compiler omc (omega-mv@e5b32567). Returns ok, the binary's size and sha256, or the compile error {line, code, meaning, fix}.",
     "inputSchema": {"type": "object", "properties": {"source": SRC}, "required": ["source"], "additionalProperties": False}},
    {"name": "run", "title": "Compile and run Omega source",
     "description": "Compile Omega source and run the program in an isolated sandbox (no network, no host filesystem, empty environment, CPU/memory/file/process limits). Returns the compile result, capped stdout/stderr and the interpreted exit status (normal, trap N with its meaning, or the limit that stopped it).",
     "inputSchema": {"type": "object", "properties": {"source": SRC, "stdin": {"type": "string", "description": "bytes given to the program on stdin (default empty)"},
                                                      "timeout_ms": {"type": "integer", "minimum": 1, "maximum": 30000, "description": "wall-clock limit in milliseconds (default 5000)"}},
                     "required": ["source"], "additionalProperties": False}},
    {"name": "explain_error", "title": "Explain an Omega error or trap",
     "description": "Explain a compile error code 1..30, an `omc: line N: error K` line, `trap T`, or a program exit status 101..114 (trap). Returns meaning, cause, fix, a minimal example and source citations.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": ["string", "integer"], "description": "an error code 1..30, an `omc: line N: error K` line, `trap T` (1..14) or an exit status 101..114; a string of 1..200 bytes or a nonnegative integer"}},
                     "required": ["query"], "additionalProperties": False}},
    {"name": "lookup", "title": "Look up an Omega word or topic",
     "description": "Look up any Omega keyword (all 177 entries of the compiler's keyword table) or a topic (requires, ensures, invariant, result, om2, exit_status, packed_list, paths, host_words, compile_errors, traps, contracts): form, arity, types, result, example and citations. A query that is not an exact keyword or topic searches names and summaries (at most 20 results).",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 64, "description": "exact keyword or topic, or a case-insensitive substring to search for"}},
                     "required": ["query"], "additionalProperties": False}},
]

ref = {"pin": {"omega_mv": "e5b32567a7aff3ce594e3254a622a846a6cd190b",
               "omc_sha256": "2c82480596bbdc50cda9626866209ef662d5834f278f839ff4ce0250c495029f"},
       "tools": TOOLS, "errors": ERRS, "traps": TRAPS, "words": W, "topics": TOP,
       "examples": {i: exp for i, (src, exp) in EX.items()}}
used = {e["example"] for e in W.values()} | {e["example"] for e in ERRS.values() if e["example"]} | \
       {e["example"] for e in TRAPS.values()} | {e["example"] for e in TOP.values()}
unused = sorted(set(EX) - used)
assert not unused, unused
os.makedirs(OUT + "/examples", exist_ok=True)
for f in os.listdir(OUT + "/examples"):
    os.remove(OUT + "/examples/" + f)
for i, (src, exp) in EX.items():
    assert re.fullmatch(r"[a-z0-9_]+", i)
    open(f"{OUT}/examples/{i}.om", "w").write(src)
raw = json.dumps(ref, indent=1, ensure_ascii=True) + "\n"
open(OUT + "/reference.json", "w").write(raw)
print("words", len(W), "errors", len(ERRS), "traps", len(TRAPS), "examples", len(EX), "bytes", len(raw))
