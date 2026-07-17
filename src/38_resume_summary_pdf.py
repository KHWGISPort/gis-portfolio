# -*- coding: utf-8 -*-
"""
[제출용] 이력서에 첨부할 요약 PDF를 만든다.

설계 원칙 (사용자 요청 반영):
  - 첫 페이지 상단에 '한눈 요약' 3~4줄
  - 3~4페이지 이내, 시각 요소(지도·표·사진) 삽입, 개발자용 내용(실행법·폴더구조 등) 전부 제외
  - "예측 모델"이 아니라 "스코어링 + 현장 검증" 프레임
  - 실패·한계를 숨기지 않고 강점으로 배치 ("모델의 한계를 현장으로 규명")
  - 결과 -> 방법 -> 검증 -> 성장 순서(시간순 아님)
  - 지표는 반드시 '의미'와 함께 (예: 적중률 46.4% = 무작위 대비 2.3배)
  - AI 활용을 정직하게 명시하되 '나의 판단' 역할을 분명히

[2차 개선 반영, 사용자 피드백]
  - 1페이지 하단 여백 제거: 지도를 키우고 '무엇을·왜'를 1페이지로 끌어올려 첫 장을 완결
  - '검증된 자리(초록) 145곳'을 결과에 추가 → 신규 후보(빨강)의 신뢰 근거
  - 8위 '진입 불가'를 위양성과 다른 색+각주로 구분 (모델은 적중, 현실 제약)

한글은 맑은 고딕 TTF를 PDF에 임베드해서, 어떤 뷰어에서도 글자가 보이게 한다.
"""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable, PageBreak,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

FONT_DIR = "C:/Windows/Fonts"
pdfmetrics.registerFont(TTFont("Malgun", f"{FONT_DIR}/malgun.ttf"))
pdfmetrics.registerFont(TTFont("MalgunBold", f"{FONT_DIR}/malgunbd.ttf"))
FB, FH = "Malgun", "MalgunBold"

NAVY = colors.HexColor("#1a2b4a")
RED = colors.HexColor("#c62828")
GREEN = colors.HexColor("#2e7d32")
AMBER = colors.HexColor("#d97706")
SLATE = colors.HexColor("#3b6ea5")   # '진입 불가'(모델은 적중, 현실 제약) 전용 색 — 위양성(빨강)과 구분
GRAY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#f4f6fa")
GREENBG = colors.HexColor("#eef6ee")
LINE = colors.HexColor("#cccccc")

S = {
    "title": ParagraphStyle("t", fontName=FH, fontSize=19, leading=24, textColor=NAVY, alignment=TA_CENTER),
    "sub": ParagraphStyle("s", fontName=FB, fontSize=10.5, leading=14, textColor=GRAY, alignment=TA_CENTER),
    "author": ParagraphStyle("a", fontName=FH, fontSize=11.5, leading=15, textColor=NAVY, alignment=TA_CENTER),
    "summary": ParagraphStyle("sm", fontName=FB, fontSize=10, leading=15.5, textColor=colors.HexColor("#1a1a1a")),
    "h2": ParagraphStyle("h2", fontName=FH, fontSize=13, leading=16, textColor=NAVY, spaceBefore=4, spaceAfter=7),
    "body": ParagraphStyle("b", fontName=FB, fontSize=9.7, leading=14.2, textColor=colors.HexColor("#222222")),
    "bodysp": ParagraphStyle("bs", fontName=FB, fontSize=9.7, leading=14.2, textColor=colors.HexColor("#222222"), spaceAfter=7),
    "statnum": ParagraphStyle("sn", fontName=FH, fontSize=17, leading=19, textColor=RED, alignment=TA_CENTER),
    "statlbl": ParagraphStyle("sl", fontName=FB, fontSize=8, leading=10.5, textColor=GRAY, alignment=TA_CENTER),
    "cap": ParagraphStyle("c", fontName=FB, fontSize=8, leading=11, textColor=GRAY, alignment=TA_CENTER),
    "small": ParagraphStyle("sms", fontName=FB, fontSize=8, leading=11, textColor=GRAY),
    "valid": ParagraphStyle("v", fontName=FB, fontSize=9.3, leading=13.5, textColor=colors.HexColor("#1a1a1a")),
    "foot": ParagraphStyle("f", fontName=FH, fontSize=10, leading=13, textColor=NAVY, alignment=TA_CENTER),
}


def h2(text):
    return Paragraph(text, S["h2"])


def summary_box():
    txt = (
        "서울 전체 상권의 <b>편의점 매출 데이터로 '좋은 입지의 조건'을 학습</b>해, 중랑구를 100m 격자로 나눠 "
        "출점 후보지에 점수를 매겼습니다. 도로·하천·산지처럼 물리적으로 출점이 불가능한 곳을 걸러 "
        "<b>539개 후보지</b>를 도출한 뒤, <b>상위 후보 5곳을 직접 답사</b>해 모델이 맞힌 것과 놓친 것을 규명했습니다. "
        "핵심은 점수를 내는 데서 그치지 않고, <b>그 점수가 현장에서 성립하는지까지 확인했다</b>는 점입니다."
    )
    t = Table([[Paragraph(txt, S["summary"])]], colWidths=[171 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("LINEBEFORE", (0, 0), (0, -1), 3, RED),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def stat_cell(num, label):
    return [Paragraph(num, S["statnum"]), Spacer(1, 1), Paragraph(label, S["statlbl"])]


def stats_row():
    cells = [
        stat_cell("539개", "물리적 출점 가능 지역 중<br/>도출한 신규 후보지"),
        stat_cell("25.8%", "도로·하천·산지 등<br/>출점불가 지역 마스킹"),
        stat_cell("46.4%", "실제 매출 상위권 적중률<br/>(무작위 대비 2.3배)"),
        stat_cell("5곳", "상위 후보지<br/>직접 현장 답사"),
    ]
    t = Table([cells], colWidths=[42.75 * mm] * 4)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def validation_line():
    """검증된 자리(초록 145곳)를 모델 타당성 근거로 제시 — 신규 후보(빨강)의 신뢰 근거."""
    txt = (
        "<b>모델 타당성 검증</b> &nbsp;—&nbsp; 실제 편의점이 영업 중인 우량 자리 <b>145곳(지도의 초록)을 모델도 "
        "'고득점'으로 재현</b>했습니다. 모델이 '좋은 입지'를 제대로 학습했으며, 신규 후보(빨강)를 신뢰할 수 있다는 근거입니다."
    )
    t = Table([[Paragraph(txt, S["valid"])]], colWidths=[171 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREENBG),
        ("LINEBEFORE", (0, 0), (0, -1), 3, GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def pipeline_row():
    steps = ["데이터 정제\n(9종+SGIS)", "12개 입지\n피처 설계", "매출 학습\n(LightGBM)", "격자\n스코어링", "출점불가\n마스킹", "현장 답사\n검증"]
    row = []
    for i, s in enumerate(steps):
        row.append(Paragraph(s.replace("\n", "<br/>"), ParagraphStyle(
            "p", fontName=FB, fontSize=8, leading=10.5, textColor=NAVY, alignment=TA_CENTER)))
        if i < len(steps) - 1:
            row.append(Paragraph("→", ParagraphStyle("ar", fontName=FH, fontSize=11, textColor=RED, alignment=TA_CENTER)))
    widths = []
    for i in range(len(steps)):
        widths.append(24 * mm)
        if i < len(steps) - 1:
            widths.append(5.4 * mm)
    t = Table([row], colWidths=widths)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
    for i in range(len(steps)):
        col = i * 2
        style.append(("BACKGROUND", (col, 0), (col, 0), LIGHT))
        style.append(("BOX", (col, 0), (col, 0), 0.5, LINE))
    t.setStyle(TableStyle(style))
    return t


def metric_row():
    def card(big, name, mean):
        return [
            Paragraph(big, ParagraphStyle("mb", fontName=FH, fontSize=15, leading=17, textColor=NAVY, alignment=TA_CENTER)),
            Paragraph(name, ParagraphStyle("mn", fontName=FH, fontSize=8.3, leading=11, textColor=RED, alignment=TA_CENTER)),
            Spacer(1, 2),
            Paragraph(mean, ParagraphStyle("mm", fontName=FB, fontSize=7.8, leading=10.5, textColor=GRAY, alignment=TA_CENTER)),
        ]
    cells = [
        card("46.4%", "Top20% 적중률", "실제 매출 상위 20% 상권 중 46.4%를 모델도 상위권으로 지목. 무작위(20%)보다 <b>2.3배</b> 정확."),
        card("0.312", "순위 일치도(스피어만)", "실제 매출 순위와 예측 순위의 일치 정도(0=무작위, 1=완벽). 위치 정보만으로 '상대적 우열'을 유의미하게 구분."),
        card("설계 의도", "순위 스코어링", "절대 매출액 예측이 아닌, <b>후보지 간 상대 우열을 비교하는 '순위 산출'</b>에 집중하도록 처음부터 설계함."),
    ]
    t = Table([cells], colWidths=[57 * mm] * 3)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def compare_table():
    """v1->v3a 개선 과정 — 방법론적 실험/진단 역량을 보여주는 표."""
    data = [
        ["버전", "타깃 · 피처", "순위 일치도", "상위권 적중률"],
        ["v1", "총매출 · 기본 10피처", "0.268", "46.4%"],
        ["v2", "점포당매출 · 집객시설 추가 12피처", "0.242", "28.6%"],
        ["v3a (최종)", "총매출 · 집객시설 추가 12피처", "0.312", "46.4%"],
    ]
    t = Table(data, colWidths=[24 * mm, 87 * mm, 30 * mm, 30 * mm])
    style = [
        ("FONTNAME", (0, 0), (-1, -1), FB),
        ("FONTNAME", (0, 0), (-1, 0), FH), ("FONTNAME", (0, 3), (-1, 3), FH),
        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#eaf0f6")),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    t.setStyle(TableStyle(style))
    return t


VERDICT = [
    ("1위", "상봉역", "적중", GREEN, "지하철 개찰구 밖 무점포 확인, 낮·저녁 이중 유동인구"),
    ("3위", "타임호프", "조건부 적중", AMBER, "고령층 근린 상권, 무인마트의 취급 공백이 오히려 기회"),
    ("8위", "먹자골목", "진입 불가*", SLATE, "수요는 확실하나 빈 점포 없음(위반건축물 5건이 방증)"),
    ("2위", "금강사거리", "위양성", RED, "초등학교발 생활인구 착시, 현장 유동 거의 없음"),
    ("9위", "진로아파트", "위양성", RED, "격자가 순수 아파트 단지 내부 → 물리적 설치 불가"),
]


def verdict_table():
    header = ["순위", "장소", "판정", "현장에서 확인한 근거"]
    data = [header] + [[r, p, v, reason] for r, p, v, _, reason in VERDICT]
    t = Table(data, colWidths=[12 * mm, 25 * mm, 27 * mm, 107 * mm])
    style = [
        ("FONTNAME", (0, 0), (-1, -1), FB), ("FONTNAME", (0, 0), (-1, 0), FH), ("FONTNAME", (2, 1), (2, -1), FH),
        ("FONTSIZE", (0, 0), (-1, -1), 8.8),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, (_, _, _, color, _) in enumerate(VERDICT, start=1):
        style.append(("TEXTCOLOR", (2, i), (2, i), color))
    t.setStyle(TableStyle(style))
    return t


# 케이스별 상세 답사 기록 (사용자 현장 소견 원문)
NARRATIVES = [
    ("1위 · 상봉역 1~2번 출구 (상봉동) — 적중", GREEN,
     "초역세권이지만 개찰구 밖에는 편의점이 없어, 환승객과 역세권 생활인구가 미포섭 상태였다. 역 내부 storyway "
     "한 곳이 전부였고 외부 고정 상권도 약해 신규 진입 여지가 있다고 판단했다. 5-6시 관찰 당시 7호선 거주 배후의 "
     "퇴근 인파가 빠르게 오갔고, 군것질·컵라면 등 역 자체 수요는 충분해 보였다. 다만 2번 출구 쪽 역-건물 간 병목 "
     "구간이 있어 외부 매대 운영에는 민원·충돌 리스크가 있다고 봤다."),
    ("3위 · 타임호프 인근 (면목동) — 조건부 적중", AMBER,
     "골목 상권이나 사거리 인근에 교회 둘·음식점 셋이 있고, 10분간 20명 넘게 오간 유효 상권이었다. 관찰된 "
     "유동인구는 대부분 고령층. 바로 옆 무인 할인마트가 경쟁 요소이나, 직접 들어가 보니 가격 경쟁력이 낮고 "
     "담배·로또 취급이 없었으며 어르신들이 무인 기계를 어려워하고 있었다. 유인 편의점이라면 이 취급 공백과 "
     "응대에서 차별화 여지가 있다고 판단했다."),
    ("8위 · 상봉 먹자골목 (상봉동) — 수요는 있으나 진입 난항", SLATE,
     "고깃집·술집 중심의 조성된 먹자골목으로, 흡연 인구가 많고 숙취해소제·주류 수요가 뚜렷해 입지 조건 자체는 "
     "좋았다. 그러나 빠질 점포를 찾기 어려운 만실 상권이었고, 인근 위반건축물이 다수 존재해 \"벌금을 월세처럼 "
     "감수하며 버틸 만큼\" 자리가 귀하다는 방증으로 읽혔다. 답사 후 격자 위치를 재확인해 실제 후보지가 더 안쪽 "
     "길목이었음을 스스로 교정했고, 로드뷰로 재검증한 결과 결론은 동일했다."),
    ("2위 · 금강사거리 (면목동) — 위양성", RED,
     "모델이 높게 본 유동인구는 인접 초등학교(면남초)에서 비롯된 착시로 판단했다. 목요일 오후 실제 유동은 거의 "
     "없었고(흡연 중인 회사원과 노인 한 명), 재개발 현수막과 곳곳의 공실이 보이는 노후 주거지였다. 사거리 전체가 "
     "경사에 걸쳐 물류 진입도 불리했다. 데이터상 점수와 현장 활력의 괴리를 확인한 대표 사례다."),
    ("9위 · 진로아파트 — 위양성", RED,
     "고득점 격자가 아파트 단지 내부여서, 입지 자체는 좋으나 물리적 설치 가능성이 지극히 낮았다. 다만 단지 안에 "
     "순대·돈까스 노점이 열려 있었는데, 이는 주민이 '단지 안 소비'에 익숙하다는 신호로 해석했다. 인근 홈플러스 "
     "폐점이라는 거시적 공백까지 겹치면 잠재 수요는 있다고 봤다."),
]


def _hex(c):
    return "#%02x%02x%02x" % (int(c.red * 255), int(c.green * 255), int(c.blue * 255))


def narrative_flowables():
    title_base = ParagraphStyle("nt", fontName=FH, fontSize=9.8, leading=13, spaceBefore=6, spaceAfter=2)
    body = ParagraphStyle("nb", fontName=FB, fontSize=9.2, leading=13.3, textColor=colors.HexColor("#222222"), spaceAfter=8)
    out = []
    for title, color, text in NARRATIVES:
        out.append(Paragraph(f'<font color="{_hex(color)}">{title}</font>', title_base))
        out.append(Paragraph(text, body))
    return out


def photo_pair():
    p1 = Image("docs/fieldwork/photos/01_상봉역_05.jpg", width=82 * mm, height=61.5 * mm)
    p2 = Image("docs/fieldwork/photos/09_진로아파트_02.jpg", width=82 * mm, height=61.5 * mm)
    cap1 = Paragraph("<b>1위 상봉역 — 적중.</b> 초역세권이지만 개찰구 밖에 편의점이 없어 유동인구가 미포섭 상태였음.", S["cap"])
    cap2 = Paragraph("<b>9위 진로아파트 — 위양성.</b> 고득점 격자가 아파트 단지 내부였고, 실제로는 출점이 불가능했음.", S["cap"])
    t = Table([[p1, p2], [cap1, cap2]], colWidths=[85 * mm, 85 * mm])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 1), (-1, 1), 3)]))
    return t


if __name__ == "__main__":
    os.makedirs("outputs", exist_ok=True)
    out = "outputs/portfolio_resume_summary.pdf"
    doc = SimpleDocTemplate(out, pagesize=A4, topMargin=13 * mm, bottomMargin=11 * mm,
                            leftMargin=19.5 * mm, rightMargin=19.5 * mm)
    st = []

    # ===== 페이지 1: 한눈 요약 + 결과 + 무엇을·왜 (첫 장에서 완결) =====
    st.append(Paragraph("편의점 최적입지 스코어링 및 현장 검증", S["title"]))
    st.append(Paragraph("서울 공공데이터 기반 · 중랑구 100m 격자 분석 · 개인 프로젝트", S["sub"]))
    st.append(Spacer(1, 5))
    st.append(Paragraph("김현우", S["author"]))
    st.append(Spacer(1, 10))
    st.append(summary_box())
    st.append(Spacer(1, 14))

    st.append(h2("프로젝트 결과"))
    # 제목·범례 없는 컴팩트 지도를 원본 비율(세로/가로 1.297) 그대로 삽입 — 왜곡 방지 (범례는 아래 캡션이 담당)
    _hw = 88 * mm
    hero = Image("outputs/36_hero_for_pdf.png", width=_hw, height=_hw * 1.297)
    hero.hAlign = "CENTER"
    st.append(hero)
    st.append(Paragraph(
        "중랑구 1,858개 격자 스코어링. 빨강=신규 후보지(고득점·무점포), 초록=검증된 자리(고득점·기존점포), 갈색=출점불가.",
        S["cap"]))
    st.append(Spacer(1, 9))
    st.append(stats_row())
    st.append(Spacer(1, 9))
    st.append(validation_line())
    st.append(Spacer(1, 15))

    st.append(h2("무엇을, 왜"))
    st.append(Paragraph(
        "입지 분석·선정에서는 늘 <b>'어떤 요인에 얼마의 가중치를 줄 것인가'</b>를 정하는 일이 중요한 과제입니다. "
        "이 프로젝트는 그 과제를 <b>가중치를 데이터로 직접 학습</b>하는 방식으로 풀어보고자 시작했습니다. "
        "다만 목표는 <b>'매출 금액을 정확히 맞히는 예측'이 아니라, '어느 자리가 상대적으로 더 유망한가'를 줄 세우는 "
        "스코어링</b>입니다. 그래서 평가지표도 절대 오차가 아니라 <b>순위 일치도</b>를 중심에 두었습니다.", S["body"]))

    st.append(PageBreak())

    # ===== 페이지 2: 어떻게 했나 + 모델 성능(의미+개선 과정) =====
    st.append(h2("어떻게 했나"))
    st.append(pipeline_row())
    st.append(Spacer(1, 11))
    st.append(Paragraph(
        "· <b>데이터</b>: 서울열린데이터광장·소상공인시장진흥공단·국가데이터처의 공공데이터 9종과, 유동인구 결합의 "
        "정확도를 위해 SGIS(통계지리정보서비스)의 승인 집계구 경계를 추가로 확보해 사용.", S["bodysp"]))
    st.append(Paragraph(
        "· <b>12개 입지 피처</b>: 경쟁 밀도(반경별 편의점 수), 대중교통 접근성(지하철 거리·승하차량, 버스정류장), "
        "생활인구(주간/야간 × 평일/주말), 집객시설(음식점·학원 수).", S["bodysp"]))
    st.append(Paragraph(
        "· <b>출점불가 마스킹</b>: 건물과 상가가 모두 없는 격자(도로·하천·산지·공원)를 걸러, 점수가 높아도 "
        "실제로는 출점이 불가능한 곳을 후보에서 제외.", S["body"]))
    st.append(Spacer(1, 18))

    st.append(h2("모델 성능 — 숫자의 의미"))
    st.append(metric_row())
    st.append(Spacer(1, 18))

    st.append(h2("모델을 3번 고쳐 만든 최종안"))
    st.append(Paragraph(
        "타깃(무엇을 예측할지)과 피처를 <b>하나씩 분리해 실험</b>했습니다. 성능이 떨어진 버전(v2)을 그냥 버리지 않고 "
        "원인을 진단해, '점포당 매출로 타깃을 바꾼 것'이 문제였고 '집객시설 피처 추가'는 도움이 됐음을 밝혀 최적 조합(v3a)을 확정했습니다.",
        S["bodysp"]))
    st.append(compare_table())
    st.append(Spacer(1, 18))

    # 현장 검증 '판정 요약표'를 2페이지 하단으로 (상세 서술은 3페이지로 이어짐)
    st.append(h2("현장 검증: 모델을 직접 걸어서 확인하다"))
    st.append(Paragraph("상위 후보 10곳 중 5곳을 직접 답사해, 모델의 판단과 현장을 대조했습니다.", S["bodysp"]))
    st.append(verdict_table())
    st.append(Spacer(1, 3))
    st.append(Paragraph(
        "* <b>8위 '진입 불가'는 모델 오류가 아닙니다.</b> 모델 점수는 정확했으나(수요 있음) 빈 점포가 없어 실제 진입만 불가한 경우로, "
        "모델이 틀린 <b>위양성(2·9위)과는 구분</b>됩니다.", S["small"]))

    st.append(PageBreak())

    # ===== 페이지 3: 케이스별 답사 상세 + 사진 =====
    st.append(h2("케이스별 답사 상세"))
    for f in narrative_flowables():
        st.append(f)
    st.append(Spacer(1, 12))
    st.append(photo_pair())

    st.append(PageBreak())

    # ===== 페이지 4: 핵심 통찰 + 역할·성장 + 데이터 출처 =====
    st.append(h2("핵심 통찰 — 한계를 현장으로 규명하다"))
    st.append(Paragraph(
        "5곳 중 완전 적중은 1곳이었지만, 이 결과가 오히려 프로젝트의 핵심입니다. 모델은 <b>'상권 매출'로 학습됐기에 "
        "사실상 '편의점이 이미 몰린 곳(상업 밀집도)'을 학습</b>했습니다. 그래서 활발한 상권은 잘 찾아내지만, "
        "비어 있는 자리가 <b>진짜 기회인지 — 아니면 순수 주거단지(9위)나 초등학교 탓에 유동인구가 부풀려진 착시(2위)인지</b>는 "
        "구분하지 못합니다. 이 한계는 데이터만 봐서는 드러나지 않았고, 직접 걸어봤기에 규명할 수 있었습니다. "
        "<b>모델을 신뢰하되 맹신하지 않고, 정량 분석과 현장 검증을 함께 쓰는 것</b>이 이 프로젝트의 결론이자 태도입니다.",
        S["body"]))
    st.append(Spacer(1, 22))

    st.append(h2("나의 역할과 프로젝트의 성장"))
    st.append(Paragraph(
        "파이프라인 <b>코드 작성에는 AI 코딩 도구(Claude Code)를 활용</b>했습니다. 대신 데이터 선정, 피처 설계, "
        "좌표계·마스킹 규칙 같은 방법론적 판단, 모델 버전 비교와 원인 진단, 답사 대상 선정과 현장 검증, 결과 해석은 "
        "모두 직접 수행했습니다.", S["bodysp"]))
    st.append(Paragraph(
        "프로젝트는 매 단계의 판단으로 나아졌습니다. 유동인구와 집계구 경계가 <b>0% 일치</b>하던 문제를 코드 체계 차이가 "
        "아니라 <b>'기준 연도 불일치'로 재진단</b>해 알맞은 경계를 확보하고 100% 일치를 만들었고, 성능이 떨어진 모델 버전의 "
        "원인을 <b>타깃 변경과 피처 추가로 분리 실험</b>해 진짜 원인을 짚었으며, 지도에서 산지에 후보지가 몰린 것을 "
        "<b>눈으로 발견</b>해 마스킹 규칙을 고쳐 오탐을 걸러냈습니다. AI가 준 결과를 그대로 받지 않고 <b>'왜 그런지 되묻고 "
        "검증하는 것'</b>이 제 역할이었습니다.", S["body"]))
    st.append(Spacer(1, 22))

    st.append(h2("확장 방향"))
    st.append(Paragraph(
        "· 산지·비상업지역을 포함한 학습 데이터 보강으로 모델의 외삽 한계(빈자리 오판)를 완화.", S["bodysp"]))
    st.append(Paragraph(
        "· 건물 용도·임대 정보를 결합해 '물리적 출점 가능성'을 더 정교하게 판정.", S["bodysp"]))
    st.append(Paragraph(
        "· 다른 자치구로 스코어링 확장, 임장 결과를 라벨로 되먹여 재학습(active learning).", S["body"]))
    st.append(Spacer(1, 22))

    st.append(h2("데이터 출처 및 라이선스"))
    st.append(Paragraph(
        "집계구 경계 데이터(<b>bnd_oa_11_2016_4Q, 2015_4Q</b>)는 <b>SGIS(통계지리정보서비스)</b>에서 자료 신청·승인을 받아 "
        "취득했으며, 재사용 시 SGIS 출처 표기가 필요합니다. 그 외 데이터는 <b>서울열린데이터광장, 국가데이터처, "
        "소상공인시장진흥공단</b>이 공개한 공공데이터를 사용했습니다.", S["body"]))

    st.append(Spacer(1, 20))
    st.append(HRFlowable(width="100%", thickness=0.6, color=LINE))
    st.append(Spacer(1, 5))
    st.append(Paragraph(
        '전체 코드 · 데이터 명세 · 상세 검증 기록 →  '
        '<a href="https://github.com/KHWGISPort/gis-portfolio/tree/master"><u>https://github.com/KHWGISPort/gis-portfolio</u></a>',
        S["foot"]))

    doc.build(st)
    print(f"저장 완료: {out}")
