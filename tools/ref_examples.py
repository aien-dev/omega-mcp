# Example programs for data/examples (authoring input of tools/gen-reference.py). id -> (source, expect)
EX = {}


def ex(i, src, **exp):
    EX[i] = (src.lstrip("\n"), exp)


ex("hello", r'''
note write the bytes of a text to stdout (fd 1); main's value is the exit status
text msg "hello\n"
fn main to int
w = write 1 msg 0 len msg
ret 0
end
''', mode="run", exit=0, stdout="hello\n")

ex("ints", '''
note every integer width; each value converts to long and the sum modulo 256 is the exit status
fn main to int
s = long uchar 200
s = add s long u8 1
s = add s long ushort 300
s = add s long u16 2
s = add s long uint 3
s = add s long u32 4
s = add s long ulong 5
s = add s long u64 6
s = add s long byte -7
s = add s long i8 8
s = add s long short -9
s = add s long i16 10
s = add s long int 11
s = add s long i32 12
s = add s long 13
s = add s i64 14
ret int rem s 256
end
''', mode="run", exit=61)

ex("arith", '''
note signed and unsigned arithmetic, bit operations, comparisons and not
fn main to int
a = int 17
b = int 5
s = add a b
s = sub s mul a b
s = add s div a b
s = add s rem a b
x = uint 12
x = and x 10
x = or x 3
x = xor x 6
x = shl x 2
x = shr x 1
n = neg s
k = int 0
if eq n 58
k = add k 1
end
if ne a b
k = add k 1
end
if lt b a
k = add k 1
end
if le a 17
k = add k 1
end
if gt a b
k = add k 1
end
if ge b 5
k = add k 1
end
if not lt a b
k = add k 1
end
ret add add n int x k
end
''', mode="run", exit=91)

ex("control", '''
note while with a bound, continue, break, for, if/else and bool values
fn pick c bool to uint
if c
ret 100
else
ret 1
end
end
fn main to int
s = uint 0
i = uint 0
while lt i 100 bound 1000
i = add i 1
if eq rem i 2 0
continue
end
if gt i 9
break
end
s = add s i
end
for j uint 4
s = add s j
end
t = true
f = false
s = add s pick and t not f
ret int s
end
''', mode="run", exit=131)

ex("arrays", '''
note a local array (new), a global pool, view and edit parameters, get, put and len
global tot ulong 1
fn sum a view uint 4 to uint
s = uint 0
for i ulong len a
s = add s get a i
end
ret s
end
fn fill a edit uint 4 to void
for i ulong 4
put a i uint add i 1
end
end
fn main to int
a = new uint 4 0
fill a
put tot 0 ulong sum a
ret int get tot 0
end
''', mode="run", exit=10)

ex("calls", '''
note recursion, a void function, ret with and without a value, grouping parentheses
fn fib n uint to uint
if lt n 2
ret n
end
ret add (fib sub n 1) (fib sub n 2)
end
fn nothing v uint to void
if gt v 1
ret
end
end
fn main to int
nothing 3
x = (fib 10)
ret int x
end
''', mode="run", exit=55)

ex("exit", '''
note exit ends the program at once; the status is the value modulo 256
fn main to int
exit 300
end
''', mode="run", exit=44)

ex("trapword", '''
note trap N stops the program; in program mode the exit status is 100 + N
fn main to int
trap 4
end
''', mode="trap", trap=4)

ex("free_refused", '''
fn main to int
a = new uchar 4 0
free a
ret 0
end
''', mode="error", code=9, line=3)

ex("own_refused", '''
fn main to int
a = new uchar 4 0
own a
ret 0
end
''', mode="error", code=9, line=3)

ex("structs", '''
note a struct on the stack, field get and put, sizeof and offsetof
struct Pt x long y long end
fn main to int
p = new Pt 3 4
put p x add get p x 10
s = add get p x get p y
z = add sizeof Pt offsetof Pt y
ret int add s long z
end
''', mode="run", exit=41)

ex("floats", '''
note f64 and f32 values, fsqrt, fabs, fmin, fmax, conversions and bitcast
fn main to int
if ne bitcast ulong 1.0f64 4607182418800017408
ret 1
end
r = fsqrt 16.0f64
b = fabs neg 1.5f64
c = fmax b fmin 0.25f64 3.0f64
d = f32 1.5f64
v = add mul r 2.0f64 add c f64 d
ret int v
end
''', mode="run", exit=11)

ex("consts", '''
note named typed constants, used as an array length, a for count and a value
const lim uint 5
const seven uint 7
fn main to int
a = new uint lim seven
s = uint 0
for i uint lim
s = add s get a i
end
ret int s
end
''', mode="run", exit=35)

ex("om2_rotate", '''
om2
note rotr and rotl rotate an unsigned value; amounts outside 0..width-1 trap 7
fn main to int
x = uint 0x80000001
y = rotr x 1
z = rotl y 2
ret int z
end
''', mode="run", exit=3)

ex("om2_unroll", '''
om2
note unroll compiles the body K times with a constant counter; inline compiles each call in place
fn sq x ulong to ulong inline
ret mul x x
end
fn main to int
s = ulong 0
for i ulong 4 unroll
s = add s sq i
end
ret int s
end
''', mode="run", exit=14)

ex("om2_abstract", '''
om2
note abstract types: values made only by seal in NAMEmk, read by open, operations listed by ops;
note holds dup32 checks every seal at run time (trap 10)
abstract tag uint ops and or
abstract dup32 ulong ops xor
holds dup32 dup32
fn tagmk x uint to tag
ret seal tag x
end
fn dup32mk x uint to dup32
ret seal dup32 or shl ulong x 32 ulong x
end
fn main to int
t = or tagmk 12 tagmk 3
u = and t tagmk 5
d = xor dup32mk 7 dup32mk 4
if ne open d 12884901891
ret 1
end
ret int open u
end
''', mode="run", exit=5)

ex("om2_fresh", '''
om2
note fresh: incoming elements are unspecified, so every element must be written before it is read
fn f s edit uchar 4 fresh to ulong
for i ulong 4 unroll
put s i uchar add i 1
end
ret add ulong get s 0 ulong get s 3
end
fn main to int
a = new uchar 4 0
ret int f a
end
''', mode="run", exit=5)

ex("om2_layout", '''
om2
note an external byte layout: fields at fixed offsets with a byte order, over a uchar array of SIZE bytes
layout hdr 6
field magic ushort at 0 big
field size uint at 2 little
end
fn setc c edit hdr to void
put c magic 0x4f4d
put c size 258
end
fn main to int
c = new uchar 6 0
setc c
ret int add get c 0 get c 2
end
''', mode="run", exit=81)

ex("om2_part", '''
om2
note part A o k passes elements o..o+k-1 to an unsized view or edit parameter (T *)
text msg "0123456789"
fn first v view uchar * to ulong
ret ulong get v 0
end
fn main to int
ret int first part msg 7 3
end
''', mode="run", exit=55)

ex("om2_out", '''
om2
note an out parameter is written by the unit; inside the unit it is an edit of T N
fn fill r out ulong 3 v ulong to ulong
for i ulong 3
put r i add v i
end
ret get r 2
end
fn main to int
a = new ulong 3 0
ret int fill a 10
end
''', mode="run", exit=12)

ex("om2_export", '''
om2
note function mode: export marks an entry; word 0 branches to it. Compile only (no fn main).
export fn twice a ulong to ulong
ret add a a
end
''', mode="compile")

ex("contracts", '''
om2
note requires and ensures form a function's prefix; invariant forms a loop body's prefix;
note result is the returned value inside ensures
fn step x uint to uint
requires lt x 10
ensures eq result add x 1
ret add x 1
end
fn main to int
i = uint 0
while lt i 3
invariant le i 3
i = step i
end
ret int sub i 3
end
''', mode="run", exit=0)

ex("contract_fail", '''
om2
note a false requires stops the program with trap 9 (exit 109)
fn step x uint to uint
requires lt x 2
ret add x 1
end
fn main to int
ret int step 5
end
''', mode="trap", trap=9)

ex("files", '''
note open, write, sync, lock, seek, read, positioned read and write, truncate, stat, chmod, unlink, memfd
text path "demo.txt"
global data uchar 5
global buf uchar 128
fn ck yes bool to void
if not yes
exit 80
end
end
fn main to int
for i ulong 5
put data i uchar add 97 i
end
old = umask 18
fd = int fopen path 0 len path 578 420
ck ge fd 0
ck eq write fd data 0 len data 5
ck eq fsync fd 0
ck eq fdsync fd 0
ck eq flock fd 2 0
ck eq syncfs fd 0
ck eq pwrite fd data 0 1 5 1
ck eq fseek fd 0 0 0
ck eq read fd buf 0 6 6
ck eq pread fd buf 0 2 3 2
ck eq ftrunc fd 3 0
ck eq fstat fd buf 0 128 0
ck eq fchmod fd 384 0
ck eq fclose fd 0
ck eq stat path 0 len path buf 0 128 0
ck eq lstat path 0 len path buf 0 128 0
ck eq chmod path 0 len path 420 0
ck eq faccess path 0 len path 4 0
ck eq truncate path 0 len path 1 0
ck eq unlink path 0 len path 0
m = memfd path 0 len path 0
ck ge m 0
ret 0
end
''', mode="run", exit=0)

ex("dirs", '''
note directories, links and renames; paths pairs are packed lists (u16 count, then u16 length + bytes)
text dir "sub"
text gone "tmp"
text fa "a"
text dot "."
global buf uchar 512
fn ck yes bool to void
if not yes
exit 80
end
end
fn main to int
ck eq makedir dir 0 len dir 448 0
ck eq makedir gone 0 len gone 448 0
ck eq rmdir gone 0 len gone 0
ck eq chdir dir 0 len dir 0
ck gt cwd buf 0 512 0
fd = int fopen fa 0 len fa 577 384
ck ge fd 0
ck eq fclose fd 0
p = new uchar 8 0
put p 0 2
put p 2 1
put p 4 97
put p 5 1
put p 7 98
ck eq link p 0 8 0
put p 7 99
ck eq symlnk p 0 8 0
c = new uchar 1 99
ck eq readlnk c 0 1 buf 0 64 1
put p 4 98
put p 7 100
ck eq renames p 0 8 1 0
ck eq chown fa 0 len fa int getuid int getgid 0
ck ge add geteuid getegid 0
d = int fopen dot 0 len dot 0 0
ck ge d 0
ck gt getdnts d buf 0 512 0
ck eq fchdir d 0
ret 0
end
''', mode="run", exit=0)

ex("procs", '''
note fork, wait, signals, pipes, dup, process groups and sessions, and a failed execprog
global st uchar 4
global ends uchar 8
fn ck yes bool to void
if not yes
exit 80
end
end
fn main to int
ck eq pipefds ends 0 8 0 0
p = fork
if eq p 0
exit 7
end
ck gt p 0
ck eq waitpid int p st 0 4 0 p
ck eq get st 1 7
ck eq killpid int getpid 0 0
ck ge getppid 0
ck ge getpgid 0 0
ck ge getsid 0 0
r = setpgid 0 0
s = setsid
ck eq dupfd 1 9 0 9
x = new uchar 6 0
put x 0 1
put x 2 2
put x 4 47
put x 5 120
ck eq execprog x 0 6 neg long 2
ret 0
end
''', mode="run", exit=0)

ex("argsenv", '''
note the argument and environment vectors; the server runs programs with no arguments and an empty environment
global buf uchar 64
fn main to int
n = argcnt
r = argread 0 buf 0 64
if gt envcnt 0
x = envread 0 buf 0 64
end
ret int n
end
''', mode="run", exit=1)

ex("clock", '''
note monotonic and realtime clocks, a short sleep and random bytes
global buf uchar 16
fn main to int
a = monons
r = sleepns 1000000
b = monons
if lt sub b a 1000000
ret 1
end
if le realns 0
ret 2
end
if ne random buf 0 16 0 16
ret 3
end
ret 0
end
''', mode="run", exit=0)

ex("sockets", '''
note a Unix socket pair in the working directory: socket, option, bind, listen, connect, accept,
note send, wait, receive, peer identity, sendmsg, poll and shutdown
global buf uchar 64
global four uchar 4
global pfd uchar 8
text msg "ping"
fn ck yes bool to void
if not yes
exit 80
end
end
fn main to int
na = new uchar 3 0
put na 0 1
put na 2 115
s = int socknew 1 1 0
ck ge s 0
put four 0 1
ck eq sockopt s 1 2 four 0 4 0
ck eq bind s na 0 3 0
ck eq listen s 4 0
ck gt sockname s buf 0 64 0
c = int socknew 1 1 0
ck eq connect c na 0 3 0
a = int accept s 0
ck ge a 0
ck eq send c msg 0 4 0 4
ck gt waitio a 1 1000000000 0
ck eq recv a buf 0 4 0 4
ck eq peercred a buf 0 12 0
ck eq sendmsg a msg 0 4 0 4
put pfd 0 uchar c
put pfd 4 1
ck eq pollfds pfd 0 8 1000000000 1
ck eq shutdown c 2 0
ret 0
end
''', mode="run", exit=0)

ex("mapping", '''
note owned mappings and checked device calls; device calls use fd -1 here, so no device is opened
global hdr uchar 48
global prm uchar 32
global data uchar 64
global ends uchar 8
global cnt uchar 4
global buf uchar 8
text name "m"
fn ck yes bool to void
if not yes
exit 80
end
end
fn main to int
h = mapnew neg int 1 0 4096 3 34
ck gt h 0
ck gt mapaddr h 4096
ck eq mapset h 8 8 77 0
ck eq mapget h 8 8 77
put buf 0 5
ck eq mapwrite h 0 buf 0 1 1
ck eq mapread h 0 buf 1 1 1
ck eq get buf 1 5
ck eq mapdrop h 0
ck eq pipefds ends 0 8 0 0
rd = int get ends 0
ck eq devctl rd uint 21531 cnt 0 4 0
ck eq devcall neg int 1 uint 3223340587 hdr 0 32 prm 0 0 neg long 9
ck eq uvmctl neg int 1 uint 75 data 8 8 neg long 9
m = int memfd name 0 len name 0
ck ge m 0
ck eq ftrunc m 4096 0
r = maphold 68719476736 4096
ck gt r 0
ck eq mapbind r m 0 3 0
ret 0
end
''', mode="run", exit=0)

# compiler error examples (gate15 cases and OM-2 obligations)
ex("e03", "fn main to int\nret q\nend\n", mode="error", code=3, line=2)
ex("e04", "struct S a uint\nfn main to int\nret 0\nend\n", mode="error", code=4, line=2)
ex("e05", "fn main to int\nret 0 extra\nend\n", mode="error", code=5, line=2)
ex("e06", "fn main to int\nx = 12a\nret 0\nend\n", mode="error", code=6, line=2)
ex("e07", "fn main to int\nx = add int 1 uint 2\nret 0\nend\n", mode="error", code=7, line=2)
ex("e08", "fn main to int\nx = int 2147483648\nret 0\nend\n", mode="error", code=8, line=2)
ex("e09", "fn main to int\nbreak\nret 0\nend\n", mode="error", code=9, line=2)
ex("e10", "fn f x int x int to int\nret 0\nend\nfn main to int\nret 0\nend\n", mode="error", code=10, line=1)
ex("e11", "fn main to int\nx = 5\nret 0\nend\n", mode="error", code=11, line=2)
ex("e12", "fn main to int\n" + "".join(f"a{i} = int {i}\n" for i in range(1, 18))
   + "ret add a1 add a2 add a3 add a4 add a5 add a6 add a7 add a8 add a9 add a10 add a11 add a12 add a13 add a14 add a15 add a16 a17\nend\n",
   mode="error", code=12, line=18)
ex("e13", "fn main to int\nabcdefghi = int 1\nret 0\nend\n", mode="error", code=13, line=2)
ex("e14", "struct S a long b long c long d long e long f long g long h long i long j long k long l long m long n long o long p long q long end\nfn main to int\nret 0\nend\n",
   mode="error", code=14, line=1)
ex("e15", "fn main to int\nret 0\n", mode="error", code=15, line=3)
ex("e16", "wat\n", mode="error", code=16, line=1)
ex("e17", "fn main to int\nret 0\nret 1\nend\n", mode="error", code=17, line=3)
ex("e18", "fn f to int\nend\nfn main to int\nret 0\nend\n", mode="error", code=18, line=3)
ex("e19", "global g uchar 4\nfn f a edit uchar 4 to void\nend\nfn main to int\nf g\nret 0\nend\n", mode="error", code=19, line=5)
ex("e20", "text t \"abc\"\nfn main to int\nput t 0 1\nret 0\nend\n", mode="error", code=20, line=3)
ex("e21", "fn main to int\na = new uint 4 0\nput a 4 1\nret 0\nend\n", mode="error", code=21, line=3)
ex("e22", "text t \"a\\q\"\nfn main to int\nret 0\nend\n", mode="error", code=22, line=1)
ex("e23", "fn main to int\na = new uchar 16777217 0\nret 0\nend\n", mode="error", code=23, line=2)
ex("e27", "om2\nfn f s edit uchar 4 fresh to ulong\nret ulong get s 0\nend\nfn main to int\na = new uchar 4 0\nret int f a\nend\n",
   mode="error", code=27, line=3)
ex("e28", "om2\nabstract tag uint\nfn main to int\nt = seal tag 1\nret 0\nend\n", mode="error", code=28, line=4)
ex("e29", "om2\nlayout hdr 4\nfield a uint at 2 little\nend\nfn main to int\nret 0\nend\n", mode="error", code=29, line=3)
ex("e30", "om2\nfn f x uint to uint\nrequires eq result 0\nret x\nend\nfn main to int\nret int f 1\nend\n", mode="error", code=30, line=3)

# trap examples
ex("t01", "fn main to int\nx = int 2147483647\ny = add x 1\nret 0\nend\n", mode="trap", trap=1)
ex("t02", "fn main to int\nz = int 0\nret div 7 z\nend\n", mode="trap", trap=2)
ex("t03", "fn main to int\na = new uchar 4 0\ni = ulong 4\nret int get a i\nend\n", mode="trap", trap=3)
ex("t04", "fn main to int\ni = int 0\nwhile ge i 0 bound 10\ni = add i 1\nend\nret 0\nend\n", mode="trap", trap=4)
ex("t05", "fn main to int\nx = int 300\ny = uchar x\nret 0\nend\n", mode="trap", trap=5)
ex("t06", "fn deep n ulong to ulong\nret add 1 deep add n 1\nend\nfn main to int\nret int deep 0\nend\n", mode="trap", trap=6)
ex("t07", "fn main to int\ns = uint 40\nx = shl uint 1 s\nret 0\nend\n", mode="trap", trap=7)
for n in (8, 11, 12, 13, 14):
    ex(f"t{n:02d}", f"note native program mode raises trap {n} only through the trap word\nfn main to int\ntrap {n}\nend\n",
       mode="trap", trap=n)
ex("t10", "om2\nfn one to uint\nensures eq result 2\nret 1\nend\nfn main to int\nret int one\nend\n", mode="trap", trap=10)
