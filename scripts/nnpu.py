# -*- coding: utf-8 -*-
"""nnPU (non-negative Positive-Unlabeled) 학습 — numpy 구현.

출처: Kiryo, Niu, du Plessis, Sugiyama,
      "Positive-Unlabeled Learning with Non-Negative Risk Estimator",
      NIPS 2017, pp. 1675-1685.

왜 이게 필요한가 —
우리는 천연물 배경을 '음성(negative)'으로 라벨링해 학습시켰다. 그런데 사실
그 분자들은 '미분류(unlabeled)'다. 아무도 HSD17B13에 시험해 본 적이 없을 뿐이다.
음성으로 단정하면 모델에게 "천연물은 비활성"이라고 가르치는 셈이고, 실제로
30번 스크리닝에서 전체의 99.97%가 0.25 미만으로 눌렸다.

nnPU는 그 가정을 손실함수 수준에서 고친다.

  비편향 PU 위험(uPU):
      R_pu(g) = pi_p * R_p^+(g) + [ R_u^-(g) - pi_p * R_p^-(g) ]

  두 번째 대괄호는 이론상 pi_n * R_n^-(g) >= 0 이어야 하는데, 표본에서는
  음수가 될 수 있다. 모델이 유연하면 그쪽으로 끝없이 내려가며 과적합한다.
  (논문 Figure 1b: uPU의 훈련 위험이 음수로 발산하고 시험 위험이 치솟는다)

  nnPU는 거기에 0으로 바닥을 깐다 (논문 식 (6)):
      R~_pu(g) = pi_p * R_p^+(g) + max{ 0, R_u^-(g) - pi_p * R_p^-(g) }

  즉 "미분류 데이터를 전부 음성 취급하는 방향으로는 더 못 내려간다".

손실은 논문 권장대로 시그모이드 손실을 쓴다.
      l_sig(z) = 1 / (1 + exp(z)),  z = g(x) * y
기울기가 어디서나 0이 아니어서 일반 경사법으로 풀린다.

Algorithm 1 (미니배치):
      r_i = R_u^-(g; X_u^i) - pi_p * R_p^-(g; X_p^i)
      r_i >= -beta  이면  정상 기울기로 갱신
      r_i <  -beta  이면  -grad(r_i) 방향으로 step을 gamma배 줄여 갱신
      권장값 beta=0, gamma=1 (논문 Figure 1 설정)

모델은 논문과 같은 꼴의 MLP (d-100-1, ReLU)를 쓴다. torch가 설치돼 있지 않아
Adam까지 numpy로 직접 구현했다. 2048차원 x 수만 샘플 규모에서 충분히 돈다.
"""
import numpy as np


def sigmoid_loss(z):
    """l_sig(z) = 1/(1+exp(z)). z = g(x)*y 이므로 z가 클수록 손실이 작다."""
    return 1.0 / (1.0 + np.exp(np.clip(z, -60, 60)))


def sigmoid_loss_grad(z):
    """d l_sig / dz = -s(1-s), s = sigmoid(-z) = l_sig(z)."""
    s = sigmoid_loss(z)
    return -s * (1.0 - s)


class MLP:
    """d - h - 1 MLP (ReLU). 출력은 실수값 g(x) (로짓처럼 쓰되 손실은 시그모이드 손실)."""

    def __init__(self, d, h=100, seed=0):
        rng = np.random.default_rng(seed)
        self.W1 = rng.normal(0, np.sqrt(2.0 / d), (d, h))
        self.b1 = np.zeros(h)
        self.W2 = rng.normal(0, np.sqrt(2.0 / h), (h, 1))
        self.b2 = np.zeros(1)
        self.params = ["W1", "b1", "W2", "b2"]
        self._m = {p: np.zeros_like(getattr(self, p)) for p in self.params}
        self._v = {p: np.zeros_like(getattr(self, p)) for p in self.params}
        self._t = 0

    def forward(self, X):
        self._X = X
        self._a1 = X @ self.W1 + self.b1
        self._h1 = np.maximum(self._a1, 0.0)
        return (self._h1 @ self.W2 + self.b2).ravel()

    def backward(self, dout):
        """dout: dL/dg(x), 길이 n."""
        dout = dout.reshape(-1, 1)
        g = {}
        g["W2"] = self._h1.T @ dout
        g["b2"] = dout.sum(axis=0)
        dh = dout @ self.W2.T
        dh[self._a1 <= 0] = 0.0
        g["W1"] = self._X.T @ dh
        g["b1"] = dh.sum(axis=0)
        return g

    def step(self, grads, lr=1e-3, b1=0.9, b2=0.999, eps=1e-8):
        """Adam (Kingma & Ba 2015) — 논문이 외부 최적화기로 지정한 것."""
        self._t += 1
        for p in self.params:
            gp = grads[p]
            self._m[p] = b1 * self._m[p] + (1 - b1) * gp
            self._v[p] = b2 * self._v[p] + (1 - b2) * gp ** 2
            mh = self._m[p] / (1 - b1 ** self._t)
            vh = self._v[p] / (1 - b2 ** self._t)
            setattr(self, p, getattr(self, p) - lr * mh / (np.sqrt(vh) + eps))


def _risk_parts(model, Xp, Xu, pi_p):
    """R_p^+, R_p^-, R_u^- 와 각 항의 dL/dg 를 함께 돌려준다."""
    gp = model.forward(Xp)
    Rp_pos = sigmoid_loss(+gp).mean()          # y=+1
    Rp_neg = sigmoid_loss(-gp).mean()          # y=-1
    dRp_pos = sigmoid_loss_grad(+gp) / len(gp)
    dRp_neg = -sigmoid_loss_grad(-gp) / len(gp)
    hp = (model._X, model._a1, model._h1)

    gu = model.forward(Xu)
    Ru_neg = sigmoid_loss(-gu).mean()
    dRu_neg = -sigmoid_loss_grad(-gu) / len(gu)
    hu = (model._X, model._a1, model._h1)
    return (Rp_pos, Rp_neg, Ru_neg, dRp_pos, dRp_neg, dRu_neg, hp, hu, gp, gu)


def _grads_for(model, cache, dout):
    """forward 캐시를 복원해 backward 한 번 수행."""
    model._X, model._a1, model._h1 = cache
    return model.backward(dout)


def _add(a, b, s=1.0):
    return {k: a[k] + s * b[k] for k in a}


def fit_nnpu(Xp, Xu, pi_p, Xn=None, hidden=100, epochs=40, batch=512,
             lr=1e-4, beta=0.0, gamma=1.0, seed=0, verbose=True):
    """nnPU 학습.

    Xp : 양성(알려진 active)
    Xu : 미분류(천연물 라이브러리 표본) — 음성이 아니다
    Xn : 진짜 음성(실측 inactive). 있으면 PNU로 함께 쓴다.
    pi_p : 클래스 사전확률 = 미분류 중 진짜 양성의 비율. 추정해서 넣어야 한다.
    beta, gamma : 논문 Algorithm 1의 허용치와 step 감쇠. 권장 0, 1.
    """
    d = Xp.shape[1]
    model = MLP(d, hidden, seed)
    rng = np.random.default_rng(seed)
    np_, nu = len(Xp), len(Xu)
    nb = max(nu // batch, 1)
    hist = []

    for ep in range(epochs):
        ip = rng.permutation(np_)
        iu = rng.permutation(nu)
        tot, neg_batches = 0.0, 0
        for b in range(nb):
            pb = ip[(b * max(np_ // nb, 1)) % np_:][:max(np_ // nb, 1)]
            if len(pb) < 2:
                pb = rng.choice(np_, size=min(8, np_), replace=False)
            ub = iu[b * batch:(b + 1) * batch]
            if len(ub) < 2:
                continue
            xp, xu = Xp[pb], Xu[ub]

            (Rp_pos, Rp_neg, Ru_neg, dRp_pos, dRp_neg, dRu_neg,
             hp, hu, _, _) = _risk_parts(model, xp, xu, pi_p)

            r = Ru_neg - pi_p * Rp_neg          # 논문의 r_i
            if r >= -beta:
                # 정상 경로: grad( pi_p*Rp_pos + Ru_neg - pi_p*Rp_neg )
                gP = _grads_for(model, hp, pi_p * dRp_pos - pi_p * dRp_neg)
                gU = _grads_for(model, hu, dRu_neg)
                grads = _add(gP, gU)
                step_lr = lr
                tot += pi_p * Rp_pos + r
            else:
                # 음수로 내려간 미니배치: -grad(r) 방향, step 감쇠
                gP = _grads_for(model, hp, +pi_p * dRp_neg)
                gU = _grads_for(model, hu, -dRu_neg)
                grads = _add(gP, gU)
                step_lr = lr * gamma
                neg_batches += 1
                tot += pi_p * Rp_pos

            # 진짜 음성이 있으면 보통의 지도학습 항으로 더한다 (PNU)
            if Xn is not None and len(Xn):
                nbidx = rng.choice(len(Xn), size=min(batch // 4, len(Xn)), replace=False)
                gn = model.forward(Xn[nbidx])
                dn = -sigmoid_loss_grad(-gn) / len(gn)
                hn = (model._X, model._a1, model._h1)
                grads = _add(grads, _grads_for(model, hn, dn))

            model.step(grads, lr=step_lr)

        hist.append({"epoch": ep + 1, "risk": tot / nb, "clamped_batches": neg_batches})
        if verbose and (ep + 1) % 5 == 0:
            print(f"    epoch {ep+1:3d}  위험 {tot/nb:+.4f}  "
                  f"바닥에 닿은 미니배치 {neg_batches}/{nb}")
    model.history = hist
    return model


def predict_score(model, X, batch=20000):
    out = []
    for i in range(0, len(X), batch):
        out.append(model.forward(X[i:i + batch]))
    return np.concatenate(out)
