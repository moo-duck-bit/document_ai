from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA = PROJECT_ROOT / "data"
TEMPLATES_EC_SW = DATA / "templates" / "ec_sw"
EXAMPLES_EC_SW = DATA / "examples" / "ec_sw"
SCHEMAS_EC_SW = DATA / "schemas" / "ec_sw"
CASES = DATA / "cases"

TEMPLATE_PATHS = {
    "spec_requirements": TEMPLATES_EC_SW / "template_mdsr.docx",
    "spec_design": TEMPLATES_EC_SW / "template_mddr.docx",
}

FILLED_PATHS = {
    "spec_requirements": EXAMPLES_EC_SW / "spec_mdsr_EC-SW-MDSR(XA)_소프트웨어_요구사항명세서.docx",
    "spec_design": EXAMPLES_EC_SW / "spec_mddr_EC-SW-MDDR(XA) 소프트웨어 설계 명세서.docx",
    "report_security_verification": EXAMPLES_EC_SW
    / "report_xxcs_EC-SW-XXCS(XA) 소프트웨어 보안 검증 보고서.docx",
}
