# -*- coding: utf-8 -*-
"""HSD17B13 실측 화합물의 RDKit descriptor(217종)로 분류모델을 학습하고,
어떤 물성(descriptor)이 활성과 연관되는지 feature importance로 해석한다.

- 학습 데이터: 실측 active/inactive만 (decoy 제외 — 물성 해석은 진짜 데이터로)
- 모델: LightGBM (트리 기반 → 스케일 불필요, gain importance로 해석)
- dedup: 같은 물질(canonical)은 하나로 (label=하나라도 active면 active)
- 결과: 중요 descriptor 상위 + active/inactive 평균 비교(방향)까지

출력:
  data/HSD17B13_descriptor_importance.csv
  data/HSD17B13_descriptor_model.pkl   (SimpleImputer+LGBM Pipeline — 신규 예측 시 그대로 적용)
"""
import numpy as np
import pandas as pd
import pickle
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import (roc_auc_score, average_precision_score,
                             confusion_matrix)
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from lightgbm import LGBMClassifier

SRC = "data/HSD17B13_descriptors.csv"
IMP_OUT = "data/HSD17B13_descriptor_importance.csv"
MODEL_OUT = "data/HSD17B13_descriptor_model.pkl"
META = ["canonical_smiles", "ic50_nM", "relation", "sources", "label"]

df = pd.read_csv(SRC)
df = df.dropna(subset=["label"]).copy()
desc_cols = [c for c in df.columns if c not in META]

# ---------- 물질(canonical) 단위 dedup: 같은 구조는 descriptor 동일 → 첫 행, 라벨은 max ----------
agg = {c: "first" for c in desc_cols}
agg["label"] = "max"
comp = df.groupby("canonical_smiles").agg(agg).reset_index()
comp["label"] = comp["label"].astype(int)

X = comp[desc_cols].replace([np.inf, -np.inf], np.nan)
y = comp["label"].to_numpy()
print(f"물질 {len(comp)}개 | active {int(y.sum())} / inactive {int((y==0).sum())} "
      f"| descriptor {len(desc_cols)}종")

# ---------- 5-fold CV (트리 → 스케일 불필요, 결측만 median 대체) ----------
pipe = Pipeline([
    ("impute", SimpleImputer(strategy="median")),
    ("clf", LGBMClassifier(n_estimators=400, class_weight="balanced",
                           random_state=42, n_jobs=-1, verbosity=-1)),
])
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
proba = cross_val_predict(pipe, X, y, cv=skf, method="predict_proba", n_jobs=-1)[:, 1]
pred = (proba >= 0.5).astype(int)
tn, fp_, fn, tp = confusion_matrix(y, pred).ravel()
print("\n=== descriptor 모델 5-fold CV ===")
print(f"ROC-AUC {roc_auc_score(y, proba):.3f} | PR-AUC {average_precision_score(y, proba):.3f} "
      f"| Recall(act) {tp/(tp+fn):.3f} | Prec(act) {tp/(tp+fp_):.3f}")
print("(참고: fingerprint 모델(실측데이터)은 ROC-AUC ~0.90)")

# ---------- 전체 학습 → 중요도 + 방향 해석 ----------
pipe.fit(X, y)
imp = pipe.named_steps["clf"].feature_importances_   # gain 아님, split 기반 → gain으로 재계산
booster = pipe.named_steps["clf"].booster_
gain = booster.feature_importance(importance_type="gain")

Xf = pipe.named_steps["impute"].transform(X)
Xf = pd.DataFrame(Xf, columns=desc_cols)
act_mean = Xf[y == 1].mean()
ina_mean = Xf[y == 0].mean()
pooled = Xf.std().replace(0, np.nan)
cohen = (act_mean - ina_mean) / pooled          # 표준화 효과크기(방향+세기)

res = pd.DataFrame({
    "descriptor": desc_cols,
    "gain_importance": gain,
    "active_mean": act_mean.values,
    "inactive_mean": ina_mean.values,
    "std_effect": cohen.values,               # +면 active에서 높음
}).sort_values("gain_importance", ascending=False).reset_index(drop=True)
res.to_csv(IMP_OUT, index=False)

with open(MODEL_OUT, "wb") as f:
    pickle.dump({"pipeline": pipe, "desc_cols": desc_cols}, f)

print(f"\n=== 활성과 가장 연관된 물성(중요도) 상위 20 ===")
print(f"{'descriptor':22s} {'중요도':>10s} {'active평균':>11s} {'inact평균':>11s} {'방향':>6s}")
for _, r in res.head(20).iterrows():
    arrow = "↑active" if r.std_effect > 0 else "↓active"
    print(f"{r.descriptor:22s} {r.gain_importance:10.0f} "
          f"{r.active_mean:11.2f} {r.inactive_mean:11.2f} {arrow:>7s}")

print(f"\n저장: {IMP_OUT} | {MODEL_OUT}")
print("주의: descriptor끼리 상관 높으면 중요도가 서로 나뉘어 과소평가될 수 있음 → 방향(std_effect)과 함께 해석")
