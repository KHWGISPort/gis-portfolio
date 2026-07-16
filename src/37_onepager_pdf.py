# -*- coding: utf-8 -*-
"""
[Phase 6 - 요약 PDF] 비개발 직군 검토자를 위한 1페이지 요약 PDF를 만든다.
30초 안에 "정량 분석 x 현장 검증"이라는 프로젝트의 핵심을 읽을 수 있도록,
텍스트는 최소화하고 지도 이미지·핵심 인사이트·판정표 위주로 구성한다.

한글 출력을 위해 reportlab의 내장 CID 폰트(HYSMyeongJo-Medium, 별도 폰트
파일 설치 없이 바로 쓸 수 있는 어도비 표준 한글 폰트)를 사용한다.
"""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# reportlab의 내장 CID 폰트(HYSMyeongJo-Medium 등)는 실제 글꼴을 PDF 안에 담지 않고
# "뷰어가 이 이름의 폰트를 갖고 있길" 기대하는 방식이라, 그 폰트가 없는 PC/뷰어에서는
# 한글이 통째로 안 보이는 문제가 있었다 (실제로 확인됨). 그래서 윈도우에 있는 맑은 고딕
# TTF 파일을 직접 읽어서 PDF 안에 통째로 심어(embed) 넣는 방식으로 바꿨다 -- 이러면
# 어떤 PC에서 열어도 폰트가 없어서 글자가 안 보이는 일이 없다.
FONT_DIR = "C:/Windows/Fonts"
pdfmetrics.registerFont(TTFont("MalgunGothic", f"{FONT_DIR}/malgun.ttf"))
pdfmetrics.registerFont(TTFont("MalgunGothicBold", f"{FONT_DIR}/malgunbd.ttf"))

FONT_BODY = "MalgunGothic"
FONT_HEAD = "MalgunGothicBold"

NAVY = colors.HexColor("#1a2b4a")
RED = colors.HexColor("#e41a1c")
GREEN = colors.HexColor("#4daf4a")
GRAY = colors.HexColor("#555555")
LIGHT_BG = colors.HexColor("#f4f6fa")

styles = {
    "title": ParagraphStyle("title", fontName=FONT_HEAD, fontSize=20, leading=25,
                             textColor=NAVY, alignment=TA_CENTER),
    "subtitle": ParagraphStyle("subtitle", fontName=FONT_BODY, fontSize=11, leading=15,
                                textColor=GRAY, alignment=TA_CENTER),
    "tagline": ParagraphStyle("tagline", fontName=FONT_HEAD, fontSize=15, leading=18,
                               textColor=colors.white, alignment=TA_CENTER),
    "h2": ParagraphStyle("h2", fontName=FONT_HEAD, fontSize=12.5, leading=16,
                          textColor=NAVY, spaceBefore=4, spaceAfter=4),
    "body": ParagraphStyle("body", fontName=FONT_BODY, fontSize=9.5, leading=13.5,
                            textColor=colors.HexColor("#222222")),
    "insight": ParagraphStyle("insight", fontName=FONT_BODY, fontSize=10, leading=14.5,
                               textColor=colors.HexColor("#1a1a1a")),
    "small": ParagraphStyle("small", fontName=FONT_BODY, fontSize=7.5, leading=10,
                             textColor=GRAY),
}

VERDICT_ROWS = [
    ("1위", "상봉역", "✅ 적중", "게이트 밖 무점포, 낮+저녁 이중 유동인구 확인"),
    ("2위", "금강사거리", "❌ 위양성", "초등학교발 생활인구 착시, 현장 유동 전무"),
    ("3위", "타임호프", "⭕ 조건부 적중", "고령층 근린 상권, 무인마트 취급 공백이 차별화 여지"),
    ("8위", "먹자골목", "⚠️ 진입 불가", "수요는 확실하나 공실 없음(위반건축물 5건)"),
    ("9위", "진로아파트", "❌ 위양성", "격자가 순수 아파트 단지 내부라 물리적 설치 불가"),
]

INSIGHTS = [
    "서울 전체 상권 708곳의 매출 데이터를 학습해, 중랑구 100m 격자 1,858개 중 물리적으로 "
    "출점 가능한 곳만 골라 <b>539개 신규 후보지</b>를 순위로 도출했습니다.",
    "Top10 후보 중 5곳을 직접 답사한 결과 <b>완전 적중 1건, 조건부 적중 1건</b>이었고, "
    "나머지는 초등학교발 인구 착시·아파트 단지 절단처럼 <b>데이터에 없는 변수</b>로 설명됐습니다.",
    "모델은 '이미 활발한 상권'은 잘 찾아내지만 '빈자리의 진짜 이유'는 구분하지 못합니다 — "
    "그래서 <b>정량 분석과 현장 검증을 함께</b> 쓰는 것이 이 프로젝트의 결론입니다.",
]


def build_verdict_table():
    header = ["순위", "장소", "판정", "핵심 근거"]
    data = [header] + [list(row) for row in VERDICT_ROWS]
    t = Table(data, colWidths=[13*mm, 26*mm, 24*mm, 97*mm])
    style = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_BODY),
        ("FONTNAME", (0, 0), (-1, 0), FONT_HEAD),
        ("FONTSIZE", (0, 0), (-1, -1), 8.7),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]
    t.setStyle(TableStyle(style))
    return t


def tagline_banner():
    t = Table([[Paragraph("정량 분석 × 현장 검증", styles["tagline"])]], colWidths=[171*mm], rowHeights=[11*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return t


if __name__ == "__main__":
    os.makedirs("outputs", exist_ok=True)
    out_path = "outputs/portfolio_onepager.pdf"

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        topMargin=14*mm, bottomMargin=10*mm, leftMargin=19.5*mm, rightMargin=19.5*mm,
    )

    story = []
    story.append(Paragraph("편의점 최적입지 스코어링 및 검증", styles["title"]))
    story.append(Paragraph("서울시 중랑구 기준 · 데이터로 배우는 입지선정 포트폴리오", styles["subtitle"]))
    story.append(Spacer(1, 6))
    story.append(tagline_banner())
    story.append(Spacer(1, 8))

    # 지도 이미지 (핵심 결과)
    img = Image("outputs/36_readme_hero_map.png")
    img.drawWidth = 78*mm
    img.drawHeight = 78*mm
    img.hAlign = "CENTER"
    story.append(img)
    story.append(Paragraph(
        "빨강=고득점·점포없음(신규후보) · 초록=고득점·점포있음(검증된 자리) · 갈색=출점불가(건물·상가 없음)",
        styles["small"],
    ))
    story.append(Spacer(1, 6))

    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))
    story.append(Paragraph("핵심 인사이트", styles["h2"]))
    for i, text in enumerate(INSIGHTS, start=1):
        story.append(Paragraph(f"{i}. {text}", styles["insight"]))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 4))
    story.append(Paragraph("현장 답사 5곳 판정 요약", styles["h2"]))
    story.append(build_verdict_table())

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "데이터: 서울열린데이터광장·소상공인시장진흥공단·국가데이터처·SGIS(통계지리정보서비스, 승인자료) · "
        "모델: LightGBM (스피어만 순위상관 0.312, Top20% 적중률 46.4%, 순위 스코어링 용도) · "
        "전체 코드·상세 근거: GitHub 저장소 참고",
        styles["small"],
    ))

    doc.build(story)
    print(f"저장 완료: {out_path}")
