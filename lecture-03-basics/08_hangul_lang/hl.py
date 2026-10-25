"""데모 8 : 한글 언어 '업무' - 파이썬 소스를 거치지 않고 바이트코드를 직접 만들어 .pyc 로 굽는다

  소스(.업무) --lexer--> 토큰 --parser--> AST --codegen--> 바이트코드(직접 조립) --> code 객체 --marshal--> .pyc
                                                                                    └ PVM(python) 이 그대로 실행

사용법 (파이썬 3.14 전용 : 바이트코드와 pyc 매직넘버가 버전마다 다르다)
  python hl.py build hello.업무        # hello.pyc 생성
  python hello.pyc                     # PVM 에서 그냥 실행 (우리 컴파일러는 이미 빠짐)
  python hl.py dis hello.pyc           # 직접 만든 바이트코드 구경
  python hl.py run hello.업무          # build + 실행
"""
import dis
import importlib.util
import marshal
import opcode
import re
import struct
import subprocess
import sys
import types
from pathlib import Path

assert sys.version_info[:2] == (3, 14), f"3.14 에서만 동작 (지금 {sys.version.split()[0]}) : 바이트코드는 버전마다 다르다"

# ───────────────────────── 1) lexer ─────────────────────────
TOKEN = re.compile(r"""\s+|\#[^\n]*|(?P<num>\d+)|(?P<str>"[^"\n]*")|(?P<name>[^\W\d]\w*)|(?P<op>==|!=|<=|>=|[-+*<>=(){},])""")


def lex(src):
    pos, out = 0, []
    while pos < len(src):
        m = TOKEN.match(src, pos)
        if not m:
            raise SyntaxError(f"이상한 글자: {src[pos]!r} (위치 {pos})")
        pos = m.end()
        if m.lastgroup:
            out.append((m.lastgroup, m.group()))
    out.append(("eof", ""))
    return out


# ───────────────────────── 2) parser (AST 는 튜플) ─────────────────────────
CONST = {"참": True, "true": True, "거짓": False, "false": False, "없음": None}
CMP = {"<", ">", "==", "!=", "<=", ">="}
ARITH = {"+": 1, "-": 1, "*": 2}


class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i]

    def eat(self, val=None):
        tok = self.t[self.i]
        if val is not None and tok[1] != val:
            raise SyntaxError(f"'{val}' 가 와야 하는데 '{tok[1]}' 가 왔습니다 (토큰 {self.i})")
        self.i += 1
        return tok

    def program(self):
        body = []
        while self.peek()[0] != "eof":
            body.append(self.stmt())
        return body

    def block(self):
        self.eat("{")
        body = []
        while self.peek()[1] != "}":
            body.append(self.stmt())
        self.eat("}")
        return body

    def stmt(self):
        kind, val = self.peek()
        nxt = self.t[self.i + 1][1]
        if val in ("운영업무", "결재") and nxt == "(":          # while / if
            self.eat(); self.eat("(")
            cond = self.expr(); self.eat(")")
            body = self.block()
            if val == "운영업무":
                return ("while", cond, body)
            orelse = []
            if self.peek()[1] == "반려":                         # else
                self.eat(); orelse = self.block()
            return ("if", cond, body, orelse)
        if val == "퇴근" and nxt == "(":                         # break
            self.eat(); self.eat("("); self.eat(")")
            return ("break",)
        if kind == "name" and nxt == "=":                        # 대입
            self.eat(); self.eat("=")
            return ("assign", val, self.expr())
        return ("expr", self.expr())

    def expr(self):
        left = self.arith(0)
        if self.peek()[1] in CMP:
            op = self.eat()[1]
            left = ("cmp", op, left, self.arith(0))
        return left

    def arith(self, min_prec):
        left = self.atom()
        while self.peek()[1] in ARITH and ARITH[self.peek()[1]] > min_prec:
            op = self.eat()[1]
            left = ("bin", op, left, self.arith(ARITH[op]))
        return left

    def atom(self):
        kind, val = self.eat()
        if kind == "num":
            return ("const", int(val))
        if kind == "str":
            return ("const", val[1:-1])
        if val == "(":
            e = self.expr(); self.eat(")")
            return e
        if kind == "name":
            if val in CONST:
                return ("const", CONST[val])
            if self.peek()[1] == "(":                            # 함수 호출
                self.eat("(")
                args = []
                while self.peek()[1] != ")":
                    args.append(self.expr())
                    if self.peek()[1] == ",":
                        self.eat()
                self.eat(")")
                return ("call", BUILTIN.get(val, val), args)
            return ("name", val)
        raise SyntaxError(f"예상치 못한 토큰: {val!r}")


BUILTIN = {"출력해": "print"}   # 한글 이름 -> 파이썬 내장함수. 이게 우리 언어의 '표준 라이브러리'


# ───────────────────────── 3) codegen : 바이트코드를 손으로 조립 ─────────────────────────
CACHE = opcode._inline_cache_entries   # 3.14 : 명령어 뒤에 붙는 인라인 캐시 칸 수
OP = opcode.opmap
NB = {sym: i for i, (_, sym) in enumerate(dis._nb_ops)}
# 3.13+ COMPARE_OP 의 oparg = (비교종류 << 5) | 결과마스크 | 16(bool 로 변환)
CMP_MASK = {"<": 2, "<=": 10, "==": 8, "!=": 5, ">": 4, ">=": 12}
CMP_IDX = {s: i for i, s in enumerate(dis.cmp_op)}


class Label:
    pos = None


class Asm:
    def __init__(self):
        self.ins = []          # (opname, arg | Label)
        self.consts, self.names = [], []

    def emit(self, op, arg=0):
        self.ins.append((op, arg))

    def label(self, lb):
        self.ins.append(("LABEL", lb))

    def const(self, v):
        for i, c in enumerate(self.consts):   # True == 1 이라서 타입까지 비교
            if type(c) is type(v) and c == v:
                return i
        self.consts.append(v)
        return len(self.consts) - 1

    def name(self, n):
        if n not in self.names:
            self.names.append(n)
        return self.names.index(n)

    def assemble(self):
        # 패스 1: 라벨 위치 (코드 단위 = 2바이트) 계산
        pc = 0
        for op, arg in self.ins:
            if op == "LABEL":
                arg.pos = pc
            else:
                pc += 1 + CACHE.get(op, 0)
        # 패스 2: 바이트로 인코딩
        out, pc = bytearray(), 0
        for op, arg in self.ins:
            if op == "LABEL":
                continue
            end = pc + 1 + CACHE.get(op, 0)
            if isinstance(arg, Label):
                # 3.12+ 점프는 '다음 명령어 기준' 상대값. 뒤로 가는 건 JUMP_BACKWARD 전용
                arg = end - arg.pos if op == "JUMP_BACKWARD" else arg.pos - end
            assert 0 <= arg < 256, "EXTENDED_ARG 는 안 만들었다 (데모라서)"
            out += bytes([OP[op], arg]) + b"\x00\x00" * CACHE.get(op, 0)
            pc = end
        return bytes(out)


def gen(prog):
    a = Asm()
    loops = []                       # 중첩 루프의 '끝' 라벨 스택 (퇴근 = break)

    def expr(e):
        k = e[0]
        if k == "const":
            a.emit("LOAD_CONST", a.const(e[1]))
        elif k == "name":
            a.emit("LOAD_NAME", a.name(e[1]))
        elif k == "bin":
            expr(e[2]); expr(e[3])
            a.emit("BINARY_OP", NB[e[1]])
        elif k == "cmp":
            expr(e[2]); expr(e[3])
            a.emit("COMPARE_OP", (CMP_IDX[e[1]] << 5) | CMP_MASK[e[1]] | 16)
        elif k == "call":
            a.emit("LOAD_NAME", a.name(e[1]))
            a.emit("PUSH_NULL")      # 3.11+ 호출 규약 : [함수, NULL, 인자들...]
            for arg in e[2]:
                expr(arg)
            a.emit("CALL", len(e[2]))

    def cond_jump_if_false(cond, target):
        expr(cond)
        if cond[0] != "cmp":         # 비교는 이미 bool, 나머지는 bool 로 바꿔야 점프 가능
            a.emit("TO_BOOL")
        a.emit("POP_JUMP_IF_FALSE", target)
        a.emit("NOT_TAKEN")

    def stmt(s):
        k = s[0]
        if k == "expr":
            expr(s[1]); a.emit("POP_TOP")
        elif k == "assign":
            expr(s[2]); a.emit("STORE_NAME", a.name(s[1]))
        elif k == "break":
            if not loops:
                raise SyntaxError("퇴근은 운영업무 안에서만 가능합니다")
            a.emit("JUMP_FORWARD", loops[-1])
        elif k == "while":
            top, end = Label(), Label()
            a.label(top)
            cond_jump_if_false(s[1], end)
            loops.append(end)
            for x in s[2]: stmt(x)
            loops.pop()
            a.emit("JUMP_BACKWARD", top)
            a.label(end)
        elif k == "if":
            els, end = Label(), Label()
            cond_jump_if_false(s[1], els)
            for x in s[2]: stmt(x)
            if s[3]:
                a.emit("JUMP_FORWARD", end)
            a.label(els)
            for x in s[3]: stmt(x)
            a.label(end)

    a.emit("RESUME", 0)
    for s in prog:
        stmt(s)
    a.emit("LOAD_CONST", a.const(None))
    a.emit("RETURN_VALUE")
    return a


def make_code(asm, filename):
    return types.CodeType(
        0, 0, 0, 0,                      # argcount, posonly, kwonly, nlocals
        16,                              # stacksize (데모라 넉넉히)
        0,                               # flags (모듈 레벨)
        asm.assemble(),                  # ★ 우리가 만든 바이트코드
        tuple(asm.consts), tuple(asm.names), (),
        filename, "<업무>", "<업무>",
        1, b"", b"", (), (),             # firstlineno, linetable, exceptiontable, freevars, cellvars
    )


def write_pyc(code, path):
    # pyc 헤더 16바이트 : 매직넘버(버전) + 플래그 + (mtime, size) 자리. 그 뒤가 marshal 직렬화된 code 객체
    header = importlib.util.MAGIC_NUMBER + struct.pack("<III", 0, 0, 0)
    Path(path).write_bytes(header + marshal.dumps(code))


def build(src_path):
    src = Path(src_path)
    code = make_code(gen(Parser(lex(src.read_text(encoding="utf-8"))).program()), src.name)
    out = src.with_suffix(".pyc")
    write_pyc(code, out)
    return out


def load_pyc(path):
    return marshal.loads(Path(path).read_bytes()[16:])


if __name__ == "__main__":
    cmd, target = (sys.argv[1:] + [None, None])[:2]
    if cmd == "build":
        out = build(target)
        print(f"{target} -> {out} ({out.stat().st_size} bytes)")
    elif cmd == "dis":
        dis.dis(load_pyc(target))
    elif cmd == "run":
        out = build(target)
        print(f"$ python {out}")
        subprocess.run([sys.executable, str(out)], check=True)
    else:
        print(__doc__)
