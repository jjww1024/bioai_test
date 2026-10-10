# -*- coding: utf-8 -*-
"""파이프라인 공용 경로 도우미 — 산출 파일 이름 앞에 YYMMDD 스탬프를 붙인다.

왜 필요한가
-----------
파이프라인을 다시 돌릴 때마다 같은 이름으로 덮어쓰면 "지금 이 파일이 언제 만든 건지"를
파일명만 보고 알 수 없다. 그래서 **쓸 때는 스탬프를 붙이고(`out`), 읽을 때는 스탬프가
가장 큰(=최신) 파일을 자동으로 고른다(`latest`)**.

    data/processed/train_1to1.csv  →  data/processed/261010_train_1to1.csv

쓰는 법
-------
노트북 맨 위(루트 이동 직후)에서:

    import sys; sys.path.insert(0, "notebooks/pipeline")
    from _paths import STAMP, out, latest

그 다음 경로는 이렇게 쓴다:

    SRC = latest("data/processed/train_1to1.csv")   # 읽기 → 최신 스탬프본 자동 선택
    OUT = out("data/processed/HSD17B13_1to1_3d_descriptors.csv")   # 쓰기 → 오늘 스탬프

파이프라인을 새로 돌릴 때
-------------------------
아래 `STAMP` 한 줄만 새 날짜로 바꾸면 **전 노트북에 동시에 반영**된다.
(노트북별로 따로 적지 않으므로 스탬프가 서로 엇갈릴 일이 없다.)
이전 결과는 옛 스탬프 이름으로 그대로 남고, `latest()`는 항상 최신본을 집는다.
"""
import os
import re
import glob

# ===== 여기만 바꾸면 전 파이프라인에 적용 (YYMMDD) =====
STAMP = "261010"

_STAMPED = re.compile(r"^(\d{6})_(.+)$")   # '261010_name.csv' → ('261010', 'name.csv')


def _split(path):
    """경로를 (디렉터리, 스탬프 없는 파일명)으로 분해."""
    d, b = os.path.split(str(path).replace("\\", "/"))
    m = _STAMPED.match(b)
    if m:
        b = m.group(2)                     # 이미 스탬프가 붙어 있으면 떼어낸다
    return d, b


def out(path, stamp=None):
    """쓰기용 경로. 파일명 앞에 스탬프를 붙인다.

    >>> out("data/processed/train_1to1.csv")
    'data/processed/261010_train_1to1.csv'
    """
    d, b = _split(path)
    name = f"{stamp or STAMP}_{b}"
    return f"{d}/{name}" if d else name


def latest(path, stamp=None):
    """읽기용 경로. 같은 이름의 스탬프 파일 중 **가장 최신**을 돌려준다.

    - `stamp`를 주면 그 스탬프본을 (있으면) 그대로 집는다.
    - 스탬프 파일이 하나도 없으면 스탬프 없는 원본 경로를 돌려준다
      (WEKA 선택본처럼 손으로 만든 고정 파일용).
    """
    d, b = _split(path)
    dd = d or "."
    if stamp:
        p = f"{dd}/{stamp}_{b}"
        if os.path.exists(p):
            return p
    cands = [p.replace("\\", "/") for p in glob.glob(f"{dd}/" + "[0-9]" * 6 + f"_{b}")]
    if cands:
        return max(cands, key=lambda p: _STAMPED.match(os.path.basename(p)).group(1))
    return f"{d}/{b}" if d else b


def which(path):
    """진단용: 그 이름으로 존재하는 모든 스탬프본을 최신순으로 나열."""
    d, b = _split(path)
    dd = d or "."
    cands = [p.replace("\\", "/") for p in glob.glob(f"{dd}/" + "[0-9]" * 6 + f"_{b}")]
    plain = f"{dd}/{b}"
    if os.path.exists(plain):
        cands.append(plain.replace("./", ""))
    return sorted(cands, reverse=True)
