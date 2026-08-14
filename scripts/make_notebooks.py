# -*- coding: utf-8 -*-
"""scripts/의 파이프라인 .py들을 notebooks/의 .ipynb로 변환한다.

셀 분리 규칙:
  - 파일 맨 위 docstring → 제목/설명 마크다운 셀
  - 최상위 섹션 헤더 주석(`# ---- 제목 ----`, `# ==== ====`) → 마크다운 설명 셀
  - 그 사이 코드 → 코드 셀 (함수 내부 주석은 그대로 유지)
  - 첫 코드 셀 앞에 '프로젝트 루트로 이동' 셋업 셀 삽입(상대경로 data/... 동작 보장)

의존성 없이 .ipynb(JSON)를 직접 생성. 재실행하면 최신 .py 기준으로 다시 만듦.
"""
import os
import re
import ast
import json
import glob

OUTDIR = "notebooks"
os.makedirs(OUTDIR, exist_ok=True)
SECTION = re.compile(r"^#.*(-{3,}|={3,})")   # 최상위 섹션 헤더(들여쓰기 없음)

SETUP = ("# 노트북을 어느 폴더에서 열든 프로젝트 루트에서 실행되도록 이동\n"
         "import os\n"
         "if not os.path.isdir('data') and os.path.basename(os.getcwd()) in ('notebooks', 'scripts'):\n"
         "    os.chdir('..')\n"
         "print('작업 폴더:', os.getcwd())")


def md_cell(text):
    return {"cell_type": "markdown", "metadata": {},
            "source": text.splitlines(keepends=True)}


def code_cell(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": text.rstrip("\n").splitlines(keepends=True)}


def clean_header(line):
    return line.lstrip("#").strip().strip("-=").strip()


def convert(path, outdir=OUTDIR):
    src = open(path, encoding="utf-8").read()
    lines = src.splitlines()
    # 1) docstring → 제목 마크다운
    tree = ast.parse(src)
    doc = ast.get_docstring(tree)
    first = tree.body[0] if tree.body else None
    doc_end = (first.end_lineno if (isinstance(first, ast.Expr)
               and isinstance(getattr(first, "value", None), ast.Constant)
               and isinstance(first.value.value, str)) else 0)
    base = os.path.basename(path)
    title = f"# {base}\n\n"
    if doc:
        title += doc.strip()
    cells = [md_cell(title), code_cell(SETUP)]

    body = lines[doc_end:]
    # 최상위 `if __name__ == "__main__":` 블록은 노트북에서 argparse가 깨지므로 잘라내고
    # 뒤에 안전한(주석 처리된) 실행 예시 셀로 대체한다.
    has_main = False
    for k, ln in enumerate(body):
        if ln.startswith("if __name__"):
            body = body[:k]
            has_main = True
            break
    i, n = 0, len(body)
    buf = []

    def flush_code():
        text = "\n".join(buf).strip("\n")
        if text.strip():
            cells.append(code_cell(text))
        buf.clear()

    while i < n:
        line = body[i]
        # 최상위 주석(들여쓰기 없이 '#'로 시작) → 마크다운 셀로 분리
        if line.startswith("#"):
            flush_code()
            is_hdr = bool(SECTION.match(line))
            md = [clean_header(line) if is_hdr else line.lstrip("#").strip()]
            i += 1
            while i < n and body[i].startswith("#"):
                md.append(body[i].lstrip("#").strip())
                i += 1
            head = md[0]
            rest = "\n".join(md[1:])
            cells.append(md_cell(f"### {head}" + (f"\n\n{rest}" if rest else "")
                                 if is_hdr else "\n".join(md)))
        else:
            buf.append(line)
            i += 1
    flush_code()

    if has_main:
        cells.append(md_cell(
            "### 노트북에서 실행하기\n\n"
            "원본의 `argparse` 기반 `main()`은 CLI 전용이라 노트북에선 아래처럼 "
            "`run_pipeline`을 직접 호출한다. (자동 실행되지 않도록 주석 처리)"))
        cells.append(code_cell(
            "# cfg = Config(target=\"HSD17B13\")\n"
            "# run_pipeline(cfg)\n"
            "#\n"
            "# 주의: 이 스캐폴드는 ChEMBL API 자동수집을 시도한다(현재 불안정).\n"
            "# 신뢰가능한 HSD17B13 파이프라인은 scripts/(01~16) 노트북을 사용."))

    nb = {"cells": cells,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                      "name": "python3"},
                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 4}   # minor 4: 셀 id 불필요(호환성)
    out = os.path.join(outdir, base[:-3] + ".ipynb")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    return out, len(cells)


targets = sorted(p for p in glob.glob("scripts/*.py")
                 if re.match(r"\d", os.path.basename(p)))   # 번호로 시작하는 파이프라인만
if os.path.exists("bioai_test.py"):
    targets.append("bioai_test.py")   # 루트의 올인원 스캐폴드도 포함
print(f"변환 대상 {len(targets)}개 → {OUTDIR}/")
for p in targets:
    # 루트의 올인원 스캐폴드(bioai_test)는 루트에, 나머지는 notebooks/에
    outdir = "." if os.path.basename(p) == "bioai_test.py" else OUTDIR
    out, ncell = convert(p, outdir)
    print(f"  {os.path.basename(p):28s} → {out:38s} ({ncell} cells)")
print("완료")
