// van Tilborg 2026 강의 노트 (docx)
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  LevelFormat, PageBreak,
} = require("docx");

const OUT = "C:\\Users\\jjww1\\Desktop\\claude code\\bioai_test\\docs\\261112_vanTilborg2026_강의노트.docx";
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
    children: header.map((h, i) => cell(h, i, true, false)),
  })];
  rows.forEach((r, ri) => trs.push(new TableRow({
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
    children: [new TextRun({ text: "Molecular deep learning", size: 48, bold: true, color: PETROL, font: KO })],
  }),
  new Paragraph({
    spacing: { after: 240 },
    children: [new TextRun({ text: "at the edge of chemical space", size: 48, bold: true, color: PETROL, font: KO })],
  }),
  new Paragraph({
    spacing: { after: 400 },
    border: { top: { style: BorderStyle.SINGLE, size: 12, color: "E0A033", space: 1 } },
    children: [],
  }),
  P("van Tilborg, Rossen & Grisoni (2026)", { size: 24, bold: true }),
  P("Nature Machine Intelligence 8:575–587   ·   doi 10.1038/s42256-026-01216-w", { size: 21, color: GRAY }),
  GAP(500),
  P("슬라이드 11장을 따라가며 개념과 배경지식을 처음부터 설명합니다.", { size: 22 }),
  P("원문을 직접 읽을 때 대조할 수 있도록 영어 표현을 함께 실었습니다.", { size: 22 }),
  GAP(900),
  P("2026-11-12   ·   홍재원   ·   HSD17B13 소재발굴 프로젝트", { size: 20, color: GRAY }),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 사용법
push(
  H1("이 문서를 읽는 법"),
  P("논문은 결과부터 던지고 방법을 뒤에 설명합니다. 그래서 처음 읽으면 용어가 설명 없이 쏟아집니다. 이 문서는 순서를 바꿔, 필요한 배경지식을 먼저 깔고 그 위에 논문 내용을 올립니다."),
  GAP(60),
  TBL(["부분", "무엇이 들어 있나", "언제 읽나"], [
    ["0장\n기초", "분자를 컴퓨터에 넣는 법, 닮음을 재는 법,¶신경망 부품, 성능 지표, 기호 읽는 법", "가장 먼저.¶여기를 건너뛰면 1장부터 막힙니다"],
    ["1~10장\n본문", "슬라이드 1~10과 같은 순서.¶각 장은 (1) 먼저 알아야 할 것 (2) 차근차근¶(3) 원문 대조 세 부분", "순서대로"],
    ["부록", "자주 나오는 영어 표현,¶기호 일람, 원문 읽는 순서 추천", "논문을 직접 펼칠 때"],
  ], [1300, 4700, 3000]),
  GAP(160),
  BOX("한 문장으로 요약하면", [
    "이 논문은 \"모델이 처음 보는 분자를 만났을 때, 그 사실을 모델 스스로 알아채게 만드는 방법\"을 제안합니다.",
    "그 알아채는 정도를 숫자 하나로 만든 것이 불친숙도(unfamiliarity, 기호 𝕌)입니다.",
    "주의 — 이 방법은 예측을 더 정확하게 만들지 않습니다. 언제 틀릴지를 알려줄 뿐입니다. (10장에서 다시 설명)",
  ], WARM, "E0A033"),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 0장
push(
  H1("0장.  읽기 전에 — 이 논문에 깔린 기초"),

  H2("0-1.  분자를 컴퓨터에 넣는 두 가지 방법"),
  P("컴퓨터는 분자 그림을 그대로 못 읽습니다. 글자나 숫자로 바꿔 줘야 합니다. 이 논문은 두 가지를 씁니다. 둘의 차이를 아는 것이 이 논문 이해의 절반입니다."),
  GAP(60),
  H3("(가) SMILES — 분자를 '한 줄 글자'로 적기"),
  P("아스피린을 SMILES로 쓰면 이렇습니다."),
  new Paragraph({
    spacing: { before: 60, after: 120, line: 300 },
    indent: { left: 360 },
    shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
    children: [new TextRun({ text: "  CC(=O)Oc1ccccc1C(=O)O  ", size: 22, font: "Consolas" })],
  }),
  B("대문자 C = 탄소, O = 산소, N = 질소"),
  B("소문자 c = 벤젠 같은 방향족 고리의 탄소"),
  B("괄호 ( ) = 가지가 갈라지는 자리"),
  B("숫자 1 = 고리가 시작되고 닫히는 짝"),
  B("= 는 이중결합"),
  GAP(60),
  P("즉 분자를 한 줄짜리 문장처럼 적는 방법입니다. 이 글자 하나하나를 논문에서는 토큰(token)이라고 부릅니다."),
  BOX("왜 이게 중요한가", [
    "이 논문의 핵심 아이디어가 \"모델이 이 문장을 다시 받아쓸 수 있느냐\"이기 때문입니다.",
    "아는 언어로 된 문장은 듣고 그대로 받아쓸 수 있지만, 모르는 외국어는 못 받아씁니다.",
    "분자도 마찬가지라는 것이 이 논문의 출발점입니다.",
  ]),
  GAP(100),
  H3("(나) 지문(fingerprint) — 분자를 '0과 1의 줄'로 적기"),
  P("ECFP라는 지문은 분자 안에 어떤 조각이 들어 있는지를 체크리스트로 만든 것입니다."),
  B("2048칸짜리 빈 칸을 준비한다"),
  B("분자를 훑으며 '벤젠 고리 있음', '-OH 있음', '-COOH 있음' 같은 조각을 찾는다"),
  B("찾은 조각마다 정해진 칸에 1을 적는다. 나머지는 0"),
  GAP(60),
  P("결과는 0과 1이 2048개 늘어선 줄입니다. 분자 두 개의 줄을 겹쳐 보면 얼마나 닮았는지 셀 수 있습니다."),
  GAP(60),
  P("논문에 CATS라는 것도 나옵니다. 이건 원자 하나하나 대신 \"양전하를 띠는 부분\", \"수소결합을 주는 부분\" 같은 성격과 그들 사이의 거리로 분자를 적는 방식입니다. 파마코포어(pharmacophore) 기술자라고 부릅니다.", {}),
  GAP(160),

  H2("0-2.  닮음을 재는 자 — Tanimoto 계수"),
  P("지문 두 개를 놓고 이렇게 계산합니다."),
  new Paragraph({
    spacing: { before: 60, after: 120, line: 300 },
    indent: { left: 360 },
    children: [new TextRun({ text: "Tanimoto  =  (둘 다 1인 칸 수)  ÷  (둘 중 하나라도 1인 칸 수)",
                             size: 21, bold: true, color: PETROL, font: KO })],
  }),
  P("0이면 겹치는 조각이 하나도 없고, 1이면 완전히 같습니다."),
  GAP(60),
  TBL(["Tanimoto", "실무에서의 뜻"], [
    ["0.7 이상", "사실상 같은 계열. 곁가지만 바꾼 쌍둥이 수준"],
    ["0.4 ~ 0.7", "닮은 구석이 있음"],
    ["0.3 이하", "남남. 같은 집안으로 보기 어렵다"],
  ], [1800, 7200]),
  GAP(100),
  BOX("우리 과제와 연결", [
    "우리 HSD17B13 학습셋과 천연물의 Tanimoto가 0.18~0.20입니다.",
    "즉 모델이 배운 것과 우리가 예측하려는 것이 완전히 남남이라는 뜻입니다.",
    "이 논문이 다루는 문제가 정확히 이 상황입니다.",
  ], WARM, "E0A033"),
  GAP(160),

  H2("0-3.  골격(scaffold) — 분자의 뼈대만 남기기"),
  P("분자에서 곁가지를 전부 떼어내고 고리 부분만 남긴 것을 Bemis–Murcko 골격이라고 합니다."),
  GAP(60),
  P("왜 이걸 쓸까요. 어떤 제약회사가 한 골격을 찾아 곁가지만 바꿔가며 분자 500개를 만들었다고 합시다. 겉보기엔 분자 500개지만, 사실은 \"같은 집안 사람 500명\"입니다. 골격으로 묶어 보면 그게 드러납니다."),
  GAP(60),
  P("이 논문은 골격을 두 군데에서 씁니다."),
  N("시험셋을 만들 때 — 학습셋과 골격이 멀리 떨어진 분자들만 따로 모읍니다"),
  N("사전학습 데이터를 거를 때 — 평가에 쓸 분자와 골격이 비슷한 것은 사전학습에서 빼 버립니다"),
  GAP(160),

  H2("0-4.  기계학습의 기본, 그리고 '나누기'가 왜 중요한가"),
  B("학습셋(training set) — 정답을 보여주며 가르치는 분자들"),
  B("시험셋(test set) — 정답을 숨기고 맞혀 보게 하는 분자들"),
  GAP(60),
  P("여기에 함정이 하나 있습니다. 시험셋이 학습셋과 비슷하면 시험이 쉬워집니다. 곁가지만 바꾼 쌍둥이가 양쪽에 하나씩 들어가 있으면, 모델은 외운 답을 그대로 적으면 됩니다. 점수는 높게 나오지만 그건 실력이 아닙니다."),
  GAP(60),
  BOX("이것이 이 논문의 설계 동기입니다", [
    "그래서 이 논문은 분자들을 골격으로 묶은 뒤, 학습셋에서 가장 멀리 떨어진 덩어리를 통째로 떼어 시험셋으로 씁니다.",
    "일부러 어려운 시험을 만드는 것입니다. 그래야 \"처음 보는 분자에서의 실력\"을 잴 수 있습니다.",
    "참고 — 우리 HSD17B13 모델은 무작위로 나눠서, 시험셋의 12.2%가 학습셋과 골격을 공유합니다. 같은 함정에 빠져 있습니다.",
  ]),
  GAP(160),

  H2("0-5.  신경망의 부품 네 가지"),
  P("이 논문의 그림(Figure 1b)에 나오는 상자들이 무엇인지 알아 둡시다."),
  GAP(60),
  TBL(["부품", "하는 일", "비유"], [
    ["인코더\nencoder", "입력(SMILES 문자열)을 읽어 짧은 숫자 벡터로 압축한다", "긴 글을 읽고¶요약문을 쓰는 사람"],
    ["임베딩\nembedding (z)", "그렇게 압축된 숫자 벡터 자체. 논문에서 z라고 씁니다", "그 요약문"],
    ["디코더\ndecoder", "z만 보고 원래 입력을 다시 만들어 낸다", "요약문만 보고¶원래 글을 복원하는 사람"],
    ["예측 헤드\nprediction head", "z를 보고 답(활성/비활성)을 낸다", "요약문을 보고¶문제를 푸는 사람"],
  ], [1900, 4300, 2800]),
  GAP(100),
  P("이 논문의 인코더는 1D-CNN, 디코더는 RNN입니다."),
  B("1D-CNN — 글자 줄을 창문처럼 훑으며 \"여기 몇 글자가 이런 패턴이네\"를 잡아내는 신경망"),
  B("RNN — 한 글자씩 순서대로 뱉어내는 신경망. 앞 글자를 보고 다음 글자를 고릅니다"),
  GAP(60),
  P("인코더와 디코더를 붙여 \"압축했다가 다시 펴는\" 구조를 오토인코더(autoencoder)라고 부릅니다. 논문은 복잡한 변분 오토인코더(VAE)도 시도했지만 이득이 없어 일반 오토인코더를 썼다고 밝혔습니다."),
  GAP(160),

  H2("0-6.  성능을 재는 자"),
  P("정확도(맞힌 비율)만 쓰면 속기 쉽습니다. 활성 분자가 5%뿐인 데이터에서 \"전부 비활성\"이라고만 답해도 정확도 95%가 나옵니다."),
  GAP(60),
  BOX("균형정확도 (balanced accuracy)", [
    "균형정확도 = ( 활성을 맞힌 비율  +  비활성을 맞힌 비율 ) ÷ 2",
    "",
    "활성 쪽과 비활성 쪽을 따로 채점해 평균을 냅니다. 한쪽만 잘해서는 점수가 안 오릅니다.",
    "0.5 = 찍기 수준,  1.0 = 완벽.  이 논문이 쓰는 주 지표입니다.",
  ]),
  GAP(100),
  P("논문 뒤쪽 가상 스크리닝에서는 두 가지가 더 나옵니다."),
  B("적중률(hit rate) — 활성이라고 고른 것 중 실제로 활성이었던 비율"),
  B("정밀도(precision) — 모델이 양성이라고 한 것 중 실제 양성의 비율"),
  GAP(160),

  H2("0-7.  기호 읽는 법"),
  P("논문에 특수한 글꼴의 기호가 나옵니다. 처음 보면 당황스럽지만 종류는 몇 개 안 됩니다."),
  GAP(60),
  TBL(["기호", "읽는 법", "뜻"], [
    ["𝔼(y|x)", "익스펙테이션 와이 기븐 엑스", "분자 x가 활성일 것이라는 모델의 예측값"],
    ["ℍ(y|x)", "엔트로피 와이 기븐 엑스", "그 예측이 얼마나 애매한가 = 불확실성"],
    ["𝕌(x)", "유 오브 엑스", "이 논문이 새로 만든 불친숙도"],
    ["ℒ", "로스", "손실(오차). 작을수록 잘한 것"],
    ["P", "피값", "우연히 이만큼 차이 날 확률.¶0.05보다 작으면 \"유의하다\"고 말합니다"],
    ["D", "디, KS 통계량", "두 분포가 얼마나 떨어져 있나. 0~1"],
    ["r", "상관계수", "−1 ~ +1. 0이면 아무 관계 없음"],
    ["τ", "타우", "켄달 순위상관계수. 역시 −1 ~ +1"],
    ["n.s.", "엔에스", "not significant. 통계적으로 차이가 없다"],
  ], [1200, 2800, 5000]),
  GAP(100),
  BOX("'given x'가 뭔가요", [
    "세로줄 | 은 \"~가 주어졌을 때\"로 읽습니다.",
    "ℍ(y|x) = \"분자 x를 봤을 때, 그 답 y에 대한 불확실성\"이라는 뜻입니다.",
    "확률·통계에서 조건을 적는 표준 표기이고, 특별한 연산 기호가 아닙니다.",
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 1장
push(
  H1("1장.  문제 — AI는 '처음 보는 분자'에서 무너진다"),
  P("(슬라이드 2)", { color: GRAY, size: 19 }),

  H2("먼저 알아야 할 것"),
  H3("왜 '구조가 새로운' 분자를 찾아야 하나"),
  P("이미 알려진 분자를 조금 바꾼 것으로는 안 되는 이유가 세 가지 있습니다. 논문 첫 단락이 이 셋을 나열합니다."),
  N("미충족 수요 — 기존 약으로 안 듣는 병은, 기존 약과 닮은 분자로도 대개 안 듣습니다"),
  N("사업성 — 남이 이미 특허를 가진 골격이면 개발해도 팔 수 없습니다"),
  N("내성 — 세균이나 암세포가 기존 약에 적응하면, 작동 방식이 다른 구조가 필요합니다"),
  GAP(100),
  H3("규모의 차이"),
  P("논문이 지적하는 숫자가 인상적입니다."),
  B("학습에 쓸 수 있는 분자: 보통 수백 개 (실험으로 하나하나 측정해야 하니까)"),
  B("스크리닝해 보고 싶은 분자: 수십억 개 (상용 라이브러리 + 가상 라이브러리)"),
  GAP(60),
  P("수백 개로 배워서 수십억 개를 판정해야 합니다. 당연히 대부분은 배운 적 없는 유형입니다."),

  H2("차근차근"),
  P("기계학습이 하는 일은 \"본 것에서 규칙을 뽑아, 비슷한 것에 적용\"입니다. 그러니 본 적 없는 유형에서 틀리는 건 결함이 아니라 원리입니다."),
  GAP(60),
  P("진짜 문제는 다른 데 있습니다."),
  BOX(null, [
    "모델은 틀릴 때도 똑같이 확신에 찬 숫자를 냅니다.",
    "\"활성 확률 0.93\" 이라고 답할 때, 그게 잘 아는 분자라서 0.93인지 처음 보는 분자인데도 0.93인지 구분할 방법이 없습니다.",
  ], WARM, RED),
  GAP(100),
  P("그래서 사람들은 적용 범위(applicability domain)라는 개념을 씁니다. 모델을 믿어도 되는 영역에 선을 긋고, 그 밖의 예측은 버리는 것입니다. Figure 1a의 점선이 그 선입니다."),
  GAP(60),
  P("이 논문은 그 선을 긋는 더 나은 방법을 제안합니다."),

  H2("원문 대조"),
  CMP([
    ["fail to generalize beyond the chemical space of their training data",
     "학습 데이터의 화학 공간 밖으로는 일반화가 안 된다"],
    ["out-of-distribution (OOD) molecules", "학습 분포 바깥에 있는 분자들"],
    ["structurally novel bioactive molecules", "구조가 새로운 활성 분자"],
    ["the 'edge' of the charted chemical space", "지도가 그려진 화학 공간의 가장자리.¶논문 제목의 edge가 이것입니다"],
    ["training sets typically contain only hundreds of molecules",
     "학습셋에는 보통 수백 개밖에 없다"],
    ["makes ... a herculean task", "엄청나게 힘든 일로 만든다 (헤라클레스의 과업)"],
    ["applicability domain", "적용 범위"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 2장
push(
  H1("2장.  기존 두 가지 방법과 각각의 한계"),
  P("(슬라이드 3)", { color: GRAY, size: 19 }),

  H2("먼저 알아야 할 것"),
  H3("불확실성(uncertainty)이란"),
  P("모델이 \"활성일 확률 0.95\"라고 하면 확신하는 것이고, \"0.51\"이라고 하면 애매해하는 것입니다. 이 애매한 정도를 숫자로 잰 것이 엔트로피 ℍ(y|x)입니다."),
  GAP(60),
  P("실제로 재는 방법은 조금 더 정교합니다. 모델을 조금씩 바꿔가며 여러 번 예측시켜, 답이 얼마나 흔들리는지를 봅니다. 논문에서는 approximate Bayesian modelling(근사 베이즈 모델링)이라고 부릅니다. 매번 같은 답이 나오면 확신, 답이 춤추면 불확실입니다."),

  H2("차근차근"),
  H3("방법 ① 유사도 기반 적용 범위"),
  B("학습 분자와 Tanimoto가 기준치(예: 0.5) 아래면 \"믿지 마라\""),
  B("간단하고 계산이 빠릅니다"),
  B("한계 1 — 모델이 무엇을 배웠는지는 전혀 보지 않습니다. 모델이 그 구조를 잘 다루는지와 무관하게 유사도만 봅니다"),
  B("한계 2 — 목표와 정면으로 충돌합니다. 구조가 새로운 분자를 찾으려는데, 구조가 새로우면 전부 걸러집니다"),
  GAP(100),
  H3("방법 ② 불확실성 추정"),
  B("예측이 애매하면 \"믿지 마라\""),
  B("모델이 배운 내용을 쓰므로 ①보다 낫습니다"),
  B("한계 — 분포가 크게 달라지면 신호가 거의 안 나옵니다. 이 논문이 7장에서 숫자로 보여줍니다 (KS D = 0.181)"),
  GAP(140),
  BOX("두 질문의 차이 — 이 논문 전체의 핵심", [
    "불확실성  :  \"답이 뭔지 모르겠다\"",
    "불친숙도  :  \"이 문제 자체를 처음 본다\"",
    "",
    "시험지에 비유하면 ①은 배운 단원인데 헷갈리는 문제, ②는 아예 안 배운 단원의 문제입니다.",
    "둘 다 틀릴 수 있지만 원인이 다르고, 대처도 달라야 합니다.",
    "그리고 이 논문은 두 값이 실제로 서로 무관함을 측정으로 보여줍니다 (r = −0.03 ± 0.03).",
  ]),

  H2("원문 대조"),
  CMP([
    ["a threshold on molecular similarity to the training data",
     "학습 데이터와의 분자 유사도에 기준선을 긋는 방식"],
    ["does not incorporate the information learned by the model",
     "모델이 배운 정보를 반영하지 못한다"],
    ["hampers the discovery of structurally novel molecules",
     "구조가 새로운 분자의 발굴을 방해한다"],
    ["uncertainty estimation", "불확실성 추정"],
    ["approximate Bayesian modelling", "근사 베이즈 모델링"],
    ["the two remain independent", "그 둘은 서로 독립이다"],
    ["complementarity", "상호 보완성"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 3장
push(
  H1("3장.  아이디어 — 모델에게 분자를 '다시 그려보라'고 시킨다"),
  P("(슬라이드 4)", { color: GRAY, size: 19 }),

  H2("먼저 알아야 할 것"),
  P("0-5에서 본 인코더·디코더를 떠올려 주세요. 입력을 압축했다가 다시 펴는 구조입니다."),
  GAP(60),
  P("여기에 중요한 직관이 하나 있습니다."),
  BOX(null, [
    "압축한 것만 보고 원래를 복원할 수 있다면, 그 내용을 제대로 이해한 것이다.",
    "모르는 외국어 문장은 받아쓰기도 못 합니다. 아는 언어면 들은 대로 쓸 수 있습니다.",
  ]),

  H2("차근차근"),
  H3("구조 — 출구가 두 개인 모델"),
  P("JMM(joint modelling)은 인코더 하나에 출구를 두 개 답니다."),
  N("예측 헤드 — z를 보고 활성 여부를 맞힌다  (원래 하려던 일)"),
  N("디코더 — z만 보고 원래 SMILES를 한 글자씩 다시 써낸다  (새로 추가한 일)"),
  GAP(60),
  P("두 일을 같은 z로 해야 하므로, z에는 \"구조 정보\"와 \"활성 정보\"가 함께 담기게 됩니다. 논문은 이를 shared latent space(공유 잠재 공간)라고 부릅니다."),
  GAP(140),
  H3("수식 풀어 읽기"),
  P("논문 식 (1)과 (2)입니다. 겁먹을 필요 없습니다."),
  new Paragraph({
    spacing: { before: 100, after: 60, line: 320 },
    indent: { left: 360 },
    children: [new TextRun({ text: "ℒ재구성(x)  =  − (1/|x|) · Σ log p( tᵢ | t<ᵢ )",
                             size: 22, bold: true, color: PETROL, font: KO })],
  }),
  P("한 조각씩 보겠습니다.", { before: 60 }),
  B("tᵢ  —  SMILES의 i번째 글자"),
  B("t<ᵢ  —  그 앞까지의 글자들"),
  B("p(tᵢ | t<ᵢ)  —  앞 글자들을 보고 \"다음은 이 글자일 것\"이라고 모델이 매긴 확률"),
  B("맞혔으면 확률이 1에 가깝고, log 1 = 0 이므로 손실이 0에 가깝습니다"),
  B("틀렸으면 확률이 0에 가깝고, log는 아주 큰 음수가 되므로 손실이 큽니다"),
  B("맨 앞의 마이너스 — 손실을 양수로 만들기 위한 부호 뒤집기"),
  B("1/|x| — 글자 수로 나누기. 긴 분자라고 불리해지지 않게 하는 장치"),
  GAP(100),
  new Paragraph({
    spacing: { before: 60, after: 60, line: 320 },
    indent: { left: 360 },
    children: [new TextRun({ text: "𝕌(x)  =  log  ℒ재구성(x)",
                             size: 22, bold: true, color: RED, font: KO })],
  }),
  P("여기에 로그를 한 번 더 씌운 것이 불친숙도입니다. 값의 범위를 눌러 비교하기 쉽게 만드는 흔한 처리입니다.", { before: 60 }),
  GAP(60),
  P("논문은 이 값의 이론적 상한도 적어 두었습니다. 쓰는 글자 종류가 V개일 때 상한은 log(log V)이고, 이 연구는 V = 35이므로 약 1.27입니다. 실제로 Figure 2e의 값들이 그 근처에 분포합니다."),
  GAP(140),
  H3("공짜인가 — 디코더를 붙인 대가"),
  P("일을 하나 더 시켰으니 예측이 나빠지지 않았을까요. 논문이 이것을 확인했습니다."),
  TBL(["비교", "균형정확도 (Test_ID)"], [
    ["기존 ECFP 기반 모델", "0.78 ± 0.02"],
    ["JMM", "0.75 ± 0.02"],
    ["디코더 있음 vs 없음", "차이 없음  (P = 0.499)"],
  ], [4500, 4500]),
  GAP(100),
  P("약간 낮지만 실무적으로 같은 수준이고, 디코더 유무로는 차이가 나지 않았습니다. 즉 \"낯섦을 재는 기능\"을 예측 성능을 깎지 않고 얻은 셈입니다."),

  H2("원문 대조"),
  CMP([
    ["joint modelling approach", "두 가지 일을 함께 학습시키는 방식"],
    ["molecular reconstruction", "분자 재구성 (= 다시 써내기)"],
    ["reconstruction loss", "재구성 손실. 다시 써낼 때의 오차"],
    ["negative log-likelihood loss", "음의 로그우도 손실"],
    ["normalized by SMILES token length", "SMILES 글자 수로 나눠 정규화한"],
    ["shared latent space", "공유 잠재 공간. 두 일이 함께 쓰는 z"],
    ["vocabulary size V", "쓰는 글자 종류 수 (이 연구에서는 35)"],
    ["a regular autoencoder was used ... no performance benefits of the more complex variational autoencoder",
     "일반 오토인코더를 썼다. 더 복잡한 VAE는 이득이 없었다"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 4장
push(
  H1("4장.  설계 — 낯선 시험셋을 일부러 만들어 둔다"),
  P("(슬라이드 5)", { color: GRAY, size: 19 }),

  H2("먼저 알아야 할 것"),
  H3("군집화(clustering)"),
  P("비슷한 것끼리 묶는 일입니다. 여기서는 \"골격이 비슷한 분자끼리\" 묶습니다."),
  GAP(60),
  P("논문은 스펙트럼 군집화(spectral clustering)라는 방법을 씁니다. 분자들을 점으로, 유사도를 선의 굵기로 보는 그래프를 만든 뒤, \"어디를 자르면 가장 적게 끊어지는가\"를 행렬 계산으로 찾는 방식입니다. 덩어리 모양이 복잡해도 잘 찾습니다."),
  GAP(100),
  H3("엘보(elbow)"),
  P("군집을 몇 개로 나눌지 정해야 합니다. 개수를 늘려가며 그래프를 그리면 어느 지점부터 거의 평평해지는데, 그 꺾이는 지점을 고릅니다. 팔꿈치처럼 생겨서 엘보라고 부릅니다. 논문은 kneed라는 알고리즘으로 자동으로 찾았고, 예시 데이터셋에서 11개가 나왔습니다."),

  H2("차근차근"),
  H3("OOD 시험셋 만드는 절차 (Figure 1c)"),
  N("분자에서 고리 골격만 남긴다"),
  N("골격끼리 Tanimoto 유사도를 전부 계산해 n×n 행렬 A를 만든다"),
  N("A를 라플라시안이라는 형태로 바꾼다.  L = I − D^(−1/2) A D^(−1/2)"),
  N("고유분해를 하고, 고유값을 작은 순으로 늘어놓아 엘보에서 군집 수 k를 정한다"),
  N("작은 쪽 고유벡터 k개로 k-means 군집화를 한다"),
  N("학습 중심에서 가장 먼 군집들(전체의 25%)을 Test_OOD로 뗀다"),
  N("남은 분자를 Test_ID 25% / Train 50%로 나눈다"),
  GAP(100),
  BOX("3번 식이 무서워 보이지만", [
    "유사도 행렬을 \"어디를 자를지 계산하기 좋은 형태\"로 바꾸는 표준 변환입니다.",
    "I는 단위행렬, D는 각 분자가 다른 분자들과 얼마나 연결되어 있는지를 모은 행렬입니다.",
    "결과만 알면 됩니다 — 이 변환 뒤 고유분해를 하면 자연스러운 덩어리가 드러납니다.",
  ]),
  GAP(140),
  H3("데이터 — 33개 데이터셋"),
  TBL(["출처", "타깃 수", "내용"], [
    ["MoleculeACE", "29", "ChEMBL에서 뽑은 생물활성 데이터셋 모음"],
    ["LIT-PCBA", "3", "ESR1(길항) · TP53 · PPARγ"],
    ["Ames 변이원성", "1", "독성 시험. 원래부터 이진 라벨"],
    ["합계", "33", "EC50 또는 Ki ≤ 100 nM 이면 활성으로 라벨"],
  ], [2600, 1400, 5000]),
  GAP(100),
  B("EC50 — 효과가 절반 나오는 농도. 낮을수록 강함"),
  B("Ki — 결합 세기를 나타내는 상수. 역시 낮을수록 강함"),
  B("100 nM = 0.1 µM. 꽤 엄격한 기준입니다"),
  GAP(140),
  H3("누수를 막은 장치 — 이 부분이 중요합니다"),
  P("모델은 먼저 ChEMBL 전체로 사전학습을 받습니다. 그런데 사전학습에서 본 분자가 나중에 시험에 나오면 반칙입니다."),
  GAP(60),
  BOX(null, [
    "그래서 평가용 33개 데이터셋의 골격과 Tanimoto 0.7을 넘는 ChEMBL 분자는 사전학습에서 전부 빼 버렸습니다.",
    "고리가 없어 골격을 뽑을 수 없는 분자도 제외했습니다.",
    "",
    "논문의 신뢰도를 판단할 때 이런 장치가 있는지를 보면 됩니다. 이 논문은 잘 해 두었습니다.",
  ]),

  H2("원문 대조"),
  CMP([
    ["inducing molecular distribution shifts", "분자 분포 이동을 일부러 만들어 내기"],
    ["spectral clustering", "스펙트럼 군집화"],
    ["symmetrically normalized Laplacian", "대칭 정규화 라플라시안"],
    ["eigenvalue decomposition", "고유값 분해"],
    ["the elbow (the point of maximal curvature)", "엘보 (곡률이 가장 큰 지점)"],
    ["in-distribution (ID)", "학습 분포 안쪽"],
    ["molecules with a Bemis–Murcko scaffold similar to any such scaffold ... were removed",
     "평가셋의 골격과 비슷한 골격을 가진 분자는 제거했다"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 5장
push(
  H1("5장.  검증 ① — 성능은 떨어지고, 𝕌(x)는 그걸 잡아낸다"),
  P("(슬라이드 6)", { color: GRAY, size: 19 }),

  H2("먼저 알아야 할 것"),
  H3("윌콕슨 부호순위 검정"),
  P("같은 데이터셋에서 ID 점수와 OOD 점수를 짝지어 비교하는 검정입니다. \"우연히 이만큼 차이가 날 확률\"을 P로 돌려줍니다. P가 0.05보다 작으면 \"유의한 차이\"라고 말합니다."),
  GAP(100),
  H3("박스플롯 읽는 법"),
  B("가운데 가로선 = 중앙값"),
  B("상자 = 전체의 25%~75%가 들어 있는 구간"),
  B("수염 = 그 바깥 (보통 1.5배 사분위범위까지)"),
  B("따로 찍힌 점 = 각 데이터셋 하나하나"),

  H2("차근차근"),
  H3("비교한 모델 5종"),
  TBL(["이름", "무엇인가"], [
    ["CATS + RF", "파마코포어 기술자 + 랜덤포레스트"],
    ["ECFP + RF", "지문 + 랜덤포레스트"],
    ["ECFP + MLP", "지문 + 다층 퍼셉트론(간단한 신경망)"],
    ["SMILES + JMM (no decoder)", "이 논문 모델에서 디코더만 뗀 것"],
    ["SMILES + JMM", "이 논문의 완성형"],
  ], [3400, 5600]),
  GAP(100),
  H3("결과 세 가지"),
  N("모델 5종 전부 Test_OOD에서 성능이 떨어졌다. 대략 0.80 → 0.60"),
  N("같은 분자들에 𝕌(x)를 매기니 Test_OOD 쪽이 유의하게 높았다"),
  N("데이터셋 33개 전부에서 같은 방향이었다 (Figure 2f의 모든 줄에 별표)"),
  GAP(100),
  BOX("0.60이 어느 정도인가", [
    "균형정확도는 0.5가 찍기입니다.",
    "0.60이면 찍기보다 조금 나은 수준이라는 뜻입니다.",
    "학습 분포 안에서 0.80이던 모델이 밖에 나가면 거의 반반이 됩니다.",
  ], WARM, RED),
  GAP(100),
  P("세 번째가 특히 중요합니다. 한 데이터셋에서만 잘 되는 지표는 우연일 수 있지만, 33개 전부에서 같은 방향이면 믿을 만합니다."),

  H2("원문 대조"),
  CMP([
    ["balanced accuracy", "균형정확도"],
    ["paired, two-sided, Wilcoxon signed-rank test", "짝지은 양측 윌콕슨 부호순위 검정"],
    ["Such performance degradation is a hallmark of OOD data",
     "이런 성능 저하는 OOD 데이터의 전형적인 징표다"],
    ["in line with existing literature", "기존 문헌 수준과 비슷하다"],
    ["two-sided Kolmogorov–Smirnov (KS) test", "양측 KS 검정"],
    ["denoted with an asterisk", "별표로 표시된"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 6장
push(
  H1("6장.  검증 ② — 다른 지표들과 숫자로 붙여 보면"),
  P("(슬라이드 7  ·  논문 Table 1, Table 2)", { color: GRAY, size: 19 }),

  H2("먼저 알아야 할 것"),
  H3("순위 상관 — Spearman과 Kendall τ"),
  P("두 값이 같은 방향으로 움직이는지를 순위로 재는 것입니다. +1이면 완전히 같은 방향, −1이면 완전히 반대, 0이면 아무 관계 없음."),
  GAP(60),
  BOX("표에 음수가 많은 이유", [
    "\"학습셋과 유사도가 높다\"  ↔  \"불친숙도가 낮다\"",
    "두 값은 반대 방향으로 움직이는 것이 자연스럽습니다. 그래서 음수가 나옵니다.",
    "부호가 아니라 절댓값을 보세요. 클수록 관계가 뚜렷합니다.",
  ]),
  GAP(100),
  H3("임베딩 거리 (Mahalanobis distance)"),
  P("z 벡터가 학습 데이터 뭉치에서 얼마나 떨어져 있는지를 재는 거리입니다. 단순한 직선거리와 달리 데이터 뭉치가 퍼진 모양을 감안합니다. 이 논문에서는 비교 대상으로 나옵니다."),

  H2("차근차근"),
  H3("Table 1 — 세 지표가 '구조적 거리'를 얼마나 반영하나"),
  TBL(["지표", "골격 유사도", "분자핵심 중첩", "파마코포어 유사도"], [
    ["불친숙도 𝕌(x)", "−0.46 ± 0.03", "−0.32 ± 0.04", "−0.24 ± 0.04"],
    ["임베딩 거리", "−0.36 ± 0.03", "−0.56 ± 0.02", "−0.10 ± 0.05"],
    ["불확실성 ℍ(y|x)", "−0.15 ± 0.04", "0.02 ± 0.04", "−0.15 ± 0.04"],
  ], [2400, 2200, 2200, 2200]),
  GAP(100),
  P("읽는 법 — 맨 아랫줄을 보세요. 불확실성은 −0.15, +0.02, −0.15입니다. 거의 0입니다."),
  GAP(60),
  BOX(null, [
    "불확실성은 \"이 분자가 학습 분자와 구조적으로 얼마나 다른가\"를 거의 보지 않는다는 뜻입니다.",
    "불친숙도는 세 가지 유사도 모두와 뚜렷하게 상관합니다.",
    "두 지표가 애초에 다른 것을 본다는 직접 증거입니다.",
  ]),
  GAP(100),
  P("한 가지 흥미로운 점이 있습니다. 임베딩 거리(−0.36)보다 불친숙도(−0.46)가 골격 유사도를 더 잘 반영합니다. 둘 다 같은 z에서 나온 값인데도 그렇습니다. 저자의 해석은 이렇습니다 — \"z로부터 분자를 실제로 복원해 보는 것\"이 \"z가 어디에 있는지 보는 것\"보다 많은 정보를 준다."),
  GAP(140),
  H3("Table 2 — 어느 지표가 '성능'을 더 잘 예측하나"),
  P("방법이 조금 특이합니다. 분자들을 어떤 지표 순으로 8등분한 뒤, 각 구간에서 실제 성능을 재고, \"구간 순서\"와 \"성능 순서\"가 얼마나 맞아떨어지는지를 Kendall τ로 잽니다. 1.0이면 완벽."),
  GAP(60),
  TBL(["구간화 기준", "균형정확도", "적중률", "정밀도"], [
    ["골격 유사도", "0.42 ± 0.06", "0.51 ± 0.04", "0.50 ± 0.06"],
    ["분자핵심 중첩", "0.28 ± 0.07", "0.22 ± 0.09", "0.25 ± 0.07"],
    ["파마코포어 유사도", "0.19 ± 0.07", "0.37 ± 0.09", "0.43 ± 0.08"],
    ["임베딩 거리", "0.36 ± 0.06", "0.24 ± 0.09", "0.29 ± 0.08"],
    ["불확실성 ℍ(y|x)", "0.51 ± 0.08", "0.62 ± 0.06", "0.72 ± 0.04"],
    ["불친숙도 𝕌(x)", "0.58 ± 0.04", "0.52 ± 0.07", "0.52 ± 0.05"],
  ], [2700, 2100, 2100, 2100]),
  GAP(100),
  B("균형정확도를 예측하는 데는 불친숙도가 1위 (0.58)"),
  B("적중률과 정밀도를 예측하는 데는 불확실성이 1위 (0.62 / 0.72)"),
  GAP(60),
  P("어느 한쪽이 이긴 것이 아니라 서로 다른 것을 잘 봅니다. 그래서 논문은 \"둘은 보완적\"이라고 결론 냅니다."),

  H2("원문 대조"),
  CMP([
    ["reliability metric", "신뢰도 지표"],
    ["Mahalanobis distance of embeddings (z vectors)", "임베딩(z 벡터)의 마할라노비스 거리"],
    ["Highest correlations are reported in bold", "가장 높은 상관은 굵게 표시"],
    ["Molecules are binned into eight bins per dataset", "데이터셋마다 분자를 8개 구간으로 나눈다"],
    ["A correlation of 1.0 indicates perfect model calibration",
     "상관 1.0이면 모델 보정이 완벽하다는 뜻"],
    ["bins are ordered to reflect low to high confidence",
     "구간은 신뢰도가 낮은 쪽부터 높은 쪽 순으로 정렬"],
    ["fail to capture the 'chemical nuances'", "화학적 미묘함을 잡아내지 못한다"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 7장
push(
  H1("7장.  검증 ③ — 실제 구매 가능한 140만 개에 돌려 보면"),
  P("(슬라이드 8)", { color: GRAY, size: 19 }),

  H2("먼저 알아야 할 것"),
  H3("상용 스크리닝 라이브러리"),
  P("회사가 판매하는 화합물 모음입니다. Asinex, Specs, Enamine 같은 회사들이 수십만 개씩 카탈로그로 갖고 있고, 주문하면 실제로 배송됩니다. 가상의 분자가 아니라 지금 당장 실험할 수 있는 분자들입니다."),
  GAP(100),
  H3("KS 검정 (Kolmogorov–Smirnov)"),
  P("두 분포가 다른지를 보는 검정입니다. 통계량 D는 두 누적분포 곡선 사이의 가장 큰 세로 간격입니다."),
  B("D = 0  →  두 분포가 완전히 같다"),
  B("D = 1  →  전혀 겹치지 않는다"),

  H2("차근차근"),
  P("세 라이브러리를 합쳐 고유 분자 1,395,422개를 모으고, 33개 타깃 모델 전부로 추론했습니다. 분자 × 타깃 = 약 4,600만 건입니다."),
  GAP(100),
  TBL(["무엇을 비교했나", "라이브러리 vs Test_ID", "Test_OOD vs Test_ID"], [
    ["(a)  학습셋과의 유사도", "D = 0.499", "D = 0.279"],
    ["(b)  불확실성 ℍ(y|x)", "D = 0.181", "D = 0.155"],
    ["(c)  불친숙도 𝕌(x)", "D = 0.999", "D = 0.368"],
  ], [3400, 2800, 2800]),
  GAP(100),
  P("세 줄을 차례로 읽어 봅시다."),
  N("(a) 실제로 사려는 라이브러리는 Test_OOD보다도 학습셋에서 멉니다. 즉 논문이 어렵게 만든 시험보다 현실이 더 어렵습니다"),
  N("(c) 𝕌(x)로 보면 D = 0.999 — 거의 완벽히 갈라집니다. 라이브러리와 시험셋이 사실상 겹치지 않는다는 뜻입니다"),
  N("(b) 그런데 불확실성으로 보면 D = 0.181 — 사실상 구분하지 못합니다"),
  GAP(100),
  BOX("이 세 숫자가 이 논문에서 가장 설득력 있는 부분입니다", [
    "강한 분포 이동 앞에서 불확실성은 거의 무력해집니다.",
    "불친숙도는 그 상황을 정확히 집어냅니다.",
    "저자도 \"uncertainty estimation is unreliable on strongly OOD data\"라고 적으며 선행 연구 3건을 인용합니다.",
  ], WARM, RED),
  GAP(140),
  H3("두 지표의 관계 (Figure 3d)"),
  P("140만 개 분자 전부에서 불확실성과 불친숙도의 상관을 쟀습니다."),
  new Paragraph({
    spacing: { before: 60, after: 120, line: 320 },
    indent: { left: 360 },
    children: [new TextRun({ text: "r  =  −0.03 ± 0.03", size: 24, bold: true, color: RED, font: KO })],
  }),
  P("사실상 0입니다. 두 값은 서로 독립입니다."),
  GAP(60),
  BOX("흔한 오해", [
    "\"독립\"은 \"둘 다 쓸모없다\"는 뜻이 아닙니다.",
    "\"서로 다른 정보를 준다\"는 뜻입니다. 그래서 하나만 보면 놓치는 경우가 생기고, 둘 다 봐야 합니다.",
  ]),

  H2("원문 대조"),
  CMP([
    ["commercially available molecules", "상용 구매 가능 분자"],
    ["strong distribution shifts", "강한 분포 이동"],
    ["KS test statistics (D)", "KS 검정 통계량 D"],
    ["utopia point", "여러 목표가 모두 최선인 가상의 점 (8장에서 사용)"],
    ["predicted as generally bioactive across all drug targets",
     "모든 타깃에서 두루 활성으로 예측된"],
    ["uncertainty estimation is unreliable on strongly OOD data",
     "강한 OOD 데이터에서는 불확실성 추정을 믿을 수 없다"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 8장
push(
  H1("8장.  실제 실험 ① — 18만 개에서 60개를 고르기까지"),
  P("(슬라이드 9)", { color: GRAY, size: 19 }),

  H2("먼저 알아야 할 것"),
  H3("키나아제(kinase)가 무엇인가"),
  P("다른 단백질에 인산기(-PO₃)를 붙이는 효소입니다. 인산기가 붙으면 그 단백질의 스위치가 켜지거나 꺼집니다. 세포 안의 신호 전달을 담당하므로, 암이나 염증에서 고장 나는 일이 많고 그래서 약 표적으로 인기가 많습니다."),
  B("PIM1 — 혈액암과 관련된 키나아제. 이 논문의 학습 데이터 1,443개"),
  B("CDK1 — 세포 분열을 조절하는 키나아제. 학습 데이터 312개. 이 연구의 다른 어디에도 쓰지 않은 완전 독립 타깃입니다"),
  GAP(100),
  H3("ATP 모방 코어"),
  P("키나아제는 ATP를 가져다 인산기를 떼어 씁니다. 그러니 ATP가 앉는 자리에 대신 끼어들어 앉으면 효소가 일을 못 합니다. 그래서 키나아제 저해제는 대개 ATP를 닮은 고리 구조를 갖습니다. 논문이 라이브러리를 거를 때 이 조건을 넣은 이유입니다."),
  GAP(100),
  H3("utopia point"),
  P("목표가 여러 개인데 전부 최고로 만들 수는 없을 때 쓰는 방법입니다. \"모든 목표가 최고치인 가상의 점\"을 찍어 두고, 실제 후보들 중 그 점에서 가까운 순으로 고릅니다."),

  H2("차근차근"),
  H3("선정 4단계"),
  N("Specs 라이브러리(2025년 4월)를 받아 약 180,000개로 거른다"),
  N("세 목표로 순위를 매긴다 — 예측 활성 𝔼(y|x)는 높게, 불확실성 ℍ(y|x)와 불친숙도 𝕌(x)는 전략에 따라"),
  N("학습셋이나 이미 고른 분자와 Tanimoto 0.70 이상이면 탈락시킨다"),
  N("타깃당 전략별 10개씩 = 30개, 두 타깃 합계 60개를 구입한다"),
  GAP(100),
  H3("1단계의 거르기 조건 — 왜 이런 걸 거나"),
  TBL(["조건", "무엇을 거르나"], [
    ["분자량 200~600", "너무 작으면 결합이 약하고, 너무 크면 안 녹고 세포에 못 들어간다"],
    ["logP < 6", "logP는 기름에 녹는 정도. 너무 높으면 물(실험 완충액)에 안 녹는다"],
    ["극성 표면적 20~140 Å²", "막을 통과할 수 있는 범위"],
    ["수소결합 주개 < 6", "너무 많으면 막 통과가 어렵다"],
    ["회전 가능 결합 < 10", "너무 흐느적거리면 표적에 잘 안 맞는다"],
    ["반응성 작용기 제거", "말단 에논 · 이소시아네이트 · 퀴논 · 방향족 니트로 ·¶아지드 · 에폭사이드. 어세이를 교란한다"],
    ["키나아제 적합성", "ATP 모방 코어, 고리 2개 이상 등.¶임상에 간 키나아제 저해제의 98.6%가 이 조건을 통과한다"],
  ], [2600, 6400]),
  GAP(140),
  H3("세 가지 선정 전략"),
  TBL(["전략", "불확실성 ℍ", "불친숙도 𝕌", "어떤 분자를 고르게 되나"], [
    ["A", "높음 ↑", "낮음 ↓", "익숙한 영역인데 답이 애매한 것"],
    ["B", "낮음 ↓", "낮음 ↓", "익숙하고 확신도 있는 것"],
    ["C", "낮음 ↓", "높음 ↑", "낯선데 확신은 있는 것"],
  ], [900, 1700, 1700, 4700]),
  GAP(100),
  P("세 전략 모두 예측 활성 𝔼(y|x)는 높게 잡습니다. 차이는 나머지 두 지표를 어느 방향으로 두느냐입니다."),
  GAP(100),
  BOX("3단계가 중요합니다", [
    "Tanimoto 0.70 이상을 탈락시킨 것은, 모델을 일부러 학습 분포 밖으로 더 밀어내기 위한 조치입니다.",
    "그 결과 고른 60개의 학습셋 최대 Tanimoto는 PIM1 0.28 ± 0.05, CDK1 0.28 ± 0.06이었습니다.",
    "0-2에서 본 기준으로 보면 전부 \"남남\" 수준입니다. 쉬운 분자를 골라 성공한 것이 아니라는 뜻입니다.",
  ]),

  H2("원문 대조"),
  CMP([
    ["prospective virtual screening", "전향적 가상 스크리닝.¶예측을 먼저 하고 나중에 실험으로 확인하는 것"],
    ["retrospective", "후향적. 이미 답을 아는 데이터로 사후 검증하는 것"],
    ["relaxed rule-of-five and Veber criteria", "완화된 리핀스키 5규칙과 베버 기준"],
    ["to prevent assay interference", "어세이 교란을 막기 위해"],
    ["ATP mimetic core", "ATP를 흉내 내는 핵심 골격"],
    ["hinge interaction", "키나아제 경첩 부위와의 상호작용"],
    ["intentionally permissive for new chemotypes", "새로운 화학 유형을 일부러 넉넉히 허용하는"],
    ["three complementary objectives", "서로 보완하는 세 가지 목표"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 9장
push(
  H1("9장.  실제 실험 ② — 60개 측정 결과"),
  P("(슬라이드 10)", { color: GRAY, size: 19 }),

  H2("먼저 알아야 할 것"),
  H3("ADP-Glo 키나아제 어세이"),
  P("키나아제가 일을 하면 ATP가 ADP로 바뀝니다. 그러니 생긴 ADP의 양을 재면 효소가 얼마나 일했는지 알 수 있습니다. ADP-Glo는 그 ADP를 빛으로 바꿔 측정하는 방식입니다. 빛이 약하면 효소가 억제된 것입니다."),
  GAP(100),
  H3("단일농도 스크리닝과 용량반응"),
  N("단일농도(point screening) — 일단 모두 같은 농도(10 µM)로 한 번씩 측정해 유망한 것을 추린다"),
  N("용량반응(dose–response) — 추린 것만 농도를 바꿔가며 다시 측정해 S자 곡선을 그린다. 절반이 억제되는 농도가 IC50이다"),
  GAP(60),
  P("이 논문은 10 µM에서 0.0046 µM까지 농도를 낮춰가며 측정했습니다. 각 농도는 기술적 삼중복(같은 시료를 3번)으로 쟀습니다."),
  GAP(100),
  H3("양성 대조"),
  P("실험이 제대로 돌아가는지 확인하려면 \"확실히 듣는 약\"을 같이 넣어 봐야 합니다. PIM1에는 AZD1208, CDK1에는 dinaciclib을 썼습니다. 결과 히트맵에서 이 둘이 각각 2%와 1%로 나온 것이, 실험이 정상 작동했다는 증거입니다."),

  H2("차근차근"),
  H3("단일농도 결과"),
  TBL(["", "PIM1 (학습 1,443개)", "CDK1 (학습 312개)"], [
    ["초기 히트 (억제 > 50%)", "4개", "1개"],
    ["약한 히트 (억제 > 25%)", "6개", "5개"],
    ["용량반응 확인 후 적중률", "17 %  (5/30)", "7 %  (2/30)"],
  ], [3400, 2800, 2800]),
  GAP(100),
  P("CDK1이 낮은 이유로 저자는 학습셋 크기(312개)를 지목합니다."),
  GAP(140),
  H3("IC50이 나온 7개"),
  TBL(["화합물", "전략", "IC50", "비고"], [
    ["4  (PIM1)", "A", "1.5 ± 0.4 µM", "뚜렷한 S자 부분억제 곡선"],
    ["10 (PIM1)", "A", "0.92 ± 0.97 µM", "뚜렷한 S자 부분억제 곡선"],
    ["25 (PIM1)", "C", "0.87 ± 0.5 µM", "뚜렷한 S자 부분억제 곡선"],
    ["9  (PIM1)", "A", "≈ 5.9 µM", "곡선 미완성 → 상한 추정치"],
    ["18 (PIM1)", "B", "≈ 7.5 µM", "곡선 미완성 → 상한 추정치"],
    ["40 (CDK1)", "A", "2.9 ± 0.75 µM", "완전한 용량반응 곡선"],
    ["33 (CDK1)", "A", "≈ 3.4 µM", "상한 추정치"],
  ], [1700, 1000, 2100, 4200]),
  GAP(100),
  BOX("부분 억제(partial inhibition)란", [
    "농도를 아무리 올려도 활성이 0%까지 내려가지 않고 중간에서 멈추는 현상입니다.",
    "알로스테릭 결합(ATP 자리가 아닌 다른 곳에 붙음)이거나, 화합물의 용해도 한계일 수 있습니다.",
    "",
    "이 때문에 IC50 추정의 오차가 큽니다. 10번 화합물의 0.92 ± 0.97 µM을 보세요 — 오차가 값만큼 큽니다.",
    "\"약 1 µM 근처\" 정도로 읽는 것이 맞습니다.",
  ]),
  GAP(140),
  H3("가장 중요한 관찰 — 여기를 놓치면 논문을 거꾸로 이해합니다"),
  B("IC50이 나온 7개 중 5개가 전략 A입니다. 즉 불확실성은 높고 불친숙도는 낮은 쪽입니다", 0, { bold: true }),
  B("전략 A · B · C 사이의 활성 차이는 통계적으로 유의하지 않았습니다 (n.s.)"),
  GAP(60),
  BOX(null, [
    "따라서 이 논문은 \"낯선 분자를 고르면 더 잘 나온다\"고 말하지 않습니다.",
    "오히려 실측 결과는 그 반대에 가깝습니다.",
    "",
    "𝕌(x)의 쓸모는 좋은 것을 고르는 기준이 아니라, 못 믿을 것을 거르는 기준입니다.",
    "낯선 쪽(전략 C)에서도 0.87 µM짜리 25번이 나오긴 했지만, 전체 분포로 보면 A가 유리했습니다.",
  ], WARM, RED),

  H2("원문 대조"),
  CMP([
    ["point screening", "단일농도 스크리닝"],
    ["technical triplicates", "기술적 삼중복 (같은 시료를 3번 측정)"],
    ["dose–response curve", "용량반응 곡선"],
    ["partial inhibition", "부분 억제"],
    ["upper-bound potency estimates", "역가의 상한 추정치"],
    ["incomplete curve resolution", "곡선이 끝까지 그려지지 않음"],
    ["n.s.", "not significant. 통계적으로 유의하지 않음"],
    ["initial hits / weak hits", "초기 히트 / 약한 히트"],
    ["positive control", "양성 대조 (확실히 듣는 약)"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 10장
push(
  H1("10장.  정리 — 이 논문으로 되는 것과 안 되는 것"),
  P("(슬라이드 11)", { color: GRAY, size: 19 }),

  H2("논문이 실제로 보인 것"),
  N("재구성 오차로 \"모델에게 낯선 정도\"를 숫자화할 수 있다"),
  N("그 숫자를 얻는 대가로 예측 정확도를 깎지 않는다 (P = 0.499)"),
  N("불친숙도와 불확실성은 독립이며(r = −0.03), 성능 예측력에서는 서로 보완한다"),
  N("강한 분포 이동에서는 불확실성이 거의 무력하지만(D = 0.181) 불친숙도는 작동한다(D = 0.999)"),
  N("작은 학습셋(1,443 / 312개)으로도 60개 중 7개에서 저마이크로몰 활성을 찾았다"),

  H2("이 논문이 하지 않는 것"),
  P("우리 과제에 적용할 때 가장 오해하기 쉬운 부분입니다. 아래 세 가지는 논문 자체의 숫자입니다."),
  GAP(60),
  TBL(["근거", "수치", "뜻"], [
    ["JMM을 써도 OOD 성능", "0.80 → 0.60  (그대로)", "정확도는 전혀 오르지 않는다"],
    ["디코더 유무에 따른 차이", "P = 0.499 / 0.594", "통계적으로 차이 없음"],
    ["전략 A·B·C 간 활성 차이", "n.s.", "선정 전략으로 성능이 올라간 것이 아니다"],
  ], [2700, 2600, 3700]),
  GAP(100),
  BOX("그래서 결론은 이렇습니다", [
    "이 논문은 \"천연물 예측을 믿을 수 있게\" 만들어 주지 않습니다.",
    "\"얼마나 못 믿는지, 그중 무엇은 그나마 믿을 만한지\"를 알려 줍니다.",
  ], WARM, RED),
  GAP(140),

  H2("게다가 — 이 논문의 OOD는 천연물이 아닙니다"),
  P("우리 과제에 옮길 때 반드시 짚어야 할 점입니다."),
  B("스크리닝 라이브러리는 Asinex · Specs · Enamine — 전부 합성 약물유사 화합물입니다"),
  B("전향 실험에서는 \"ATP 모방 코어, 고리 2개 이상\" 필터로 오히려 키나아제 화학공간 쪽으로 더 좁혔습니다"),
  B("즉 이 논문이 다룬 분포 이동은 \"합성물 안에서 골격이 다른 정도\"입니다"),
  GAP(60),
  P("합성물에서 천연물로 넘어가는 점프는 그보다 훨씬 큽니다. 그 폭을 실제로 측정한 것은 이 논문이 아니라 Cockroft 2019입니다 (AUROC 0.94~0.99 → 0.70~0.85)."),
  GAP(140),

  H2("그래도 쓸 데가 있다 — 네 가지"),
  TBL(["", "용도", "구체적으로"], [
    ["①", "정직한 보고", "\"후보 N개 중 M개는 적용 범위 밖\"을 숫자로 말할 수 있다.¶지금은 말할 근거가 없다"],
    ["②", "천연물 내부 순위", "천연물 수천 개를 𝕌(x)로 줄 세워 낮은 쪽부터 실험한다.¶학습 데이터와 '말이 통하는' 천연물이 먼저 올라온다"],
    ["③", "실험 설계", "𝕌(x) 구간별로 몇 개씩 뽑아 측정하면,¶천연물 구간의 성능을 처음으로 잴 수 있다"],
    ["④", "심사 방어", "\"학습 범위 밖을 어떻게 믿느냐\"는 질문에¶정량적으로 답할 수 있다"],
  ], [600, 2000, 6400]),
  GAP(100),
  P("②가 실무적으로 가장 큽니다. 1,000개를 다 못 믿는 상황에서, 어느 100개부터 볼지는 정해 줍니다."),
  GAP(140),

  H2("저자가 밝힌 한계와 다음 단계"),
  B("강한 OOD에서는 불확실성 추정을 신뢰할 수 없다고 명시하며 선행 연구 3건을 인용했습니다"),
  B("일회성 스크리닝을 넘어 능동학습(active learning)이나 강화학습으로 확장할 것을 제안합니다"),
  B("𝕌(x)의 절대 기준선은 제시하지 않았습니다. 데이터셋마다 상대적으로 해석해야 합니다"),
  GAP(100),
  BOX("마지막 항목이 우리에게는 숙제입니다", [
    "\"이 값을 넘으면 버려라\"라는 기준선을 정하려면 우리 데이터로 보정해야 합니다.",
    "그런데 보정하려면 천연물 실측 데이터가 필요합니다. 여기서 한 바퀴 돕니다.",
    "",
    "그래서 실행 순서는 이렇습니다.",
    "1.  라벨·분할 정리 + 미세조정으로 정확도 자체를 먼저 올린다",
    "2.  𝕌(x)를 붙여 천연물 후보를 줄 세우고, 낮은 쪽부터 20~50개를 실측한다",
    "3.  그 실측으로 𝕌(x) 기준선을 정한다. 이때부터 \"믿을 수 있는 범위\"를 말할 수 있다",
  ], WARM, "E0A033"),
  new Paragraph({ children: [new PageBreak()] }),
);

// ════════════════════════════════════════════════ 부록
push(
  H1("부록 A.  논문에 자주 나오는 표현"),
  P("본문에서 다루지 않았지만 읽다 보면 걸리는 표현들입니다."),
  GAP(60),
  CMP([
    ["bioactivity", "생물활성. 분자가 단백질에 작용하는 성질"],
    ["hit / hit molecule", "스크리닝에서 걸린 활성 분자"],
    ["hit rate", "적중률"],
    ["enrichment factor", "농축 배수. 무작위로 뽑았을 때보다 몇 배 잘 찾았나"],
    ["pharmacophore", "파마코포어. 작용에 필요한 성질들의 3차원 배치"],
    ["molecular core / scaffold", "분자의 핵심 골격"],
    ["MCS (maximal common substructure)", "두 분자가 공유하는 가장 큰 부분구조"],
    ["Tanimoto coefficient", "타니모토 계수 (닮음 지표)"],
    ["ECFP (extended-connectivity fingerprint)", "확장 연결성 지문"],
    ["latent space", "잠재 공간. 모델 내부의 압축된 표현이 사는 공간"],
    ["embedding", "임베딩. 그 압축된 벡터"],
    ["fine-tuning", "미세조정. 사전학습된 모델을 특정 과제에 맞춰 조금 더 학습시키는 것"],
    ["pretraining", "사전학습"],
    ["Monte Carlo cross-validation", "데이터를 무작위로 여러 번 나눠 평가하는 교차검증"],
    ["early stopping", "조기 종료. 검증 성능이 더 안 좋아지면 학습을 멈추는 것"],
    ["mini batch", "미니배치. 한 번에 처리하는 데이터 묶음"],
    ["learning rate", "학습률. 한 번에 얼마나 크게 고칠지"],
    ["de novo design", "분자를 처음부터 새로 설계하는 분야"],
    ["active learning", "능동학습. 모델이 \"이걸 측정해 달라\"고 요청하며 반복하는 방식"],
    ["prospective / retrospective", "전향적(미리 예측 후 실험) / 후향적(답을 알고 사후 검증)"],
  ]),
  GAP(200),

  H1("부록 B.  기호 일람"),
  SYM([
    ["𝔼(y|x)", "분자 x가 활성일 것이라는 예측값"],
    ["ℍ(y|x)", "불확실성 (엔트로피)"],
    ["𝕌(x)", "불친숙도 — 이 논문이 만든 지표"],
    ["ℒ", "손실 (loss)"],
    ["z", "압축된 임베딩 벡터"],
    ["tᵢ", "SMILES의 i번째 글자(토큰)"],
    ["t<ᵢ", "그 앞까지의 글자들"],
    ["|x|", "SMILES의 글자 수"],
    ["V", "쓰는 글자 종류 수 (이 연구에서 35)"],
    ["P", "p값. 0.05 미만이면 유의"],
    ["D", "KS 검정 통계량. 0~1"],
    ["r", "상관계수 (Spearman 등). −1 ~ +1"],
    ["τ", "켄달 순위상관계수"],
    ["α", "유의수준. 보통 0.05"],
    ["n.s.", "유의하지 않음"],
    ["s.e.m.", "평균의 표준오차"],
  ]),
  GAP(200),

  H1("부록 C.  원문을 직접 읽을 때 추천 순서"),
  P("논문은 결과부터 나오는 구조라, 앞에서부터 읽으면 용어가 설명 없이 쏟아집니다. 이 순서를 권합니다."),
  GAP(60),
  N("Abstract (1쪽) — 전체 윤곽만 잡는다. 모르는 단어는 넘어간다"),
  N("Figure 1 전체와 그 설명문 — 그림이 논문의 설계를 압축하고 있다"),
  N("Methods의 'Data preprocessing and analysis' (8쪽) — 데이터가 무엇인지부터 확인한다"),
  N("Methods의 수식 (1)·(2) — 이 문서 3장과 대조하며 읽는다"),
  N("Results를 처음부터 — 이제 용어가 통한다"),
  N("Table 1과 Table 2 — 이 문서 6장과 대조한다"),
  N("Discussion (7~8쪽) — 저자가 스스로 무엇을 주장하고 무엇을 주장하지 않는지 확인한다"),
  GAP(140),
  BOX("읽으면서 계속 물어볼 질문 두 가지", [
    "① 지금 이 숫자는 '학습 분포 안'에서 잰 것인가, '밖'에서 잰 것인가?",
    "② 이 결과는 예측을 더 정확하게 만든 것인가, 아니면 신뢰도를 판단하게 해 준 것인가?",
    "",
    "이 논문의 거의 모든 주장이 이 두 축 위에 있습니다.",
  ]),
  GAP(200),
  P("자료 공개", { bold: true, size: 22 }),
  B("논문 (오픈액세스) — https://www.nature.com/articles/s42256-026-01216-w"),
  B("데이터 — Zenodo  doi 10.5281/zenodo.14865513"),
  B("코드·데이터 — figshare  doi 10.6084/m9.figshare.30665201.v1"),
  B("코드 — GitHub (molML)"),
  B("상용 스크리닝 라이브러리 데이터는 라이선스 문제로 제외되어 있습니다"),
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
