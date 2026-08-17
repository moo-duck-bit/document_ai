---
name: document-ocr
description: 스캔 PDF·이미지에서 OCR로 텍스트를 추출합니다. Tesseract, EasyOCR, PaddleOCR, Vision API 선택 가이드.
---

# Document OCR

스캔 문서·이미지에서 텍스트를 인식합니다.

## 엔진 선택

| 엔진 | 장점 | 단점 |
|------|------|------|
| **Tesseract** | 무료, 로컬, 한국어(`kor`) | 전처리 필요, 표/레이아웃 약함 |
| **EasyOCR** | 설치 간단, 다국어 | GPU 권장, 속도 |
| **PaddleOCR** | 한국어·표 성능 우수 | 모델 크기 |
| **Google/Azure Vision** | 높은 정확도 | API 비용, 네트워크 |

**권장**: 로컬·한국어 → PaddleOCR 또는 Tesseract+kor.traineddata  
**권장**: 빠른 PoC → EasyOCR  
**권장**: 프로덕션 고품질 → Vision API + 로컬 fallback

## PDF 스캔 처리 흐름

```
PDF → 페이지별 이미지(300 DPI) → 전처리 → OCR → 텍스트 병합
```

### PDF → 이미지

```python
import fitz

def pdf_pages_to_images(pdf_path: str, dpi: int = 300) -> list[bytes]:
    doc = fitz.open(pdf_path)
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        images.append(pix.tobytes("png"))
    return images
```

### 전처리 (품질 향상)

- 그레이스케일, 이진화(Otsu), 기울기 보정(deskew)
- OpenCV: `cv2.threshold`, `cv2.fastNlMeansDenoising`

### Tesseract 예시

```python
import pytesseract
from PIL import Image

text = pytesseract.image_to_string(
    Image.open(path),
    lang="kor+eng",
    config="--psm 6"  # 단일 블록; 레이아웃에 따라 3, 4, 11 시도
)
```

## 출력

OCR 결과에 **신뢰도**와 **bbox**(가능 시) 포함:

```python
@dataclass
class OcrBlock:
    text: str
    confidence: float
    page_num: int
    bbox: tuple[float, float, float, float] | None
```

저장: `data/ocr/{doc_id}.jsonl`

## 품질 팁

- DPI 300 이상 (작은 글씨 400)
- `kor+eng` 혼합 문서에 유리
- 표는 OCR보다 **레이아웃 분석 + 셀 OCR** 또는 pdfplumber 재시도
- OCR 후 **맞춤법·깨진 글자** 샘pling → `document-eval`

## 검증

- [ ] 알려진 정답 1페이지 CER(Character Error Rate) 측정
- [ ] 한글·숫자·특수문자 혼합 페이지 테스트
- [ ] 처리 시간·페이지당 비용 기록

## 다음 단계

OCR 완료 → `document-chunk` → `document-rag`
