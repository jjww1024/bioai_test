// Cockroft 2019 (STarFish) 강의 노트 (docx)
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  LevelFormat, PageBreak,
} = require("docx");

const OUT = "C:\\Users\\jjww1\\Desktop\\claude code\\bioai_test\\docs\\논문정리\\261124_Shen2023_USP7_강의노트.docx";
const KO = "맑은 고딕";
const W = 9000;              // 본문 폭 (DXA)
const PETROL = "0B3C49", TEAL = "0E7C7B", RED = "A8452C", GRAY = "595959";
const LIGHT = "EDF3F4", WARM = "FBF3E4";

const kids = [];
const push = (...x) => x.forEach((y) => kids.push(y));

// 번호 목록이 장을 넘어가며 누적되지 않도록, 연속된 N() 만 같은 인스턴스를 쓴다
let _ni = 0, _lastN = false;
const _mark = () => { _lastN = false; };

// ── 헬퍼 ────────────────────────────────────────────────
const P = (text, o = {}) => {
  _mark();
  return new Paragraph({
    spacing: { before: o.before ?? 0, after: o.after ?? 120, line: o.line ?? 300 },
    alignment: o.align,
    indent: o.indent,
    children: [new TextRun({ text, size: o.size ?? 21, bold: o.bold, italics: o.it,
                             color: o.color ?? "1F1F1F", font: KO })],
  });
};

const RUNS = (parts, o = {}) => {
  _mark();
  return new Paragraph({
    spacing: { before: o.before ?? 0, after: o.after ?? 120, line: o.line ?? 300 },
    indent: o.indent,
    children: parts.map((p) =>
      new TextRun({ text: p[0], bold: p[1] === "b", italics: p[1] === "i",
                    color: p[2] ?? "1F1F1F", size: o.size ?? 21, font: KO })),
  });
};

const B = (text, lvl = 0, o = {}) => {
  _mark();
  return new Paragraph({
    numbering: { reference: "bul", level: lvl },
    spacing: { before: 0, after: o.after ?? 60, line: 300 },
    children: [new TextRun({ text, size: o.size ?? 21, color: o.color ?? "1F1F1F",
                             bold: o.bold, font: KO })],
  });
};

const N = (text, o = {}) => {
  if (!_lastN) _ni++;
  _lastN = true;
  return new Paragraph({
    numbering: { reference: "num", level: 0, instance: _ni },
    spacing: { before: 0, after: o.after ?? 60, line: 300 },
    children: [new TextRun({ text, size: 21, color: "1F1F1F", font: KO })],
  });
};

const H1 = (t) => { _mark(); return new Paragraph({ text: t, heading: HeadingLevel.HEADING_1 }); };
const H2 = (t) => { _mark(); return new Paragraph({ text: t, heading: HeadingLevel.HEADING_2 }); };
const H3 = (t) => { _mark(); return new Paragraph({ text: t, heading: HeadingLevel.HEADING_3 }); };

const GAP = (n = 120) => { _mark(); return new Paragraph({ spacing: { after: n }, children: [] }); };

// 음영 박스 (여러 줄)
const BOX = (title, lines, fill = LIGHT, bar = TEAL) => {
  _mark();
  const rows = [];
  const inner = [];
  if (title) inner.push(new Paragraph({
    spacing: { after: 70, line: 290 },
    children: [new TextRun({ text: title, bold: true, size: 20, color: PETROL, font: KO })],
  }));
  lines.forEach((ln, i) => inner.push(new Paragraph({
    spacing: { after: i === lines.length - 1 ? 0 : 60, line: 290 },
    children: [new TextRun({ text: ln, size: 20, color: "1F1F1F", font: KO })],
  })));
  rows.push(new TableRow({
    cantSplit: true,
    children: [
      new TableCell({
        width: { size: 60, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: bar },
        margins: { top: 0, bottom: 0, left: 0, right: 0 },
        children: [new Paragraph({ children: [] })],
      }),
      new TableCell({
        width: { size: W - 60, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill },
        margins: { top: 140, bottom: 140, left: 220, right: 180 },
        children: inner,
      }),
    ],
  }));
  return new Table({
    columnWidths: [60, W - 60],
    width: { size: W, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
      left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE },
    },
    rows,
  });
};

// 일반 표
const TBL = (header, rows, widths) => {
  _mark();
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (txt, i, head, alt) =>
    new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: head ? PETROL : (alt ? LIGHT : "FFFFFF") },
      margins: { top: 90, bottom: 90, left: 150, right: 120 },
      children: String(txt).split("¶").map((line, k) => new Paragraph({
        spacing: { after: 0, line: 280 },
        children: [new TextRun({ text: line, size: 19, bold: head,
                                 color: head ? "FFFFFF" : "1F1F1F", font: KO })],
      })),
    });
  const trs = [new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: header.map((h, i) => cell(h, i, true, false)),
  })];
  rows.forEach((r, ri) => trs.push(new TableRow({
    cantSplit: true,
    children: r.map((c, i) => cell(c, i, false, ri % 2 === 0)),
  })));
  return new Table({
    columnWidths: widths,
    width: { size: total, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: "C9D6D8" },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: "C9D6D8" },
      left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "DEE7E8" },
      insideVertical: { style: BorderStyle.NONE },
    },
    rows: trs,
  });
};

// 원문 대조표
const CMP = (pairs) => TBL(["논문 원문 표현", "뜻"], pairs, [3700, 5300]);
const SYM = (pairs) => TBL(["기호", "읽는 법 · 뜻"], pairs, [2200, 6800]);


// ════════════════════════════════════════════════ 표지
push(
  GAP(1400),
  new Paragraph({
    spacing: { after: 100 },
    children: [new TextRun({ text: "강의 노트", size: 26, color: TEAL, bold: true, font: KO })],
  }),
  new Paragraph({
    spacing: { after: 60 },
    children: [new TextRun({ text: "다중표현 융합", size: 48, bold: true, color: PETROL, font: KO })],
  }),
  new Paragraph({
    spacing: { after: 240 },
    children: [new TextRun({ text: "표현과 모델을 전수 비교하면 무엇이 보이는가", size: 29, bold: true, color: PETROL, font: KO })],
  }),
  new Paragraph({
    spacing: { after: 400 },
    border: { top: { style: BorderStyle.SINGLE, size: 12, color: "E0A033", space: 1 } },
    children: [],
  }),
  P("Shen, Tang, Li, Li & Chen (2023)", { size: 24, bold: true }),
  P("Multimodal data fusion for supervised learning-based identification of USP7 inhibitors: a systematic comparison", { size: 21, color: GRAY }),
  P("Journal of Cheminformatics 15:5  ·  doi 10.1186/s13321-022-00675-8  ·  PMC9835315  ·  CC BY 4.0", { size: 20, color: GRAY }),
  GAP(300),
  B("제1저자 공동 — Wen-feng Shen, He-wei Tang"),
  B("투고 2022-07-13  ·  게재 확정 2022-11-26  ·  온라인 2023-01-11"),
  GAP(120),
  P("Journal of Cheminformatics는 완전 공개 학술지입니다. BMC 사이트와 PMC 양쪽에서 무료로 읽을 수 있습니다.", { size: 20, color: GRAY }),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 읽는 법
push(
  H1("이 문서를 읽는 법"),

  H2("한 문장으로"),
  P("USP7 억제제 분류 문제에서, 분자 표현 3종과 SMILES, 기계학습 9종과 딥러닝 2종, "
    + "불균형 처리 3종을 조합해 15개 실험으로 전수 비교한 논문입니다."),
  GAP(100),

  H2("먼저 솔직하게 — 이 논문은 우리 문제를 풀지 않습니다"),
  BOX(null, [
    "세 논문 중 우리에게 새로 준 것이 가장 적었습니다.",
    "",
    "이 논문이 푸는 문제 — \"같은 화학공간 안에서 최적 조합 찾기\"",
    "우리 문제 — \"다른 화학공간으로 넘어가기\"",
    "",
    "그래도 읽을 가치가 있었습니다. 세 가지 이유로요.",
  ], WARM, "E0A033"),
  GAP(100),
  N("우리가 이미 쓰고 있던 방법(군집 분할, 시드 반복)의 선례가 된다 — 인용 가치"),
  N("다중표현 융합이 때때로 돕는다는 것을 전수 비교로 확인해 준다"),
  N("'읽고 나서 새로 할 것이 없다'는 결론도 결론이다 — 그 확인에 드는 비용이 적었다"),
  GAP(140),

  H2("이 논문에서 우리가 확인한 것"),
  TBL(["이 논문의 요소", "우리 상태"], [
    ["군집 단위 분할", "Butina 군집 + 5겹 + 시드 5개로 이미 적용 중"],
    ["다중표현 조기 융합", "ECFP4+FCFP4 결합은 적용. 물성 descriptor는 아직 미융합"],
    ["SMOTE 과표본화", "class_weight='balanced'로 대응 중"],
    ["비편향 decoy (ZINC)", "PubChem decoy를 평가에도 썼다가 실패 — 교훈으로 반영"],
    ["SMILES 열거 증강", "미적용. 지문 기반이라 직접 이식 불가"],
    ["시드 30개 + t-검정", "시드 5개 + 짝지은 비교로 적용 중"],
  ], [3200, 5800]),
  GAP(140),

  H2("문서 구성"),
  TBL(["장", "내용"], [
    ["0장", "기초 — USP7·다중모달·PCA·SMOTE·평가지표 등 10개 절"],
    ["1장", "문제와 데이터 수집"],
    ["2장", "분자 표현 네 가지와 전처리"],
    ["3장", "군집 기반 분할"],
    ["4장", "모델 — ML 9종과 DL 2종"],
    ["5장", "불균형 처리 세 가지"],
    ["6장", "실험 설계와 난수 처리"],
    ["7장", "결과 — 기준값에 따라 승자가 바뀐다"],
    ["8장", "우리 과제와의 거리"],
    ["9장", "이 논문이 다루지 않는 것"],
    ["10장", "정리"],
    ["부록", "표현·수치·읽는 순서·점검표"],
  ], [900, 8100]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 0장
push(
  H1("0장.  먼저 알아야 할 것들"),

  H2("0-1.  USP7이란"),
  P("Ubiquitin-Specific Protease 7. 탈유비퀴틴화 효소(deubiquitinase)입니다."),
  GAP(60),
  TBL(["개념", "뜻"], [
    ["유비퀴틴화", "단백질에 유비퀴틴을 붙이는 것. 대개 '분해하라'는 표식"],
    ["탈유비퀴틴화", "그 표식을 떼는 것. 즉 분해를 막는다"],
    ["USP7의 역할", "MDM2를 안정화 → MDM2가 p53을 분해 → 결과적으로 p53 감소"],
    ["왜 항암 표적인가", "USP7을 막으면 p53이 회복돼 암세포가 죽는다"],
  ], [1800, 7200]),
  GAP(100),
  P("우리 HSD17B13과는 전혀 다른 단백질입니다. 이 논문에서 USP7은 "
    + "'분류 과제의 예시'일 뿐이고, 방법론이 본체입니다."),
  GAP(140),

  H2("0-2.  모달리티(modality)와 다중모달"),
  P("모달리티는 '데이터의 종류·형식'입니다. 같은 분자라도 여러 방식으로 표현할 수 있습니다."),
  GAP(60),
  TBL(["모달리티", "데이터 성격", "예"], [
    ["서열 데이터", "1차원 문자열", "SMILES"],
    ["연속값 데이터", "실수 벡터", "물리화학 descriptor 208종"],
    ["비트 벡터", "0/1 이진 벡터", "ECFP4 (2048 bit), MACCS (166 bit)"],
  ], [2000, 2600, 4400]),
  GAP(100),
  P("다중모달 융합은 이 셋을 함께 쓰는 것입니다. 각 표현이 서로 다른 정보를 담고 있으니 "
    + "합치면 나아질 것이라는 기대입니다."),
  GAP(140),

  H2("0-3.  조기 융합과 후기 융합"),
  TBL(["방식", "언제 합치나", "이 논문"], [
    ["조기 융합 (early fusion)", "모델에 넣기 전에 특징 벡터를 이어붙인다", "이것을 씀"],
    ["후기 융합 (late fusion)", "각 표현으로 따로 모델을 만들고 예측을 합친다", "쓰지 않음"],
  ], [2600, 4600, 1800]),
  GAP(100),
  P("우리가 쓰는 ECFP4+FCFP4 결합(2048차원)도 조기 융합입니다."),
  GAP(140),

  H2("0-4.  차원 축소 — PCA"),
  P("주성분 분석. 고차원 데이터를 분산이 큰 방향 몇 개로 투영해 차원을 줄입니다."),
  GAP(60),
  BOX("왜 이 논문이 PCA를 썼나", [
    "물성 194차원, MACCS 166비트, ECFP4 2048비트 — 모두 희소(sparse)합니다.",
    "대부분의 값이 0이거나 분산이 거의 없습니다.",
    "",
    "각각을 128차원으로 줄이면 —",
    "· 세 표현의 차원이 같아져 융합할 때 한쪽이 지배하지 않는다",
    "· 계산량이 준다",
    "· 희소성에서 오는 학습 불안정이 완화된다",
  ], LIGHT, TEAL),
  GAP(100),
  P("단점도 있습니다. PCA는 비트 하나하나의 화학적 의미를 섞어 버리므로, "
    + "'어떤 부분구조가 중요했나'를 해석할 수 없게 됩니다. "
    + "우리는 LightGBM이 희소 데이터를 직접 다룰 수 있어 PCA를 쓰지 않았습니다."),
  GAP(140),

  H2("0-5.  StandardScaler — 정규화"),
  P("각 특징의 평균을 0, 표준편차를 1로 맞춥니다."),
  GAP(60),
  P("논문의 표현 — \"서로 다른 척도로 측정된 특징들은 모델 적합에 동등하게 기여하지 못하고 "
    + "편향을 만들 수 있다.\" 분자량(수백)과 logP(한 자리) 같은 것이 섞여 있으면 "
    + "거리 기반 모델이 분자량에만 끌려갑니다."),
  GAP(60),
  P("트리 기반 모델(RF, GBDT, LightGBM)은 분할 기준만 쓰므로 척도에 둔감합니다. "
    + "우리가 정규화를 안 해도 됐던 이유입니다."),
  GAP(140),

  H2("0-6.  클래스 불균형과 SMOTE"),
  P("양성과 음성의 수가 크게 차이 나면 모델이 다수 클래스로 쏠립니다."),
  GAP(60),
  TBL(["대처법", "원리", "장단점"], [
    ["과표본화 (SMOTE)", "소수 클래스 샘플 사이를 보간해¶새 샘플을 합성한다", "데이터를 안 버린다.¶가짜 샘플이 생긴다"],
    ["과소표본화", "다수 클래스에서 일부만 쓴다", "정보를 버린다"],
    ["가중치 조정", "손실 계산 시 소수 클래스에 큰 가중치", "데이터를 안 건드린다.¶우리가 쓰는 방법"],
    ["decoy 추가", "외부 DB에서 음성으로 쓸 분자를 가져온다", "현실적이지만¶'진짜 음성'인지 모른다"],
  ], [2000, 3800, 3200]),
  GAP(140),

  H2("0-7.  SMILES 열거 (enumeration)"),
  P("같은 분자를 서로 다른 SMILES 문자열로 쓸 수 있다는 점을 이용한 데이터 증강입니다."),
  GAP(60),
  BOX("예", [
    "에탄올은 CCO 로도, OCC 로도, C(C)O 로도 쓸 수 있습니다.",
    "분자는 하나인데 문자열은 여럿입니다.",
    "",
    "SMILES를 입력으로 받는 모델(LSTM 등)에는 이것이 서로 다른 샘플로 보입니다.",
    "그래서 음성 656개에서 2,692개의 새 '샘플'을 만들 수 있었습니다.",
    "",
    "단 — 지문 기반 모델에는 쓸 수 없습니다. 어떤 SMILES로 쓰든 ECFP4는 같으니까요.",
    "우리가 이 기법을 가져오지 못하는 이유입니다.",
  ], LIGHT, TEAL),
  GAP(140),

  H2("0-8.  평가 지표 세 가지"),
  TBL(["지표", "식·뜻", "주의"], [
    ["ACC (정확도)", "맞춘 비율", "불균형 데이터에서¶쉽게 속는다"],
    ["F1", "정밀도와 재현율의 조화평균", "양성 쪽에 초점"],
    ["AUC", "순위 매기기 능력.¶무작위 양성이 무작위 음성보다 위에 올 확률", "클래스 비율에 둔감"],
  ], [1700, 4600, 2700]),
  GAP(100),
  BOX("우리가 추가로 쓰는 지표", [
    "이 논문은 ACC·F1·AUC 셋만 씁니다.",
    "",
    "우리는 BEDROC(α=20)과 EF 1%를 더 씁니다 — 가상 스크리닝에서는",
    "'목록 맨 앞'이 중요하기 때문입니다. AUC는 목록 전체를 봐서 상위권 실패를 가립니다.",
    "Cockroft 2019에서 배운 점입니다.",
  ], WARM, "E0A033"),
  GAP(140),

  H2("0-9.  t-SNE"),
  P("고차원 데이터를 2차원으로 눌러 시각화하는 방법입니다. 가까운 점은 가깝게, "
    + "먼 점은 멀게 배치하려 합니다."),
  GAP(60),
  P("논문은 t-SNE로 활성 기준값별 화학공간 분포를 그렸습니다 (Figure 5). "
    + "0.5 µM에서는 양성·음성이 뚜렷이 갈리고, 기준값이 커질수록 경계가 흐려집니다."),
  GAP(60),
  BOX("t-SNE를 읽을 때 주의", [
    "거리가 '보존되지 않습니다'. 군집의 크기와 군집 간 거리는 의미가 약합니다.",
    "'뭉쳐 있나 흩어져 있나' 정도만 읽는 것이 안전합니다.",
    "",
    "논문도 이것을 정량 근거가 아니라 '이론적으로 어려워진다'는 보조 설명으로 씁니다.",
  ], LIGHT, TEAL),
  GAP(140),

  H2("0-10.  이 논문의 약어"),
  SYM([
    ["USP7", "Ubiquitin-Specific Protease 7"],
    ["ML / DL", "기계학습 / 딥러닝"],
    ["SVC", "서포트 벡터 분류기"],
    ["RF", "랜덤 포레스트"],
    ["KNN", "k-최근접 이웃"],
    ["DT", "결정 트리"],
    ["GBDT", "경사 부스팅 결정 트리"],
    ["ABDT", "AdaBoost 결정 트리"],
    ["GNB", "가우시안 나이브 베이즈"],
    ["SGD", "확률적 경사하강 분류기"],
    ["LR", "로지스틱 회귀"],
    ["LSTM", "장단기 기억 신경망. 서열 데이터용"],
    ["self-attention", "자기주의. 서열 내 원소 간 관계를 학습"],
    ["SMOTE", "Synthetic Minority Over-sampling Technique"],
    ["PCA", "주성분 분석"],
    ["ACC / F1 / AUC", "정확도 / F1 점수 / ROC 곡선 아래 면적"],
    ["CHS / DBI / SC", "Calinski-Harabasz / Davies-Bouldin / 실루엣 — 군집 수 결정 지표"],
    ["Dtrain / Dval / Dtest", "학습 / 검증 / 시험 집합"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);


// ════════════════════════════════════════════════ 1장
push(
  H1("1장.  문제와 데이터"),

  H2("먼저 알아야 할 것"),
  P("저자의 출발점은 한 문장입니다 — \"USP7에 대해서는 전통적 가상 스크리닝의 정확도가 "
    + "충분하지 않다.\" 그래서 지도학습 분류기를 체계적으로 비교하기로 했습니다."),
  GAP(100),

  H2("차근차근"),
  H3("데이터 수집"),
  TBL(["항목", "내용"], [
    ["출처", "PubMed · ChEMBL 29 (CHEMBL2157850) · SciFinder"],
    ["접근일", "2021년 11월 13일"],
    ["활성값", "Ki · Kd · IC50 → 전부 µM로 환산"],
    ["수집 방식", "ChEMBL은 직접 내려받음.¶PubMed·SciFinder는 논문·특허를 찾아 수작업 정리"],
    ["중복 처리", "Open Babel 2.3.1 (2021-11-30 내려받음)로 고유 항목으로 통합"],
    ["규모", "USP7 리간드 약 4,000여 개"],
  ], [1800, 7200]),
  GAP(120),
  BOX("수작업 큐레이션", [
    "ChEMBL만 쓰지 않고 PubMed·SciFinder에서 수작업으로 보탰습니다.",
    "논문 표현 — \"이 데이터셋의 USP7 리간드는 신뢰할 수 있으며 데이터 출처까지 추적 가능하다.\"",
    "",
    "우리 HSD17B13 데이터도 ChEMBL + BindingDB + PubChem + 특허를 합쳐 만들었습니다.",
    "같은 태도입니다. 그리고 우리가 다음 단계로 생각하는 것 —",
    "패밀리 천연물 저해제 86개를 문헌 수작업으로 200개 이상으로 늘리는 것 — 과도 통합니다.",
  ], LIGHT, TEAL),
  GAP(140),

  H3("활성 기준값을 셋으로 나눈 이유"),
  TBL(["기준값", "양성 : 음성", "성격"], [
    ["0.5 µM", "약 1 : 1", "균형"],
    ["1 µM", "약 3 : 2", "약간 불균형"],
    ["10 µM", "약 4 : 1", "심한 불균형"],
  ], [1800, 3600, 3600]),
  GAP(100),
  P("기준값보다 작으면 양성(라벨 1), 크면 음성(라벨 0)입니다. 하나의 기준만 쓰면 "
    + "그 기준에서의 결론만 나오므로, 불균형 정도를 바꿔 가며 모델의 거동을 봅니다."),
  GAP(140),

  H3("t-SNE로 본 화학공간 (Figure 5)"),
  TBL(["기준값", "t-SNE에서 보이는 것"], [
    ["0.5 µM", "양성·음성이 뚜렷이 구분되는 영역을 차지한다"],
    ["1 µM", "경계가 흐려지기 시작"],
    ["10 µM", "분포 경계가 더 약해진다"],
  ], [1800, 7200]),
  GAP(100),
  P("논문의 해석 — \"따라서 ML 모델은 이론적으로 양성과 음성을 구별하기가 더 어려워질 것이다.\" "
    + "실제 결과(7장)가 이 예측과 맞습니다."),
  GAP(140),

  H2("우리 데이터와의 비교"),
  TBL(["", "이 논문 (USP7)", "우리 (HSD17B13)"], [
    ["규모", "약 4,000개", "실측 2,673개"],
    ["1 µM 기준 비율", "양성:음성 ≈ 3:2", "1,915 : 758 ≈ 5:2"],
    ["출처", "ChEMBL + PubMed + SciFinder", "ChEMBL + BindingDB + PubChem + 특허"],
    ["성격", "같은 화학공간 안의 분류", "다른 화학공간(천연물)으로의 전이"],
  ], [1800, 3600, 3600]),
  GAP(100),
  BOX("마지막 줄이 핵심 차이입니다", [
    "이 논문의 시험셋은 학습셋과 같은 USP7 리간드 풀에서 나왔습니다.",
    "군집을 나눴을 뿐 같은 화학공간입니다.",
    "",
    "우리는 합성 의약화학 공간에서 배워 천연물 공간으로 넘어가야 합니다.",
    "31·32번에서 확인했듯 두 공간은 영역 분류 AUC 1.0000으로 완전히 갈립니다.",
    "",
    "그래서 이 논문의 결론이 우리에게 그대로 적용되지 않습니다.",
  ], WARM, "E0A033"),
  GAP(140),

  H2("원문 대조"),
  CMP([
    ["deubiquitinase", "탈유비퀴틴화 효소"],
    ["activity cutoff value", "활성 기준값"],
    ["aggregated into unique entries", "고유 항목으로 통합되었다"],
    ["traced to the source of the data", "데이터 출처까지 추적 가능한"],
    ["chemical space distribution", "화학공간 분포"],
    ["t-distributed stochastic neighbor embedding", "t-SNE. 고차원 데이터의 2차원 시각화"],
    ["the distribution boundaries become weaker", "분포 경계가 약해진다"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 2장
push(
  H1("2장.  분자 표현 네 가지와 전처리"),

  H2("먼저 알아야 할 것"),
  P("같은 분자를 네 가지 방식으로 표현했습니다. 세 가지는 벡터, 하나는 문자열입니다."),
  GAP(100),

  H2("차근차근"),
  TBL(["표현", "원래 차원", "전처리", "최종"], [
    ["물리화학 descriptor", "208종 (RDKit)", "0만 있는 특징 제거 → 194¶→ StandardScaler → PCA", "128"],
    ["ECFP4", "2048 bit", "PCA → StandardScaler", "128"],
    ["MACCS keys", "166 bit", "PCA → StandardScaler", "128"],
    ["SMILES", "최대 195자", "어휘 64종 → 정수 매핑 → 임베딩", "100차원 임베딩"],
  ], [2100, 1700, 3400, 1800]),
  GAP(140),

  H3("RDKit 버전"),
  P("2021.03.1. SMILES를 canonical 형태로 변환한 뒤 모든 표현을 계산했습니다. "
    + "버전을 명시한 것은 재현성 측면에서 좋은 관행입니다 — descriptor 목록이 버전마다 바뀌기 때문입니다."),
  GAP(60),
  P("참고로 우리 환경은 RDKit 2026.03.4이고 descriptor는 217종입니다. "
    + "208종에서 늘어난 것입니다.", { color: GRAY }),
  GAP(140),

  H3("SMILES 처리 세부"),
  N("SMILES 표기는 'C', 'N', '@', '(' 같은 64개 기호로 이루어진다"),
  N("데이터셋의 SMILES 길이는 18~195자 범위"),
  N("195자보다 짧으면 뒤를 0으로 채운다 (padding)"),
  N("미리 만든 어휘에 따라 정수 벡터로 매핑"),
  N("임베딩 층이 그것을 100차원 연속 벡터로 바꾼다"),
  GAP(100),
  BOX("임베딩이 하는 일", [
    "기호를 숫자로 바꾸면 'C'=1, 'N'=2 같은 식이 되는데,",
    "그러면 모델이 'N이 C보다 크다'는 엉뚱한 관계를 배울 수 있습니다.",
    "",
    "임베딩은 각 기호를 100차원 벡터로 바꾸고, 그 벡터를 학습으로 정합니다.",
    "비슷하게 쓰이는 기호끼리 가까워지도록 자동으로 배치됩니다.",
  ], LIGHT, TEAL),
  GAP(140),

  H3("조기 융합 — 여덟 가지 특징 조합"),
  P("세 벡터 표현을 이어붙여 조합을 만들었습니다 (Figure 4, Table 1)."),
  GAP(60),
  TBL(["번호", "입력", "모델군"], [
    ["(1)", "물리화학 descriptor", "ML / DL"],
    ["(2)", "ECFP4", "ML / DL"],
    ["(3)", "MACCS", "ML / DL"],
    ["(4)", "SMILES", "DL만"],
    ["(5)", "물성 + ECFP4", "ML / DL"],
    ["(6)", "물성 + MACCS", "ML / DL"],
    ["(7)", "MACCS + ECFP4", "ML / DL"],
    ["(8)", "물성 + ECFP4 + MACCS", "ML / DL"],
  ], [900, 4600, 3500]),
  GAP(100),
  P("ML 7개(SMILES 제외) + DL 7개 + DL-SMILES 1개 = 총 15개 실험입니다."),
  GAP(140),

  H2("우리 설정과 비교"),
  TBL(["", "이 논문", "우리"], [
    ["표현", "물성 128 + ECFP4 128 + MACCS 128", "ECFP4 1024 + FCFP4 1024"],
    ["차원 축소", "PCA 128", "안 함"],
    ["정규화", "StandardScaler", "안 함 (LightGBM은 불필요)"],
    ["FCFP", "쓰지 않음", "씀 (25c에서 5/5 개선 확인)"],
    ["물성 descriptor", "융합에 포함", "217종 보유, 아직 미융합"],
  ], [1700, 3650, 3650]),
  GAP(100),
  BOX("가져갈 만한 것 하나", [
    "물성 descriptor를 지문과 융합하는 것은 우리도 해 볼 수 있습니다.",
    "11_train_combined.py에서 이미 시도한 적이 있는데,",
    "그때는 decoy 포함 평가라 차이를 분별하지 못했습니다.",
    "",
    "지금은 Butina 분할 + 시드 반복 틀이 갖춰졌으니 다시 재 볼 가치가 있습니다.",
  ], LIGHT, TEAL),
  GAP(140),

  H2("원문 대조"),
  CMP([
    ["molecular representation", "분자 표현"],
    ["physicochemical descriptors", "물리화학 서술자"],
    ["bit vector", "비트 벡터"],
    ["canonical form", "표준형"],
    ["high sparsity", "높은 희소성. 대부분이 0"],
    ["dimensionality reduction", "차원 축소"],
    ["early fusion", "조기 융합"],
    ["combined horizontally", "가로로 이어붙였다"],
    ["padded with trailing zeros", "뒤를 0으로 채웠다"],
    ["embedding layer", "임베딩 층"],
    ["prebuilt vocabulary", "미리 만든 어휘"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 3장
push(
  H1("3장.  군집 기반 분할"),

  H2("먼저 알아야 할 것"),
  P("무작위로 나누면 같은 계열 분자가 학습·시험 양쪽에 들어가 성능이 부풀려집니다. "
    + "이 논문은 골격 기준으로 군집을 만들고 군집 단위로 나눴습니다."),
  GAP(100),

  H2("차근차근"),
  H3("절차"),
  N("물성 + MACCS + ECFP4를 이어붙인 결합 표현을 만든다"),
  N("그 공간에서 K-means 군집화를 한다"),
  N("군집 수는 CHS·DBI·실루엣 세 지표로 결정 → 13개"),
  N("양성·음성 비율이 각 집합에서 비슷하도록 맞추면서, 10개 군집을 학습·검증으로"),
  N("남은 3개 군집을 시험 집합으로"),
  GAP(100),
  TBL(["집합", "개수"], [
    ["학습 Dtrain", "3,763"],
    ["검증 Dval", "241"],
    ["시험 Dtest", "531"],
  ], [4500, 4500]),
  GAP(120),
  P("논문은 Figure 2에서 \"시험셋의 양성·음성 비율이 전체 데이터셋과 비슷하다\"는 것을 보입니다."),
  GAP(140),

  H3("군집 수를 정하는 세 지표"),
  TBL(["지표", "무엇을 보나", "좋은 방향"], [
    ["Calinski-Harabasz (CHS)", "군집 간 분산 / 군집 내 분산", "클수록"],
    ["Davies-Bouldin (DBI)", "군집 간 유사도의 평균", "작을수록"],
    ["실루엣 계수 (SC)", "자기 군집과의 거리 대 이웃 군집과의 거리", "1에 가까울수록"],
  ], [2600, 4400, 2000]),
  GAP(100),
  P("세 지표를 함께 보는 것은 좋은 관행입니다. 하나만 보면 군집 수를 임의로 고른 것처럼 됩니다."),
  GAP(140),

  H2("우리 Butina 군집 분할과 비교"),
  TBL(["", "이 논문", "우리"], [
    ["군집 방법", "K-means (결합 표현 공간)", "Butina (Tanimoto 거리 0.4)"],
    ["군집 수", "13", "323 (실측 2,673개 기준)"],
    ["분할 방식", "홀드아웃 1회 (10 : 3)", "StratifiedGroupKFold 5겹"],
    ["반복", "시드 30개", "시드 5개"],
    ["분할 검증", ("하지 않음"), "최근접 Tanimoto로 확인"],
  ], [1800, 3600, 3600]),
  GAP(140),

  H3("우리가 추가한 '분할 검증'"),
  P("이 논문은 군집 분할을 했다는 사실만 보고하고, 그 분할이 실제로 화학공간을 갈랐는지는 "
    + "재지 않습니다. 우리는 쟀고, 그 덕에 문제를 발견했습니다."),
  GAP(60),
  TBL(["분할", "시험 분자의 최근접 Tanimoto 중앙값", "≥0.7 비율"], [
    ["무작위", "0.826", "91.0 %"],
    ["Murcko 골격", "0.754", "72.8 %"],
    ["Butina 군집 (0.6)", ("0.636"), ("34.1 %")],
  ], [2600, 4000, 2400]),
  GAP(120),
  BOX("Murcko로는 부족했습니다", [
    "처음에는 Murcko 골격 분할을 썼는데, 최근접 유사도가 0.826에서 0.754로만 떨어졌습니다.",
    "유도체가 치환기 하나 차이로 서로 '다른' Murcko 골격이 되어 폴드 사이로 샜기 때문입니다.",
    "",
    "Butina 군집으로 바꾸니 0.636까지 떨어졌습니다.",
    "분할을 했다는 것과 실제로 갈렸다는 것은 다릅니다 — 재 봐야 압니다.",
  ], WARM, "E0A033"),
  GAP(140),

  H2("원문 대조"),
  CMP([
    ["clustered the dataset into 13 groups", "데이터셋을 13개 군으로 군집화했다"],
    ["small molecule structural skeleton", "저분자 구조 골격"],
    ["conjoint representations", "결합 표현"],
    ["hold-out method", "홀드아웃 방식. 한 번 떼어 두고 평가"],
    ["generalization performance", "일반화 성능"],
    ["similar proportion of active and inactive", "활성·비활성 비율이 비슷하도록"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);


// ════════════════════════════════════════════════ 4장
push(
  H1("4장.  모델 — ML 9종과 DL 2종"),

  H2("먼저 알아야 할 것"),
  P("이 논문의 기여는 새 모델을 만든 것이 아니라, 기존 모델 11종을 같은 조건에서 "
    + "전수 비교한 것입니다. 그래서 모델 목록 자체가 결과의 일부입니다."),
  GAP(100),

  H2("4-1.  기계학습 9종"),
  TBL(["모델", "계열", "특징"], [
    ["SVC", "커널", "경계 근처 샘플만 쓴다. 고차원에 강함"],
    ["RF", "트리 앙상블", "트리 여러 개의 다수결. 과적합에 강함"],
    ["KNN", "사례 기반", "학습이 없다. 가까운 이웃의 라벨을 본다"],
    ["DT", "트리", "단일 결정 트리. 해석은 쉽지만 약함"],
    ["GBDT", "트리 부스팅", "오차를 줄이는 방향으로 트리를 순차 추가"],
    ["ABDT (AdaBoost)", "트리 부스팅", "틀린 샘플에 가중치를 키워 가며 학습"],
    ["GaussianNB", "확률", "특징 간 독립 가정. 매우 빠름"],
    ["SGD", "선형", "확률적 경사하강으로 학습하는 선형 분류기"],
    ["로지스틱 회귀", "선형", "가장 기본. 기준선 역할"],
  ], [2000, 1800, 5200]),
  GAP(120),
  P("하이퍼파라미터는 sklearn RandomizedSearchCV(5겹, n_iter=10)로 탐색했습니다. "
    + "탐색 범위는 보충자료 Table S3~S9에 있습니다."),
  GAP(140),

  H2("4-2.  딥러닝 2종"),
  H3("DL ① — 벡터 입력 (Figure 1B)"),
  N("세 표현(물성·ECFP4·MACCS)을 각각 정규화해 완전연결층에 넣는다"),
  N("그 출력을 세로로 쌓는다(vertically combined)"),
  N("self-attention 층을 통과시킨다"),
  N("마지막 완전연결층에서 출력을 낸다"),
  GAP(100),
  BOX("self-attention을 왜 넣었나", [
    "세 표현을 그냥 이어붙이면 모델이 '어느 표현이 지금 중요한가'를 모릅니다.",
    "",
    "self-attention은 입력 요소들끼리 서로를 참조해 가중치를 정합니다.",
    "분자에 따라 'ECFP4가 중요한 경우'와 'MACCS가 중요한 경우'를 나눠 처리할 수 있게 됩니다.",
  ], LIGHT, TEAL),
  GAP(140),

  H3("DL ② — SMILES 입력 (Figure 1C)"),
  N("임베딩 층 — 기호를 100차원 벡터로"),
  N("LSTM 4층 — 서열의 장기 의존성을 학습"),
  N("self-attention 층"),
  N("완전연결층"),
  GAP(100),
  TBL(["용어", "뜻"], [
    ["RNN", "순환 신경망. 서열·시계열 데이터용"],
    ["LSTM", "RNN의 확장. 기울기 소실 문제를 다루기 위해 개발됨"],
    ["장기 의존성", "서열의 앞부분이 뒷부분에 미치는 영향"],
  ], [1600, 7400]),
  GAP(100),
  P("SMILES에서 장기 의존성이 중요한 이유 — 고리를 여는 숫자와 닫는 숫자가 멀리 떨어져 있고, "
    + "괄호도 중첩되기 때문입니다. C1CCCCC1에서 두 개의 '1'이 짝입니다."),
  GAP(140),

  H2("4-3.  계산 환경"),
  TBL(["항목", "내용"], [
    ["ML 라이브러리", "scikit-learn (StandardScaler, PCA, RandomizedSearchCV)"],
    ["화학정보", "RDKit 2021.03.1, Open Babel 2.3.1"],
    ["DL 프레임워크", "PyTorch"],
    ["하드웨어", "NVIDIA Tesla V100-DGXS-16GB"],
    ["코드 공개", "github.com/Hovi123123/Open-source (tag v1.0.0)"],
  ], [1900, 7100]),
  GAP(140),

  H2("원문 대조"),
  CMP([
    ["supervised learning binary classification", "지도학습 이진 분류"],
    ["support vector classification (SVC)", "서포트 벡터 분류"],
    ["gradient boosting decision tree", "경사 부스팅 결정 트리"],
    ["Gaussian naïve Bayes", "가우시안 나이브 베이즈"],
    ["fully connected layers", "완전연결층"],
    ["self-attention layer", "자기주의 층"],
    ["long short-term memory (LSTM)", "장단기 기억 신경망"],
    ["vanishing gradient problem", "기울기 소실 문제"],
    ["long-term dependencies", "장기 의존성"],
    ["randomized search", "무작위 탐색. 하이퍼파라미터 탐색법"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 5장
push(
  H1("5장.  불균형 처리 세 가지"),

  H2("먼저 알아야 할 것"),
  P("활성 기준값을 10 µM로 하면 양성:음성이 4:1이 됩니다. 이런 불균형에서는 "
    + "모델이 전부 '양성'이라 답해도 정확도 80%가 나옵니다. 대처가 필요합니다."),
  GAP(100),

  H2("차근차근"),
  TBL(["전략", "무엇을 하나", "만든 수", "적용 대상"], [
    ["SMOTE", "소수 클래스 샘플 사이를 보간해¶새 샘플을 합성", "음성 2,692개", "수치형 데이터"],
    ["비편향 decoy 선택", "ZINC 데이터베이스에서¶'비활성이면서 구조적으로 다양한' 분자", "2,692개", "수치형 데이터"],
    ["SMILES 열거", "같은 분자를 다른 SMILES로 표기해¶샘플을 늘림", "비활성 656개에서¶2,692개", "서열 데이터"],
  ], [1900, 3700, 1700, 1700]),
  GAP(140),

  H2("5-1.  SMOTE 자세히"),
  P("Synthetic Minority Over-sampling Technique. 소수 클래스 샘플 둘을 골라 그 사이 "
    + "어딘가에 새 점을 만듭니다."),
  GAP(60),
  BOX("원리", [
    "① 소수 클래스에서 샘플 하나를 고른다",
    "② 그 샘플의 k-최근접 이웃 중 하나를 고른다",
    "③ 두 점을 잇는 선분 위의 임의의 점을 새 샘플로 만든다",
    "",
    "단순 복제와 달리 '새로운' 점이 생기므로 과적합이 덜합니다.",
  ], LIGHT, TEAL),
  GAP(100),
  BOX("화학에서 쓸 때의 문제", [
    "두 분자의 지문 벡터 사이를 보간하면, 그 결과가 '실재하는 분자'에 대응하지 않습니다.",
    "ECFP4 비트 0.37 같은 값은 화학적으로 무의미합니다.",
    "",
    "그래도 분류 성능에는 도움이 될 수 있습니다 — 결정경계를 부드럽게 해 주니까요.",
    "다만 '물리적으로 말이 되는 음성을 늘린 것'은 아닙니다.",
    "",
    "우리가 SMOTE 대신 class_weight='balanced'를 쓰는 이유입니다.",
  ], WARM, "E0A033"),
  GAP(140),

  H2("5-2.  비편향 decoy 선택"),
  P("ZINC 데이터베이스에서 음성으로 쓸 분자를 고릅니다. 논문 표현 — "
    + "\"비활성이면서 구조적으로 다양한 화합물을 얻는 것을 목표로 한다.\""),
  GAP(100),
  BOX("우리가 여기서 크게 데였습니다", [
    "우리도 같은 발상으로 PubChem에서 decoy를 뽑았습니다 (06_add_decoys.py).",
    "조건 — active와 성질은 맞추고 Tanimoto ≤ 0.35.",
    "",
    "문제는 그 decoy를 '평가'에도 썼다는 것입니다.",
    "active와 decoy는 애초에 구조가 멀어서 무엇을 써도 갈립니다.",
    "지문 5종이 전부 AUC 0.997~0.999, BEDROC 1.000으로 완전 포화됐습니다.",
    "",
    "이 논문은 학습·검증만 균형을 맞추고 시험셋은 손대지 않았습니다.",
    "그 원칙을 지켰으면 우리도 그 함정을 피했을 것입니다.",
  ], WARM, RED),
  GAP(140),

  H2("5-3.  SMILES 열거"),
  P("같은 분자를 서로 다른 SMILES로 쓸 수 있다는 점을 이용합니다. 0-7에서 본 대로입니다."),
  GAP(60),
  P("비활성 656개에서 2,692개의 새 문자열을 만들었습니다. 분자 수는 그대로이고 "
    + "'표기'만 늘어난 것입니다."),
  GAP(60),
  BOX("지문 기반 모델에는 쓸 수 없습니다", [
    "어떤 SMILES로 쓰든 RDKit이 계산하는 ECFP4는 같습니다.",
    "열거해 봐야 똑같은 벡터가 복제될 뿐이라 정보가 늘지 않습니다.",
    "",
    "SMILES를 직접 입력으로 받는 모델(LSTM·Transformer)에만 유효한 증강법입니다.",
    "우리는 지문 기반이라 이 기법을 가져올 수 없습니다.",
  ], LIGHT, TEAL),
  GAP(140),

  H2("5-4.  지켜야 할 원칙 하나"),
  BOX(null, [
    "\"학습 집합과 검증 집합에서만 양성·음성 수의 균형을 맞췄고,",
    " 시험 집합은 변경하지 않았다.\"",
    "",
    "시험셋을 건드리면 평가가 현실과 멀어집니다.",
    "실제 스크리닝에서는 음성이 압도적으로 많으니까요.",
  ], WARM, "E0A033"),
  GAP(140),

  H2("원문 대조"),
  CMP([
    ["imbalanced data", "불균형 데이터"],
    ["oversampling strategy", "과표본화 전략"],
    ["synthetic minority over-sampling", "소수 클래스 합성 과표본화"],
    ["unbiased decoy selection", "비편향 decoy 선택"],
    ["both inactive and structurally diverse", "비활성이면서 구조적으로 다양한"],
    ["SMILES enumeration", "SMILES 열거"],
    ["the test set remained unchanged", "시험 집합은 변경하지 않았다"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 6장
push(
  H1("6장.  실험 설계와 난수 처리"),

  H2("먼저 알아야 할 것"),
  P("기계학습 결과는 난수에 따라 흔들립니다. 이 논문은 그것을 정면으로 다룹니다. "
    + "우리가 25c에서 시드 5개로 반복한 것과 같은 문제의식입니다."),
  GAP(100),

  H2("차근차근"),
  H3("난수는 어디서 오나"),
  N("데이터셋의 무작위 분할"),
  N("모델 가중치의 무작위 초기화"),
  N("부스팅·배깅의 표본 추출"),
  N("하이퍼파라미터 무작위 탐색"),
  GAP(100),
  P("이 논문은 홀드아웃 분할을 고정했으므로, 난수는 주로 모델 쪽에서 옵니다. "
    + "논문 표현 — \"따라서 이 연구에서 무작위성은 주로 난수 시드에서 왔다.\""),
  GAP(140),

  H3("시드 30개"),
  P("난수 시드 30개를 무작위로 골라 30번 실험하고, 평균과 표준편차를 계산했습니다. "
    + "ML은 시드마다 RandomizedSearchCV로 하이퍼파라미터를 다시 찾았고, "
    + "DL도 같은 시드로 30번 돌렸습니다."),
  GAP(60),
  P("모델 간 비교는 t-검정으로 했습니다 (보충자료 Table S10)."),
  GAP(100),
  BOX("왜 이것이 중요한가", [
    "한 번 돌려서 \"A가 B보다 0.02 높다\"고 하면 그것이 진짜 차이인지 운인지 알 수 없습니다.",
    "",
    "우리도 25c에서 같은 문제를 겪었습니다. 지문 간 차이가 ±0.01~0.02였는데,",
    "시드 5개로 반복하고 '같은 분할에서 짝지어 비교'하니 비로소 판정이 됐습니다.",
    "",
    "ECFP4+FCFP4가 5회 전부 이긴다는 것이, 평균이 0.008 높다는 것보다 설득력 있습니다.",
  ], LIGHT, TEAL),
  GAP(140),

  H2("우리 방식과의 차이"),
  TBL(["", "이 논문", "우리 (25c)"], [
    ["반복 수", "시드 30개", "시드 5개"],
    ["비교 방식", "t-검정 (독립 표본)", "짝지은 비교 (같은 분할에서 차이를 직접 계산)"],
    ["보고", "평균 ± 표준편차", "평균 ± 표준편차 + '몇 회 이겼나'"],
    ["분할", "홀드아웃 고정", "시드마다 다시 분할"],
  ], [1600, 3000, 4400]),
  GAP(120),
  BOX("짝지은 비교가 더 민감합니다", [
    "같은 분할에서 표현 A와 B를 모두 돌리고 그 차이를 계산하면,",
    "분할 난이도에서 오는 변동이 상쇄됩니다.",
    "",
    "우리가 ΔAUC +0.008 ± 0.004 (5/5)처럼 보고할 수 있었던 이유입니다.",
    "독립 t-검정이었다면 표준편차가 커서 유의하지 않게 나왔을 것입니다.",
  ], WARM, "E0A033"),
  GAP(140),

  H2("원문 대조"),
  CMP([
    ["randomness requires special attention", "무작위성에는 특별한 주의가 필요하다"],
    ["random splits of the dataset", "데이터셋의 무작위 분할"],
    ["random initialization of the model weights", "모델 가중치의 무작위 초기화"],
    ["30 random seeds", "난수 시드 30개"],
    ["mean and standard deviation (SD)", "평균과 표준편차"],
    ["objective and scientific experimental results", "객관적이고 과학적인 실험 결과"],
    ["t-test", "t-검정"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 7장
push(
  H1("7장.  결과 — 기준값에 따라 승자가 바뀐다"),

  H2("먼저 알아야 할 것"),
  P("15개 실험 × 모델 × 시드 30회의 결과를 요약하면 한 문장이 됩니다 — "
    + "\"항상 이기는 조합은 없다.\""),
  GAP(100),

  H2("7-1.  단일 표현의 성능 폭"),
  P("0.5 µM 균형 데이터에서 단일 표현 3종 × ML 9종 = 27개 분류기를 만들었습니다."),
  GAP(60),
  TBL(["지표", "최저", "최고"], [
    ["ACC", "43.50 %", "92.28 %"],
    ["F1", "12.79 %", "93.02 %"],
    ["AUC", "63.93 %", "94.31 %"],
  ], [2600, 3200, 3200]),
  GAP(120),
  BOX("폭이 이렇게 크다는 것의 의미", [
    "같은 데이터인데 모델·표현 선택에 따라 ACC가 43%에서 92%까지 벌어집니다.",
    "",
    "즉 \"ML로 해 봤더니 성능이 X였다\"는 보고는 거의 의미가 없습니다.",
    "어떤 조합을 썼는지, 왜 그것을 골랐는지가 함께 있어야 합니다.",
  ], LIGHT, TEAL),
  GAP(140),

  H2("7-2.  기준값별 최고 조합"),
  TBL(["활성 기준", "데이터 성격", "최고 조합", "성능"], [
    ["0.5 µM", "균형 (1:1)", "MACCS 기반 AdaBoost(DT)", "ACC 92.28 · F1 93.02 · AUC 93.94"],
    ["0.5 µM", "균형", "SMILES 기반 DL", "AUC 95.20 ± 0.43"],
    ["1 µM", "약간 불균형 (3:2)", "DL (물성+ECFP4+MACCS)", "ACC 82.13 · F1 82.83 · AUC 93.92"],
    ["10 µM", "심한 불균형 (4:1)", "DL (물성+MACCS) + SMOTE", "AUC 84.32 ± 3.17"],
    ["10 µM", "심한 불균형", "ECFP4 기반 RF + SMOTE", "ACC 84.94 %"],
  ], [1500, 2300, 2700, 2500]),
  GAP(140),

  H2("7-3.  저자의 결론 네 가지"),
  N("균형·심한 불균형 데이터에서는 앙상블 모델이 가장 좋았다"),
  N("약간 불균형 데이터에서는 SMILES 기반 딥러닝이 가장 좋았다"),
  N("다중모달 융합이 도움이 될 때도 있고 아닐 때도 있다"),
  N("불균형 처리 중에서는 SMOTE가 가장 효과적이었다"),
  GAP(140),

  H2("7-4.  t-SNE 관찰과의 일치"),
  P("1장에서 본 t-SNE 결과 — 기준값이 커질수록 양성·음성 경계가 흐려진다 — 와 "
    + "성능이 맞아떨어집니다."),
  GAP(60),
  TBL(["기준값", "t-SNE 경계", "최고 AUC"], [
    ["0.5 µM", "뚜렷", "95.20"],
    ["1 µM", "흐려짐", "93.92"],
    ["10 µM", "약함", "84.32"],
  ], [2000, 3500, 3500]),
  GAP(120),
  P("데이터 자체의 난이도가 성능 상한을 정한다는 것을 보여 줍니다. "
    + "모델을 아무리 고쳐도 넘을 수 없는 선이 있다는 뜻이고, 이것은 우리가 32번에서 "
    + "확인한 것과 같은 종류의 결론입니다."),
  GAP(140),

  H2("원문 대조"),
  CMP([
    ["the performance of these models varied widely", "이 모델들의 성능은 크게 달랐다"],
    ["ensemble models performed best", "앙상블 모델이 가장 좋았다"],
    ["slightly imbalanced", "약간 불균형한"],
    ["severely imbalanced", "심하게 불균형한"],
    ["balanced dataset", "균형 데이터셋"],
    ["the degree of dataset imbalance increases", "데이터셋 불균형 정도가 커진다"],
    ["theoretically become more difficult to differentiate", "이론적으로 구별하기 더 어려워진다"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);


// ════════════════════════════════════════════════ 8장
push(
  H1("8장.  우리 과제와의 거리"),

  H2("먼저 알아야 할 것"),
  P("이 장은 논문 내용이 아니라 우리 상황과의 대조입니다. 결론부터 적으면 — "
    + "세 논문 중 우리에게 새로 준 것이 가장 적었습니다."),
  GAP(100),

  H2("8-1.  요소별 대조"),
  TBL(["이 논문의 요소", "우리 상태", "판정"], [
    ["군집 단위 분할 (K-means 13개)", "Butina 군집 + 5겹 + 시드 5개로 이미 적용", ("이미 하던 것")],
    ["다중표현 조기 융합", "ECFP4+FCFP4는 적용 (25c에서 5/5 개선).¶물성 217종은 아직 미융합", ("일부 적용")],
    ["SMOTE 과표본화", "class_weight='balanced'로 대응", "대안 존재"],
    ["비편향 decoy (ZINC)", "PubChem decoy를 평가에도 써서 실패.¶학습 전용 원칙을 교훈으로", ("교훈 반영")],
    ["SMILES 열거 증강", "지문 기반이라 이식 불가", "해당 없음"],
    ["시드 30개 + t-검정", "시드 5개 + 짝지은 비교", ("이미 하던 것")],
    ["PCA 차원 축소", "안 함 (LightGBM은 희소 데이터를 직접 처리)", "불필요"],
  ], [3000, 4200, 1800]),
  GAP(140),

  H2("8-2.  문제의 성격이 다르다"),
  TBL(["", "이 논문", "우리"], [
    ["푸는 문제", "같은 화학공간 안에서 최적 조합 찾기", "다른 화학공간으로 넘어가기"],
    ["학습셋", "USP7 리간드 3,763개", "HSD17B13 합성 억제제 1,915개"],
    ["시험셋", "같은 풀의 다른 군집 531개", "천연물 765,011개"],
    ["학습-시험 간격", "군집은 달라도 같은 의약화학 공간", "영역 분류 AUC 1.0000 — 완전 분리"],
    ["성능 상한", "데이터 난이도에 달림", "전이 가능성 자체에 달림"],
  ], [1800, 3600, 3600]),
  GAP(140),

  H2("8-3.  32번 결과가 이 차이를 수치로 보여 줍니다"),
  P("우리는 표현 6종에 대해 두 축을 동시에 쟀습니다 — 활성 AUC와 영역 AUC."),
  GAP(60),
  TBL(["표현", "활성 AUC", "영역 AUC", "판정"], [
    ["ECFP4", "0.891", "1.0000", "전이 불가"],
    ["FCFP4", "0.884", "1.0000", "전이 불가"],
    ["ECFP4+FCFP4", "0.902", "1.0000", "전이 불가"],
    ["MACCS", "0.853", "0.9999", "전이 불가"],
    ["2D descriptor (217종)", "0.875", "1.0000", "전이 불가"],
    ["FCFP4 (Murcko 일반뼈대)", ("0.632"), ("0.9624"), "여지 있음"],
  ], [2800, 2000, 2000, 2200]),
  GAP(120),
  BOX("이 논문이 비교한 표현들이 전부 들어 있습니다", [
    "ECFP4, MACCS, 2D descriptor — 이 논문이 쓴 세 표현 모두 우리 비교에 들어 있습니다.",
    "그리고 전부 영역 AUC 0.9999 이상이었습니다.",
    "",
    "즉 이 논문이 추천하는 어떤 조합을 가져와도 우리 문제는 안 풀립니다.",
    "활성을 가를 수 있는 표현은 영역도 가르기 때문입니다.",
    "",
    "조합 최적화로 넘을 수 없는 벽이라는 것이 우리 결론입니다.",
  ], WARM, RED),
  GAP(140),

  H2("8-4.  그래도 가져갈 것 — 물성 융합"),
  P("한 가지는 해 볼 만합니다. 물성 descriptor를 지문과 융합하는 것입니다."),
  GAP(60),
  N("우리는 11_train_combined.py에서 이미 시도한 적이 있다"),
  N("그런데 그때는 decoy 포함 평가라 차이를 분별하지 못했다"),
  N("지금은 Butina 분할 + 시드 반복 틀이 갖춰졌다"),
  N("다시 재 보면 ECFP4+FCFP4+물성이 더 나은지 판정할 수 있다"),
  GAP(100),
  P("다만 32번 결과로 볼 때, 내부 성능이 조금 오르더라도 천연물 전이는 "
    + "여전히 막혀 있을 가능성이 큽니다. 우선순위는 낮습니다."),
  GAP(140),

  H2("원문 대조"),
  CMP([
    ["systematic comparison", "체계적 비교"],
    ["generalization performance", "일반화 성능"],
    ["multimodal data fusion", "다중모달 데이터 융합"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 9장
push(
  H1("9장.  이 논문이 다루지 않는 것"),

  H2("항목별 확인"),
  TBL(["항목", "다루나", "우리에게 왜 중요한가"], [
    ["적용 범위 (applicability domain)", ("다루지 않음"), "천연물은 학습셋과 Tanimoto 0.2.¶외삽 여부 판단이 핵심이다"],
    ["예측 불확실성·보정", ("다루지 않음"), "van Tilborg의 주제.¶언제 믿지 말지를 알아야 한다"],
    ["분포 이동 / OOD", ("다루지 않음"), "우리 문제의 본체"],
    ["활성 절벽 (activity cliff)", ("다루지 않음"), "유사도 기반 방법의 실패 지점"],
    ["시험셋과 학습셋의 유사도 측정", ("다루지 않음"), "군집 분할이 실제로 갈랐는지¶확인하는 수단"],
    ["조기 인식 지표 (BEDROC·EF)", ("다루지 않음"), "가상 스크리닝에서는¶목록 맨 앞이 중요하다"],
    ["클래스 불균형", ("다룬다"), "SMOTE·decoy·SMILES 열거 비교"],
    ["표현·모델 조합 전수 비교", ("다룬다"), "15개 실험 × 시드 30회"],
    ["군집 기반 분할", ("다룬다"), "우리가 쓰는 방법의 선례"],
  ], [3000, 2200, 3800]),
  GAP(140),

  H2("특히 아쉬운 두 가지"),
  H3("① 분할이 실제로 갈랐는지 재지 않았다"),
  P("K-means로 13군집을 만들고 10:3으로 나눴다는 사실은 보고하지만, "
    + "시험셋 분자가 학습셋 분자와 얼마나 닮았는지는 재지 않습니다."),
  GAP(60),
  BOX("우리가 그걸 쟀기 때문에 문제를 발견했습니다", [
    "Murcko 골격 분할을 썼을 때 최근접 Tanimoto 중앙값이 0.826 → 0.754로만 떨어졌습니다.",
    "분할을 했는데 거의 안 갈린 것입니다.",
    "",
    "재 보지 않았다면 'Murcko 분할을 했으니 엄격한 평가'라고 보고했을 것입니다.",
    "Butina로 바꾼 뒤에야 0.636이 됐습니다.",
  ], WARM, "E0A033"),
  GAP(140),

  H3("② 조기 인식 지표가 없다"),
  P("ACC·F1·AUC 셋만 씁니다. 가상 스크리닝 관점에서는 부족합니다."),
  GAP(60),
  P("AUC는 목록 전체를 봅니다. 정답이 300등이어도 그 아래 1,600개를 제쳤으면 점수를 잘 받습니다. "
    + "그런데 실험할 수 있는 것은 상위 몇 개뿐입니다."),
  GAP(60),
  BOX("우리 사례가 이것을 보여 줍니다", [
    "34b번 검증에서 —",
    "",
    "nnPU        AUC 0.682,  EF 1% = 1.2배",
    "최근접 유사도  AUC 0.788,  EF 1% = 13.9배",
    "",
    "AUC 차이는 0.106인데 EF 차이는 11.6배입니다.",
    "AUC만 봤으면 '조금 낫다'로 끝났을 결론이, EF로 보면 '비교가 안 된다'가 됩니다.",
  ], WARM, RED),
  GAP(140),

  H2("정당한 평가"),
  P("이 논문이 이것들을 다루지 않은 것은 결함이 아닙니다. 논문의 목적이 "
    + "'같은 공간 안에서 조합을 고르는 것'이기 때문입니다. 그 목적 안에서는 잘 설계된 연구입니다."),
  GAP(60),
  P("다만 우리 문제와 맞지 않았을 뿐입니다. 그것도 읽어 봐야 아는 일입니다."),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 10장
push(
  H1("10장.  정리"),

  H2("논문이 한 일"),
  TBL(["", "내용"], [
    ["질문", "USP7 억제제 분류에서 어떤 표현·모델 조합이 가장 좋은가"],
    ["데이터", "USP7 리간드 약 4,000개 (train 3,763 / val 241 / test 531)"],
    ["표현", "물성 208→194→PCA128 · ECFP4 2048→128 · MACCS 166→128 · SMILES"],
    ["모델", "ML 9종 + DL 2종 (self-attention, LSTM)"],
    ["분할", "결합 표현에 K-means → 13군집 → 10:3 홀드아웃"],
    ["불균형", "SMOTE · 비편향 decoy(ZINC) · SMILES 열거. 학습·검증만 적용"],
    ["반복", "난수 시드 30개, 평균±SD, t-검정"],
    ["결과", "항상 이기는 조합은 없다. 기준값에 따라 승자가 바뀐다"],
    ["최고 성능", "AUC 0.939 ~ 0.952 (기준값에 따라)"],
    ["코드", "github.com/Hovi123123/Open-source"],
  ], [1200, 7800]),
  GAP(140),

  H2("우리가 가져간 것"),
  BOX(null, [
    "① 군집 분할의 선례 — 우리가 이미 쓰던 방법의 근거로 인용할 수 있다",
    "② 다중표현 융합이 때때로 돕는다는 전수 비교 확인",
    "③ decoy는 학습에만, 평가에는 쓰지 않는다 — 우리가 비싸게 배운 것의 정석",
    "④ 시드 반복 + 통계 검정의 중요성",
    "",
    "→ 새로 할 일: 물성 descriptor 융합을 Butina 틀에서 재측정 (우선순위 낮음)",
  ], LIGHT, TEAL),
  GAP(140),

  H2("네 논문 속에서의 위치"),
  TBL(["논문", "역할", "우리에게 준 것"], [
    ["Cockroft 2019", "분포 이동을 '측정'한 논문", "FCFP · 외부 시험셋 설계 · 낙폭 측정"],
    ["Kiryo 2017 (nnPU)", "라벨 가정을 '고친' 논문", "nnPU 구현 · 라벨 오류 확정"],
    ["Yang 2025", "개별 대신 '클래스'로 보라는 논문", "44개 농축 클래스 — 최선의 결과"],
    ["Shen 2023 (이 논문)", "같은 공간 안에서 '조합을 고르는' 논문", "기존 방법의 선례 · 평가 원칙"],
  ], [2000, 3400, 3600]),
  GAP(140),

  H2("읽고 나서의 결론"),
  BOX(null, [
    "\"새로 할 것이 없다\"도 결론입니다.",
    "",
    "우리 파이프라인이 이미 이 논문 수준의 평가 엄밀성을 갖췄음을 확인했습니다.",
    "그리고 우리 문제가 조합 최적화로 풀리는 종류가 아님을 다시 확인했습니다.",
    "",
    "확인에 드는 비용이 적었으므로, 읽은 것은 잘한 일입니다.",
  ], LIGHT, TEAL),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 부록
push(
  H1("부록 A.  원문 표현 모음"),
  CMP([
    ["multimodal data fusion", "다중모달 데이터 융합"],
    ["systematic comparison", "체계적 비교"],
    ["deubiquitinase", "탈유비퀴틴화 효소"],
    ["activity cutoff value", "활성 기준값"],
    ["molecular representation", "분자 표현"],
    ["physicochemical descriptors", "물리화학 서술자"],
    ["bit vector", "비트 벡터"],
    ["canonical form", "표준형"],
    ["high sparsity", "높은 희소성"],
    ["dimensionality reduction", "차원 축소"],
    ["principal component analysis (PCA)", "주성분 분석"],
    ["early fusion", "조기 융합"],
    ["combined horizontally", "가로로 이어붙임"],
    ["embedding layer", "임베딩 층"],
    ["prebuilt vocabulary", "미리 만든 어휘"],
    ["padded with trailing zeros", "뒤를 0으로 채움"],
    ["self-attention layer", "자기주의 층"],
    ["long short-term memory (LSTM)", "장단기 기억 신경망"],
    ["vanishing gradient problem", "기울기 소실 문제"],
    ["long-term dependencies", "장기 의존성"],
    ["supervised learning binary classification", "지도학습 이진 분류"],
    ["randomized search", "무작위 탐색"],
    ["imbalanced data", "불균형 데이터"],
    ["oversampling strategy (SMOTE)", "과표본화 전략"],
    ["unbiased decoy selection", "비편향 decoy 선택"],
    ["SMILES enumeration", "SMILES 열거"],
    ["the test set remained unchanged", "시험 집합은 변경하지 않았다"],
    ["hold-out method", "홀드아웃 방식"],
    ["generalization performance", "일반화 성능"],
    ["conjoint representations", "결합 표현"],
    ["Calinski-Harabasz Score", "칼린스키-하라바츠 점수. 군집 품질 지표"],
    ["Davies-Bouldin index", "데이비스-불딘 지수"],
    ["Silhouette Coefficient", "실루엣 계수"],
    ["random seeds", "난수 시드"],
    ["mean and standard deviation", "평균과 표준편차"],
    ["t-distributed stochastic neighbor embedding", "t-SNE"],
    ["ensemble models performed best", "앙상블 모델이 가장 좋았다"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),

  H1("부록 B.  핵심 수치 일람"),
  TBL(["항목", "값", "출처"], [
    ["게재", "J Cheminform 15:5 (2023-01-11 온라인)", "표지"],
    ["PMCID", "PMC9835315 (CC BY 4.0)", "표지"],
    ["데이터 출처", "PubMed · ChEMBL 29 · SciFinder", "Methods"],
    ["ChEMBL 접근 ID", "CHEMBL2157850", "Methods"],
    ["접근일", "2021-11-13", "Methods"],
    ["리간드 수", "약 4,000여 개", "Methods"],
    ["활성 기준값", "0.5 / 1 / 10 µM", "Methods"],
    ["양성:음성 비율", "약 1:1 / 3:2 / 4:1", "Methods"],
    ["—  표현  —", "", ""],
    ["물성 descriptor", "208 → 194 (0 제거) → PCA 128", "Methods"],
    ["ECFP4", "2048 bit → PCA 128", "Methods"],
    ["MACCS", "166 bit → PCA 128", "Methods"],
    ["SMILES 어휘", "64종 기호", "Methods"],
    ["SMILES 길이", "18 ~ 195자 (195로 패딩)", "Methods"],
    ["임베딩 차원", "100", "Methods"],
    ["—  분할  —", "", ""],
    ["군집 수", "13 (K-means, CHS·DBI·SC로 결정)", "Methods"],
    ["학습 Dtrain", "3,763", "Methods"],
    ["검증 Dval", "241", "Methods"],
    ["시험 Dtest", "531", "Methods"],
    ["—  불균형 처리  —", "", ""],
    ["SMOTE 생성 음성", "2,692", "Methods"],
    ["ZINC decoy", "2,692", "Methods"],
    ["SMILES 열거", "비활성 656개 → 2,692개", "Methods"],
    ["—  실험  —", "", ""],
    ["실험 수", "15 (Table 1)", "Methods"],
    ["난수 시드", "30개", "Methods"],
    ["하이퍼파라미터 탐색", "RandomizedSearchCV, 5겹, n_iter=10", "Methods"],
    ["—  결과  —", "", ""],
    ["단일 표현 ACC 범위 (0.5 µM)", "43.50 ~ 92.28 %", "Table S11"],
    ["단일 표현 F1 범위", "12.79 ~ 93.02 %", "Table S11"],
    ["단일 표현 AUC 범위", "63.93 ~ 94.31 %", "Table S11"],
    ["0.5 µM 최고 (ML)", "MACCS + AdaBoost: AUC 93.94", "Table 5"],
    ["0.5 µM 최고 (DL)", "SMILES: AUC 95.20 ± 0.43", "Results"],
    ["1 µM 최고", "DL 융합: AUC 93.92", "Results"],
    ["10 µM 최고", "DL(물성+MACCS)+SMOTE: AUC 84.32 ± 3.17", "Results"],
    ["하드웨어", "NVIDIA Tesla V100-DGXS-16GB", "Methods"],
  ], [3900, 3300, 1800]),
  new Paragraph({ children: [new PageBreak()] }),

  H1("부록 C.  원문을 직접 읽을 때의 순서"),
  N("초록 — 무엇을 비교했는지"),
  N("Figure 1 — 전체 구조도. ML군(A), DL 벡터(B), DL SMILES(C)"),
  N("Methods의 Data collection — 데이터 출처와 활성 기준값 세 가지"),
  N("Figure 2 — 기준값별 양성·음성 분포"),
  N("Methods의 Split 절 — K-means 13군집. 우리 Butina와 비교하며 읽기"),
  N("Figure 4와 Table 1 — 여덟 가지 특징 조합과 15개 실험 설계"),
  N("Methods의 Strategies to handle imbalanced data — SMOTE·decoy·열거"),
  N("Figure 5 — t-SNE. 기준값이 커질수록 경계가 흐려진다"),
  N("Figure 6 이후 — 결과. 그룹 I·II·III가 각각 기준값에 대응"),
  N("Conclusions — 네 줄 요약"),
  N("Additional file 1 — 하이퍼파라미터 범위(S3~S9)와 전체 성능표(S11)"),
  GAP(140),
  BOX("시간이 없으면", [
    "초록 → Figure 1 → Methods의 Split 절 → Conclusions.",
    "10분이면 됩니다. 결과 표는 필요할 때 찾아보면 됩니다.",
  ], LIGHT, TEAL),
  new Paragraph({ children: [new PageBreak()] }),

  H1("부록 D.  우리 과제 점검표"),
  TBL(["", "점검 항목", "현재 상태"], [
    ["1", "군집 단위 분할을 쓰는가", "Butina (Tanimoto 0.6), 323군집"],
    ["2", "그 분할이 실제로 화학공간을 갈랐는지 쟀는가", "완료 — 최근접 Tanimoto 0.636"],
    ["3", "난수 반복과 통계 비교를 하는가", "시드 5개 + 짝지은 비교"],
    ["4", "decoy를 평가에 쓰고 있지 않은가", "25번에서 제거. 학습 전용 원칙"],
    ["5", "시험셋의 클래스 비율을 인위로 바꾸지 않았는가", "건드리지 않음"],
    ["6", "조기 인식 지표(BEDROC·EF)를 함께 보는가", "완료 — 이 논문에는 없는 것"],
    ["7", "적용 범위를 보고하는가", "완료 — max_sim_known"],
    ["8", "다중표현 융합을 시도했는가", "ECFP4+FCFP4 완료.¶물성 217종 융합은 미완"],
    ["9", "하이퍼파라미터 탐색 범위를 기록했는가", ("미완 — 기본값 사용 중")],
  ], [500, 5500, 3000]),
  GAP(140),
  BOX("9번이 우리에게 남은 숙제입니다", [
    "우리는 LightGBM 기본값(n_estimators=300~400, class_weight='balanced')을 쓰고 있습니다.",
    "하이퍼파라미터 탐색을 한 적이 없습니다.",
    "",
    "다만 32번 결과로 볼 때, 탐색으로 내부 성능이 올라도 천연물 전이는",
    "여전히 막혀 있을 가능성이 큽니다. 우선순위는 낮게 둡니다.",
  ], WARM, "E0A033"),
  GAP(160),
  P("작성 — 2026-11-24  ·  원문: Shen et al., J Cheminform 15:5 (2023)  ·  PMC9835315  ·  CC BY 4.0",
    { size: 19, color: GRAY }),
);

// ════════════════════════════════════════════════ 문서
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: KO, size: 21, color: "1F1F1F" },
                  paragraph: { spacing: { line: 300 } } },
      title: { run: { font: KO, size: 48, bold: true, color: PETROL },
               paragraph: { spacing: { before: 0, after: 240 } } },
      heading1: { run: { font: KO, size: 30, bold: true, color: PETROL },
                  paragraph: { spacing: { before: 360, after: 180 }, keepNext: true,
                               border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: TEAL, space: 6 } } } },
      heading2: { run: { font: KO, size: 24, bold: true, color: TEAL },
                  paragraph: { spacing: { before: 300, after: 140 }, keepNext: true } },
      heading3: { run: { font: KO, size: 21, bold: true, color: "1F1F1F" },
                  paragraph: { spacing: { before: 200, after: 100 }, keepNext: true } },
    },
  },
  numbering: {
    config: [
      { reference: "bul", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 400, hanging: 250 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 760, hanging: 250 } } } },
      ] },
      { reference: "num", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 420, hanging: 280 } } } },
      ] },
    ],
  },
  sections: [{
    properties: { page: { margin: { top: 1300, bottom: 1300, left: 1440, right: 1440 } } },
    children: kids,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("저장:", OUT, "(" + Math.round(buf.length / 1024) + " KB)");
});
