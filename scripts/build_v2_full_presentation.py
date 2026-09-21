# -*- coding: utf-8 -*-
"""Build Document AI v2 full presentation PPTX + Markdown manuscript."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "docs" / "presentation"
PPTX_PATH = OUT_DIR / "Document_AI_v2_Full_Presentation.pptx"
MD_PATH = OUT_DIR / "Document_AI_v2_Full_Presentation.md"

# Navy / gray tech palette (no purple gradients)
NAVY = RGBColor(0x1F, 0x4E, 0x79)
NAVY_DARK = RGBColor(0x0F, 0x2A, 0x43)
GRAY = RGBColor(0x5C, 0x65, 0x70)
BLACK = RGBColor(0x1C, 0x1F, 0x24)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT = RGBColor(0xEE, 0xF2, 0xF6)
ACCENT = RGBColor(0x2D, 0x6A, 0x9F)
OK = RGBColor(0x1B, 0x5E, 0x3B)


def _set_run(run, text: str, *, size: int = 20, bold: bool = False, color=BLACK, font: str = "Malgun Gothic"):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font


def _add_title_bar(slide, prs):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.12))
    shape.fill.solid()
    shape.fill.fore_color.rgb = NAVY
    shape.line.fill.background()


def _blank(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    _add_title_bar(slide, prs)
    return slide


def add_title_slide(prs, title: str, subtitle: str, notes: str = ""):
    slide = _blank(prs)
    box = slide.shapes.add_textbox(Inches(0.7), Inches(2.0), Inches(12), Inches(1.5))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    _set_run(p.add_run(), title, size=36, bold=True, color=NAVY_DARK)
    sub = slide.shapes.add_textbox(Inches(0.7), Inches(3.7), Inches(12), Inches(1.2))
    stf = sub.text_frame
    stf.word_wrap = True
    sp = stf.paragraphs[0]
    _set_run(sp.add_run(), subtitle, size=18, color=GRAY)
    if notes:
        slide.notes_slide.notes_text_frame.text = notes
    return slide


def add_section(prs, title: str, notes: str = ""):
    slide = _blank(prs)
    box = slide.shapes.add_textbox(Inches(0.7), Inches(2.8), Inches(12), Inches(1.2))
    p = box.text_frame.paragraphs[0]
    _set_run(p.add_run(), title, size=32, bold=True, color=NAVY)
    if notes:
        slide.notes_slide.notes_text_frame.text = notes
    return slide


def add_bullets(prs, title: str, bullets: list[str], notes: str = "", footer: str | None = None):
    slide = _blank(prs)
    tbox = slide.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(12.2), Inches(0.9))
    _set_run(tbox.text_frame.paragraphs[0].add_run(), title, size=26, bold=True, color=NAVY_DARK)

    body = slide.shapes.add_textbox(Inches(0.7), Inches(1.4), Inches(12), Inches(5.2))
    tf = body.text_frame
    tf.word_wrap = True
    for i, line in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = 0
        p.space_after = Pt(10)
        _set_run(p.add_run(), f"•  {line}", size=20, color=BLACK)
    if footer:
        fbox = slide.shapes.add_textbox(Inches(0.7), Inches(6.8), Inches(12), Inches(0.4))
        _set_run(fbox.text_frame.paragraphs[0].add_run(), footer, size=12, color=GRAY)
    if notes:
        slide.notes_slide.notes_text_frame.text = notes
    return slide


def add_code(prs, title: str, code: str, caption: str, notes: str = ""):
    slide = _blank(prs)
    tbox = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.2), Inches(0.7))
    _set_run(tbox.text_frame.paragraphs[0].add_run(), title, size=24, bold=True, color=NAVY_DARK)

    cbox = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.55), Inches(1.15), Inches(12.3), Inches(5.0))
    cbox.fill.solid()
    cbox.fill.fore_color.rgb = RGBColor(0x0F, 0x17, 0x20)
    cbox.line.fill.background()

    tb = slide.shapes.add_textbox(Inches(0.75), Inches(1.3), Inches(12.0), Inches(4.7))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(code.splitlines()):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(2)
        run = p.add_run()
        run.text = line if line else " "
        run.font.size = Pt(11)
        run.font.name = "Consolas"
        run.font.color.rgb = RGBColor(0xE8, 0xEE, 0xF5)

    cap = slide.shapes.add_textbox(Inches(0.7), Inches(6.35), Inches(12), Inches(0.5))
    _set_run(cap.text_frame.paragraphs[0].add_run(), caption, size=14, color=GRAY)
    if notes:
        slide.notes_slide.notes_text_frame.text = notes
    return slide


def add_table_slide(prs, title: str, headers: list[str], rows: list[list[str]], notes: str = ""):
    slide = _blank(prs)
    tbox = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.2), Inches(0.7))
    _set_run(tbox.text_frame.paragraphs[0].add_run(), title, size=24, bold=True, color=NAVY_DARK)

    cols = len(headers)
    table_shape = slide.shapes.add_table(len(rows) + 1, cols, Inches(0.6), Inches(1.3), Inches(12.2), Inches(0.45 * (len(rows) + 1)))
    table = table_shape.table
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = h
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.size = Pt(14)
                r.font.color.rgb = WHITE
                r.font.name = "Malgun Gothic"
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.text = val
            for p in cell.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(13)
                    r.font.name = "Malgun Gothic"
                    r.font.color.rgb = BLACK
            if i % 2 == 1:
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT
    if notes:
        slide.notes_slide.notes_text_frame.text = notes
    return slide


def add_flow_boxes(prs, title: str, steps: list[str], notes: str = ""):
    slide = _blank(prs)
    tbox = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.2), Inches(0.7))
    _set_run(tbox.text_frame.paragraphs[0].add_run(), title, size=24, bold=True, color=NAVY_DARK)

    n = len(steps)
    total_w = 12.0
    gap = 0.15
    box_w = (total_w - gap * (n - 1)) / n
    y = 2.6
    for i, label in enumerate(steps):
        x = 0.6 + i * (box_w + gap)
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(box_w), Inches(1.4))
        shape.fill.solid()
        shape.fill.fore_color.rgb = NAVY if i % 2 == 0 else ACCENT
        shape.line.fill.background()
        tf = shape.text_frame
        tf.word_wrap = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        run = tf.paragraphs[0].add_run()
        _set_run(run, label, size=12, bold=True, color=WHITE)
        if i < n - 1:
            arr = slide.shapes.add_textbox(Inches(x + box_w - 0.05), Inches(y + 0.5), Inches(0.25), Inches(0.4))
            # arrows between via text in next iteration skip
    hint = slide.shapes.add_textbox(Inches(0.7), Inches(4.5), Inches(12), Inches(1.5))
    _set_run(
        hint.text_frame.paragraphs[0].add_run(),
        "흐름: 왼쪽 → 오른쪽 · 사람 승인 전 원본/복사본 쓰기 없음",
        size=16,
        color=GRAY,
    )
    if notes:
        slide.notes_slide.notes_text_frame.text = notes
    return slide


def build_pptx() -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    add_title_slide(
        prs,
        "Document AI v2",
        "문서 변경을 안전하게 찾는 Pilot\n찾고 → 보여주고 → 사람이 승인 → 복사본만 저장",
        "오프닝: 생성형 LLM이 문서를 쓰는 제품이 아니라, 변경 위치를 찾고 사람이 통제하는 안전 Pilot임을 먼저 말합니다.",
    )
    add_bullets(
        prs,
        "Agenda",
        [
            "문제 정의와 한 줄 해결",
            "전체 구성 · 아키텍처",
            "사용자 6단계 프로세스",
            "사용 시나리오 (EC-SW / 보고서 / 제안서)",
            "구동 방법 · 코드 · 검증 결과",
            "한계와 Next",
        ],
        "12–15분 기준. 데모는 시나리오 장에서 /pilot-v2로 전환 가능.",
    )
    add_bullets(
        prs,
        "문서는 바뀌는데, 수정은 위험하다",
        [
            "요구·설계·제안·보고서는 서로 연결됨",
            "한 줄 변경이 여러 표·섹션에 영향",
            "사람은 위치를 찾기 어렵고",
            "자동 수정은 원본 손상 위험이 큼",
        ],
        "청중에게: ‘자동 작성’보다 ‘안전한 변경 통제’가 오늘의 초점.",
    )
    add_bullets(
        prs,
        "해결: 찾고 → 보여주고 → 승인 → 복사본만",
        [
            "시스템은 영향 위치 후보를 찾는다",
            "사람은 승인 / 거절 / 보류한다",
            "원본은 직접 수정하지 않는다",
            "Writer는 게이트를 통과한 복사본만",
        ],
        "한 문장 강조: 최종 권한은 항상 사람.",
    )

    add_section(prs, "01 · 목표와 범위", "North Star와 현재 Pilot 범위를 구분합니다.")
    add_bullets(
        prs,
        "North Star vs 현재 v2 범위",
        [
            "최종: 완성본 학습 → 빈 양식 자동 작성 (Form Fill)",
            "현재 데모: 변경 요청 → 위치 탐색 → 승인 → 안전 저장",
            "상태: READY_FOR_PILOT_RELEASE",
            "Pilot Run 01 완료 · Run 02 실사용자 준비",
        ],
    )
    add_bullets(
        prs,
        "한 것과 안 한 것",
        [
            "함: Identity, Locator, Domain Pack, Pilot UI",
            "함: Approval 게이트 · Human Review 10점",
            "안 함: 원격 LLM / 원격 Embedding",
            "안 함: 자동 승인 · 원본 직접 수정 · Gold 자동 수정",
        ],
        "오해 방지 슬라이드. ‘AI가 글을 쓴다’가 아님을 분명히.",
    )

    add_section(prs, "02 · 전체 구성", "아키텍처와 모듈 맵.")
    add_flow_boxes(
        prs,
        "시스템 아키텍처",
        ["Pilot UI/CLI", "Workflow", "Domain Packs", "Controlled Writer"],
        "위→아래로 내려가는 계층. Domain Pack = EC-SW / GR / BP.",
    )
    add_bullets(
        prs,
        "모듈 맵",
        [
            "Identity · Pack Routing — 문서 유형 추천",
            "Locator · Ranking — 변경 위치 후보",
            "Physical Locator · Patch Contract — 실제 위치·유효성",
            "Controlled Writer · Diff/Validation — 안전 저장",
            "Pilot UI · Human Review — 사용·평가",
        ],
    )
    add_bullets(
        prs,
        "세션·데이터 레이아웃",
        [
            "sessions/<id>/ — 업로드 복사본·분석·리뷰",
            "data/pilot/demo/ — 발표용 샘플 문서",
            "data/pilot/results/ — Pilot 집계 보고서",
            "벤치마크 코퍼스와 Pilot 데이터는 분리",
        ],
    )

    add_section(prs, "03 · 사용자 6단계", "데모 전에 프로세스 전체를 한 바퀴.")
    add_flow_boxes(
        prs,
        "End-to-End 6 Step",
        ["1 업로드", "2 유형", "3 요청", "4 분석", "5 승인", "6 결과"],
        "이제부터 단계별로 원리와 AI 역할을 설명합니다.",
    )
    add_bullets(
        prs,
        "1. 업로드 — 세션 복사본만 사용",
        [
            "DOCX 검증 · filename sanitization",
            "fingerprint(해시)로 원본 보존 검증",
            "세션 workspace에만 저장",
            "AI 역할: 없음 (안전 입력)",
        ],
    )
    add_bullets(
        prs,
        "2. 문서 유형 — Identity & Domain Pack",
        [
            "파일명·표·식별자·구조 신호 추출",
            "EC-SW / 보고서 / 제안서 추천",
            "assisted: 사용자가 추천 확정",
            "AI 역할: 분류·추천 (최종은 사람)",
        ],
    )
    add_bullets(
        prs,
        "3. 변경 요청 — 자연어 Intent",
        [
            "예: Req.11 갱신, 방법론 출처 보강",
            "세션에 저장되어 분석 쿼리가 됨",
            "이 단계에서는 생성/추론 없음",
            "AI 역할: 없음 (입력만)",
        ],
    )
    add_bullets(
        prs,
        "4. 분석 — 엔진 파이프라인",
        [
            "parse → intent → locate → rank",
            "physical resolve → patch contract",
            "결과: 영향문서 · 후보 · REVIEW",
            "AI 역할: 후보 탐색·순위 (LLM 생성 아님)",
        ],
        "Physical Locator = DOCX 표/행/셀 실제 위치 해석기.",
    )
    add_flow_boxes(
        prs,
        "엔진 내부 파이프라인",
        ["parse", "intent", "locate", "rank", "physical", "contract"],
        "분석 단계의 내부 흐름. 여기가 ‘지능’의 중심.",
    )
    add_bullets(
        prs,
        "5. 검토·승인 — 사람이 최종 권한",
        [
            "항목별 승인 / 거절 / 보류",
            "근거·confidence를 카드로 표시",
            "자동 승인 없음",
            "AI 역할: 제안만 (결정은 사람)",
        ],
    )
    add_bullets(
        prs,
        "6. 결과 — 게이트 · 검증 · 평가",
        [
            "Writer: APPROVE∧flag∧fingerprint∧copy",
            "Diff / Validation / Original Preservation",
            "Human Review 10차원 점수",
            "AI 역할: 거의 없음 (안전·리포트)",
        ],
    )
    add_flow_boxes(
        prs,
        "Writer 안전 게이트",
        ["APPROVE", "routing", "VALID", "locator", "fingerprint", "env", "copy"],
        "하나라도 실패하면 BLOCKED. Dry-run에서는 Writer OFF가 정상.",
    )
    add_table_slide(
        prs,
        "사람 / 시스템 / AI 역할",
        ["단계", "사람", "시스템", "AI에 가까운 부분"],
        [
            ["업로드", "파일 선택", "복사·해시", "—"],
            ["유형", "추천 확정", "Identity·Routing", "문서 분류"],
            ["요청", "자연어 입력", "요청 저장", "—"],
            ["분석", "대기", "Locator·Contract", "후보 탐색·순위"],
            ["승인", "승인/거절/보류", "카드·게이트", "제안만"],
            ["결과", "평가·다운로드", "Writer·검증", "—"],
        ],
        "핵심 메시지: 생성형 LLM이 문장을 쓰는 단계가 아니다.",
    )

    add_section(prs, "04 · 사용 시나리오", "데모 전환 가능 구간.")
    add_bullets(
        prs,
        "시나리오 A · EC-SW Req.11",
        [
            "UI: EC-SW 단일 Req ID 변경",
            "요청: Req.11 추적성 행 검토",
            "기대: Req.11 행 후보",
            "사람: 관련만 승인, 나머지 보류",
        ],
        "데모 전환: /pilot-v2에서 시나리오 선택.",
    )
    add_bullets(
        prs,
        "시나리오 B · 일반보고서 방법론",
        [
            "요청: 방법론에 데이터 출처 보강",
            "기대: 방법론 섹션 후보",
            "사람: 방법론만 승인",
            "실패 신호: 결론·일정만 잡힘",
        ],
    )
    add_bullets(
        prs,
        "시나리오 C · 사업제안서 예산",
        [
            "요청: 예산 표 인건비 항목 수정",
            "기대: 예산/인건비 후보",
            "사람: 불확실하면 보류",
            "금액은 자동 승인하지 않음",
        ],
    )
    add_bullets(
        prs,
        "관찰 케이스 · 의미 기반 요청",
        [
            "요청: ‘인증 정책 강화’ (ID 없음)",
            "Run 01: 검토 항목 0건 · PARTIAL",
            "수정하지 않고 bug candidate로 기록",
            "한계를 숨기지 않는 것이 Pilot의 원칙",
        ],
    )

    add_section(prs, "05 · 구동과 코드", "실행 방법과 핵심 코드.")
    add_bullets(
        prs,
        "실행 방법",
        [
            "로컬: uvicorn … → /pilot-v2",
            "Docker: compose up → :8765",
            "기본: CONTROLLED_WRITER_ENABLED=false",
            "CLI: run-pilot-demo / evaluate-pilot",
        ],
        "외부망 공개 시 인증 없음 → LAN/VPN만 권장.",
    )
    add_code(
        prs,
        "코드 · Pilot 오케스트레이터 흐름",
        """# src/document_ai/pilot_v2/orchestrator.py
# create → upload → resolve_identity → analyze
# → apply_decisions → run_writer_if_allowed
# → save_human_review → get_result

ALLOWED = {"ec_sw", "general_report", "business_proposal"}

# Writer는 텍스트 패치를 적용하지 않음
# copy-only · 원본 경로에 쓰지 않음""",
        "이 코드가 하는 일: Pilot UI 6단계를 기존 workflow 엔진에 연결한다.",
        "파일 경로를 언급하고, ‘얇은 오케스트레이터’임을 강조.",
    )
    add_code(
        prs,
        "코드 · 분석 결과물",
        """# workflow.run_analysis →
record.impacted_documents = ...
record.patch_candidates = ...
record.review_required = ...

# 각 항목은 PENDING 승인 상태로 대기
# → WAITING_APPROVAL""",
        "이 코드가 하는 일: 영향 문서·패치 후보·REVIEW를 만들고 사람 승인을 기다린다.",
    )
    add_code(
        prs,
        "코드 · Identity / Routing",
        """# document_identity.resolve_uploaded_documents(
#   routing_mode="assisted",
#   user_confirmed=False/True,
# )
# → recommended Domain Pack
# → needs_user_confirmation""",
        "이 코드가 하는 일: 문서 유형을 추천하고, assisted면 사람 확정을 요구한다.",
    )
    add_code(
        prs,
        "코드 · Writer 게이트",
        """# run_writer_if_allowed(...)
# 필요 조건(개념):
#   explicit APPROVE
#   routing confirmed
#   Patch Contract VALID
#   physical locator RESOLVED
#   fingerprint match
#   CONTROLLED_WRITER_ENABLED
#   copy path ≠ original
# 아니면 status = BLOCKED""",
        "이 코드가 하는 일: 조건이 하나라도 빠지면 쓰기를 막는다.",
    )

    add_section(prs, "06 · 검증 결과", "Benchmark와 Pilot Run 01.")
    add_table_slide(
        prs,
        "Benchmark (고정 참조)",
        ["지표", "값"],
        [
            ["Holdout Document F1", "0.956"],
            ["Holdout E2E", "0.957"],
            ["False Patch / Unsafe", "0 / 0"],
            ["Original Preservation", "1.000"],
            ["BP Required Top-1", "0.929"],
            ["GR Node Top-1", "1.000"],
            ["EC-SW Stable Identity", "1.000"],
        ],
        "Pilot 단계에서 벤치마크를 튜닝하지 않음.",
    )
    add_table_slide(
        prs,
        "Pilot Run 01 (Writer OFF)",
        ["지표", "값"],
        [
            ["Sessions", "9 (EC3 / GR3 / BP3)"],
            ["Completion Rate", "1.000"],
            ["Document / Node Agree", "0.889 / 0.889"],
            ["Mean Trust / Usability", "3.778 / 4.000"],
            ["Original changed", "0"],
            ["Unauthorized writer", "0"],
            ["Major bug", "의미기반 후보 0건 1건"],
        ],
    )
    add_bullets(
        prs,
        "한계와 Next",
        [
            "Next: Pilot Run 02 실사용자 UI 평가",
            "Next: Writer ON 소규모 안전 Pilot",
            "이후: 승인 게이트 유지 텍스트 apply",
            "장기: MDVP · LLM free_text (현재 범위 밖)",
        ],
    )

    add_bullets(
        prs,
        "Takeaways",
        [
            "Document AI v2 Pilot = 안전한 변경 위치 탐색기",
            "사람은 승인하고, 원본은 건드리지 않는다",
            "검증된 엔진 + 통제된 UI로 실사용 준비",
        ],
        "닫는 문장: READY_FOR_PILOT_RELEASE.",
    )
    add_title_slide(prs, "Q & A", "Document AI v2 · Pilot Presentation", "질문 유도: 시나리오, 안전 게이트, LLM 미사용 이유.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prs.save(str(PPTX_PATH))


def build_md() -> None:
    md = """# Document AI v2 — Full Presentation Manuscript

발표 시간: 12–15분 · 언어: 한국어  
산출물: `Document_AI_v2_Full_Presentation.pptx`

---

## 1. 표지
**Document AI v2**  
문서 변경을 안전하게 찾는 Pilot  
찾고 → 보여주고 → 사람이 승인 → 복사본만 저장

## 2. Agenda
- 문제 정의와 한 줄 해결
- 전체 구성 · 아키텍처
- 사용자 6단계
- 시나리오 (EC-SW / GR / BP)
- 구동 · 코드 · 검증 · Next

## 3. 문제
문서는 연결돼 있고, 자동 수정은 원본 손상 위험이 큼.

## 4. 해결
찾고 → 보여주고 → 승인 → 복사본만.

## 5. North Star vs 현재
- 최종: Form Fill Agent
- 현재: Change Pilot (`/pilot-v2`)
- READY_FOR_PILOT_RELEASE

## 6. 한 것 / 안 한 것
- LLM·자동승인·원본수정·Gold 자동수정 = 안 함

## 7–9. 구성
Pilot UI/CLI → Workflow → Domain Packs → Controlled Writer  
모듈: Identity, Locator, Contract, Writer, Human Review  
데이터: sessions / demo / results (benchmark와 분리)

## 10–16. 6단계
1. 업로드 — 복사·fingerprint  
2. 유형 — Identity + Pack, 사람 확정  
3. 요청 — 자연어 intent  
4. 분석 — locate/rank/contract (**AI 중심, LLM 생성 아님**)  
5. 승인 — APPROVE/REJECT/HOLD  
6. 결과 — Writer 게이트 + Human Review 10점

## 17–20. 시나리오
- A EC-SW Req.11  
- B GR 방법론  
- C BP 예산  
- 관찰: 의미 기반 후보 0건 (bug candidate)

## 21–26. 구동·코드
- uvicorn / Docker `:8765` / Writer OFF  
- orchestrator / run_analysis / identity / writer gate

## 27–29. 결과
- Benchmark F1 0.956 · E2E 0.957 · False/Unsafe 0  
- Pilot 01: 9세션, Trust 3.778, Usability 4.0, Safety PASS  
- Next: Run 02 실사용자 → Writer ON 소규모

## 30–31. Takeaways / Q&A
안전 변경 위치 탐색기 · 사람 승인 · 원본 무변경
"""
    MD_PATH.write_text(md, encoding="utf-8")


def main() -> None:
    build_pptx()
    build_md()
    print(f"PPTX: {PPTX_PATH}")
    print(f"MD:   {MD_PATH}")
    print(f"slides: built")


if __name__ == "__main__":
    main()
