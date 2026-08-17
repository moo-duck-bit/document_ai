---
name: document-render
description: 필드값과 스키마를 바탕으로 DOCX/HWP/PDF 출력 문서를 생성합니다.
---

# Document Render (문서 출력)

`form-fill` 결과를 **편집 가능한 파일**로 렌더링.

## MVP: DOCX (python-docx)

### Bookmark / Content Control

```python
from docx import Document

def fill_docx(template_path: str, field_values: dict, schema: dict, out_path: str):
    doc = Document(template_path)
    for field in schema["fields"]:
        value = field_values.get(field["field_id"], "")
        loc = field["location"]
        if loc["type"] == "bookmark":
            _replace_bookmark(doc, loc["name"], value)
        elif loc["type"] == "table":
            _set_table_cell(doc, loc, value)
        elif loc["type"] == "paragraph":
            _replace_after_heading(doc, loc, value)
    doc.save(out_path)
```

### Placeholder 치환

양식에 `{{party_a_name}}` 형태면 Jinja2:

```python
from docxtpl import DocxTemplate
tpl = DocxTemplate("template.docx")
tpl.render(field_values)
tpl.save(out_path)
```

**권장**: 새 프로젝트는 처음부터 `{{field_id}}` placeholder 양식 사용 → 학습·렌더 단순화.

## PDF 출력

- DOCX → LibreOffice headless / docx2pdf
- 또는 reportlab 직접 (레이아웃 고정 양식)

## HWP

- 한글 SDK / pyhwp (제한적) / HWP → DOCX 변환 후 처리
- Phase 2+: HWP 전용 또는 OCR+좌표 기반

## 출력 검증

- [ ] 필수 필드 빈칸 없음
- [ ] 파일 열림 (corrupt check)
- [ ] 페이지 수 ±1 vs 유사 완성본
- [ ] `document-eval` visual/field diff

## API

```python
POST /generate
→ returns { "path": "...", "needs_review": [...] }
```

## 디렉터리

```
data/cases/{case_id}/output.docx
data/cases/{case_id}/output.pdf  # optional
```
