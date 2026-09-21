"""Factory for Small-A T2 regulatory_bench cases (MDSR+MDDR frequency-propagation)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .materialize import materialize_case

ROOT = Path("data/eval/regulatory_bench")
TEMPLATE = ROOT / "case_000"


PROFILES: list[dict[str, Any]] = [
    {
        "case_id": "case_003",
        "profile_id": "P4_diabetes_dtx",
        "product_name": "GlucoGuide DTx (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "혈당 일기 입력 주기를 매일에서 주 4회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 혈당일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 08:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 혈당일기를 주 4회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=4_per_week",
            "DI_012_NOTIFY": "주 4회 08:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*4\s*회.*알림" },
    },
    {
        "case_id": "case_004",
        "profile_id": "P5_depression_dtx",
        "product_name": "MoodTrack CBT (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "기분 체크인 입력 주기를 매일에서 주 2회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 기분 체크인을 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 19:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 기분 체크인을 주 2회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=2_per_week",
            "DI_012_NOTIFY": "주 2회 19:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*2\s*회.*알림" },
    },
    {
        "case_id": "case_005",
        "profile_id": "P6_pain_dtx",
        "product_name": "ReliefLog Pain Coach (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "통증 일기 입력 주기를 매일에서 주 3회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 통증일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 12:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 통증일기를 주 3회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=3_per_week",
            "DI_012_NOTIFY": "주 3회 12:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*3\s*회.*알림" },
    },
    {
        "case_id": "case_006",
        "profile_id": "P7_asthma_dtx",
        "product_name": "BreatheEase Asthma Log (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "천식 증상 일기 입력 주기를 매일에서 주 5회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 천식 증상 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 07:30 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 천식 증상 일기를 주 5회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=5_per_week",
            "DI_012_NOTIFY": "주 5회 07:30 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*5\s*회.*알림" },
    },
    {
        "case_id": "case_007",
        "profile_id": "P8_migraine_dtx",
        "product_name": "AuraTrack Migraine (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "편두통 일기 입력 주기를 매일에서 주 2회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 편두통 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 21:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 편두통 일기를 주 2회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=2_per_week",
            "DI_012_NOTIFY": "주 2회 21:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*2\s*회.*알림" },
    },
    {
        "case_id": "case_008",
        "profile_id": "P9_copd_dtx",
        "product_name": "LungDiary COPD (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "호흡 일기 입력 주기를 매일에서 주 3회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 호흡 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 09:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 호흡 일기를 주 3회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=3_per_week",
            "DI_012_NOTIFY": "주 3회 09:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*3\s*회.*알림" },
    },
    {
        "case_id": "case_009",
        "profile_id": "P10_obesity_dtx",
        "product_name": "BalanceBite Coach (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "식사 일기 입력 주기를 매일에서 주 4회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 식사 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 18:30 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 식사 일기를 주 4회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=4_per_week",
            "DI_012_NOTIFY": "주 4회 18:30 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*4\s*회.*알림" },
    },
    {
        "case_id": "case_010",
        "profile_id": "P11_anxiety_dtx",
        "product_name": "CalmCheck Anxiety (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "불안 체크인 입력 주기를 매일에서 주 5회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 불안 체크인를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 20:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 불안 체크인를 주 5회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=5_per_week",
            "DI_012_NOTIFY": "주 5회 20:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*5\s*회.*알림" },
    },
    {
        "case_id": "case_011",
        "profile_id": "P12_ptsd_dtx",
        "product_name": "SafeSpace PTSD Journal (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "증상 일기 입력 주기를 매일에서 주 2회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 증상 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 22:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 증상 일기를 주 2회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=2_per_week",
            "DI_012_NOTIFY": "주 2회 22:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*2\s*회.*알림" },
    },
    {
        "case_id": "case_012",
        "profile_id": "P13_rehab_msk",
        "product_name": "JointFlow Rehab Log (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "재활 운동 일기 입력 주기를 매일에서 주 3회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 재활 운동 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 10:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 재활 운동 일기를 주 3회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=3_per_week",
            "DI_012_NOTIFY": "주 3회 10:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*3\s*회.*알림" },
    },
    {
        "case_id": "case_013",
        "profile_id": "P14_fertility_dtx",
        "product_name": "CycleNote Fertility (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "주기 증상 일기 입력 주기를 매일에서 주 4회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 주기 증상 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 08:30 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 주기 증상 일기를 주 4회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=4_per_week",
            "DI_012_NOTIFY": "주 4회 08:30 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*4\s*회.*알림" },
    },
    {
        "case_id": "case_014",
        "profile_id": "P15_cardiac_rehab",
        "product_name": "PulsePath Cardiac Rehab (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "심박/활동 일기 입력 주기를 매일에서 주 5회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 심박/활동 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 07:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 심박/활동 일기를 주 5회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=5_per_week",
            "DI_012_NOTIFY": "주 5회 07:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*5\s*회.*알림" },
    },
    {
        "case_id": "case_015",
        "profile_id": "P16_ibs_dtx",
        "product_name": "GutGuide IBS Log (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "장 증상 일기 입력 주기를 매일에서 주 2회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 장 증상 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 13:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 장 증상 일기를 주 2회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=2_per_week",
            "DI_012_NOTIFY": "주 2회 13:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*2\s*회.*알림" },
    },
    {
        "case_id": "case_016",
        "profile_id": "P17_sleep_apnea",
        "product_name": "NightAir CPAP Coach (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "수면 일기 입력 주기를 매일에서 주 3회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 수면 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 23:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 수면 일기를 주 3회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=3_per_week",
            "DI_012_NOTIFY": "주 3회 23:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*3\s*회.*알림" },
    },
    {
        "case_id": "case_017",
        "profile_id": "P18_oncology_symptom",
        "product_name": "CareTrack Onco Symptom (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "항암 부작용 일기 입력 주기를 매일에서 주 4회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 항암 부작용 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 16:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 항암 부작용 일기를 주 4회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=4_per_week",
            "DI_012_NOTIFY": "주 4회 16:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*4\s*회.*알림" },
    },
    {
        "case_id": "case_018",
        "profile_id": "P19_pediatric_asthma",
        "product_name": "KidBreathe Log (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "소아 천식 일기 입력 주기를 매일에서 주 5회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 소아 천식 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 08:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 소아 천식 일기를 주 5회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=5_per_week",
            "DI_012_NOTIFY": "주 5회 08:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*5\s*회.*알림" },
    },
    {
        "case_id": "case_019",
        "profile_id": "P20_geriatric_fall",
        "product_name": "SteadyStep Fall Risk (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "낙상 위험 체크인 입력 주기를 매일에서 주 2회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 낙상 위험 체크인를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 17:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 낙상 위험 체크인를 주 2회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=2_per_week",
            "DI_012_NOTIFY": "주 2회 17:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*2\s*회.*알림" },
    },
    {
        "case_id": "case_020",
        "profile_id": "P21_dialysis_symptom",
        "product_name": "RenalDay Symptom Log (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "투석 증상 일기 입력 주기를 매일에서 주 3회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 투석 증상 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 06:30 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 투석 증상 일기를 주 3회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=3_per_week",
            "DI_012_NOTIFY": "주 3회 06:30 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*3\s*회.*알림" },
    },
    {
        "case_id": "case_021",
        "profile_id": "P22_maternity_bp",
        "product_name": "MamaPress BP Log (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "혈압 일기 입력 주기를 매일에서 주 4회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 혈압 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 09:30 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 혈압 일기를 주 4회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=4_per_week",
            "DI_012_NOTIFY": "주 4회 09:30 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*4\s*회.*알림" },
    },
    {
        "case_id": "case_022",
        "profile_id": "P23_dermatology_itch",
        "product_name": "CalmSkin Itch Diary (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "가려움 일기 입력 주기를 매일에서 주 5회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 가려움 일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 21:30 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 가려움 일기를 주 5회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=5_per_week",
            "DI_012_NOTIFY": "주 5회 21:30 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*5\s*회.*알림" },
    },
    {
        "case_id": "case_023",
        "profile_id": "P24_substance_craving",
        "product_name": "UrgeGuard Craving Log (synthetic)",
        "domain": "digital_therapeutic_sw",
        "change_request": "갈망 체크인 입력 주기를 매일에서 주 2회로 바꿔 주세요. 알림 주기도 같은 주기로 맞춰 주세요.",
        "before": {
            "REQ_007_DESC": "사용자는 갈망 체크인를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 15:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 갈망 체크인를 주 2회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=2_per_week",
            "DI_012_NOTIFY": "주 2회 15:00 입력 알림",
        },
        "accept_regex": { "DI_012_NOTIFY": r"주\s*2\s*회.*알림" },
    },
]


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload if payload.endswith("\n") else payload + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")



FAILURE_MODE_PROFILES: list[dict[str, Any]] = [
    {
        "case_id": "case_024",
        "profile_id": "F1_conflict_needs_review",
        "product_name": "OpenCBT-I Sleep Coach (synthetic)",
        "domain": "digital_therapeutic_sw",
        "failure_mode": "conflict_needs_review",
        "change_request": (
            "수면일기 입력 주기를 매일에서 주 3회로 바꿔 주세요. "
            "동시에 매일 입력으로 유지해 주세요. 알림도 맞춰 주세요."
        ),
        "before": {
            "REQ_007_DESC": "사용자는 수면일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 21:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 수면일기를 주 3회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=3_per_week",
            "DI_012_NOTIFY": "주 3회 21:00 입력 알림",
        },
        "accept_regex": {"DI_012_NOTIFY": r"주\s*3\s*회.*알림"},
        "expected_consistency": "NEEDS_REVIEW",
        "notes": "Conflicting frequency instructions; B4 should route to NEEDS_REVIEW (Safety story).",
    },
    {
        "case_id": "case_025",
        "profile_id": "F2_must_not_touch_bait",
        "product_name": "OpenCBT-I Sleep Coach (synthetic)",
        "domain": "digital_therapeutic_sw",
        "failure_mode": "must_not_touch_bait",
        "change_request": (
            "로그인(Req. 1) 문구는 건드리지 말고, "
            "수면일기 입력 주기만 매일에서 주 3회로 바꿔 주세요. 알림도 같은 주기로 맞춰 주세요."
        ),
        "before": {
            "REQ_007_DESC": "사용자는 수면일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 21:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 수면일기를 주 3회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=3_per_week",
            "DI_012_NOTIFY": "주 3회 21:00 입력 알림",
        },
        "accept_regex": {"DI_012_NOTIFY": r"주\s*3\s*회.*알림"},
        "notes": "Bait mentions Req.1 login; touching REQ_001_DESC is false_patch.",
    },
    {
        "case_id": "case_026",
        "profile_id": "F3_multi_req_seed",
        "product_name": "OpenCBT-I Sleep Coach (synthetic)",
        "domain": "digital_therapeutic_sw",
        "failure_mode": "multi_req_seed",
        "change_request": (
            "Req. 7 수면일기 입력 주기를 매일에서 주 3회로 바꾸고, "
            "Req. 6 개인정보 외부전송 금지 문구도 함께 검토·동기화해 주세요. 알림 주기도 맞춰 주세요."
        ),
        "before": {
            "REQ_007_DESC": "사용자는 수면일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 21:00 입력 알림",
        },
        "after": {
            "REQ_007_DESC": "사용자는 수면일기를 주 3회 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=3_per_week",
            "DI_012_NOTIFY": "주 3회 21:00 입력 알림",
        },
        "accept_regex": {"DI_012_NOTIFY": r"주\s*3\s*회.*알림"},
        "extra_impact_nodes": [
            {
                "node_id": "REQ_006_DESC",
                "document_id": "MDSR_v1",
                "kind": "requirement_cell",
                "req_id": "Req. 6",
                "link_type": "explicit_seed",
                "rationale": "CR jointly seeds Req. 6 for review alongside Req. 7 frequency change.",
            }
        ],
        "notes": "Multi-Req seed; gold impact includes Req.6+Req.7. Live may under-recall Req.6 (diversity).",
    },
]



def create_case_from_profile(profile: dict[str, Any], *, force: bool = True) -> Path:
    """Clone case_000 gold/meta skeleton and apply profile-specific CR/patch text."""
    case_id = profile["case_id"]
    dest = ROOT / case_id
    if dest.exists() and force:
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    meta = json.loads((TEMPLATE / "meta.json").read_text(encoding="utf-8"))
    meta["case_id"] = case_id
    meta["profile"] = {
        "profile_id": profile["profile_id"],
        "product_name": profile["product_name"],
        "domain": profile.get("domain") or "digital_therapeutic_sw",
        "notes": "Synthetic profile for benchmark only. Not a real cleared product.",
    }
    tags = list(meta.get("tags") or [])
    for t in ("T2", "mdsr_mddr", "synthetic", "factory"):
        if t not in tags:
            tags.append(t)
    meta["tags"] = tags
    if profile.get("failure_mode"):
        fm = str(profile["failure_mode"])
        if fm not in meta["tags"]:
            meta["tags"].append(fm)
        if "failure_mode" not in meta["tags"]:
            meta["tags"].append("failure_mode")
        meta["failure_mode"] = {
            "id": fm,
            "expected_consistency": profile.get("expected_consistency"),
            "notes": profile.get("notes"),
        }
    if "annotation" in meta:
        meta["annotation"]["status"] = "draft_factory"
    _write(dest / "meta.json", meta)

    for name in ("impact_nodes.json", "must_not_touch.json"):
        data = json.loads((TEMPLATE / "gold" / name).read_text(encoding="utf-8"))
        data["case_id"] = case_id
        _write(dest / "gold" / name, data)

    # Failure-mode gold overrides (multi-req seed, etc.)
    if profile.get("extra_impact_nodes"):
        impact_path = dest / "gold" / "impact_nodes.json"
        impact = json.loads(impact_path.read_text(encoding="utf-8"))
        existing = {str(n.get("node_id")) for n in (impact.get("impact_nodes") or [])}
        for node in profile["extra_impact_nodes"]:
            nid = str(node.get("node_id"))
            if nid and nid not in existing:
                impact.setdefault("impact_nodes", []).append(node)
                existing.add(nid)
        _write(impact_path, impact)
        # Remove newly impacted nodes from must_not_touch
        mnt_path = dest / "gold" / "must_not_touch.json"
        mnt = json.loads(mnt_path.read_text(encoding="utf-8"))
        mnt["untouched_nodes"] = [
            n for n in (mnt.get("untouched_nodes") or [])
            if str(n.get("node_id") if isinstance(n, dict) else n) not in existing
        ]
        _write(mnt_path, mnt)

    patch = json.loads((TEMPLATE / "gold" / "expected_patch.json").read_text(encoding="utf-8"))
    patch["case_id"] = case_id
    before = profile.get("before") or {}
    after = profile.get("after") or {}
    accept = profile.get("accept_regex") or {}
    for p in patch.get("patches") or []:
        nid = p["node_id"]
        if nid in before:
            p["before"] = before[nid]
        if nid in after:
            p["after"] = after[nid]
        if nid in accept:
            p["accept_regex"] = accept[nid]
    _write(dest / "gold" / "expected_patch.json", patch)

    cr_rel = (meta.get("change_request") or {}).get("path") or "input/change_request.txt"
    _write(dest / cr_rel, profile["change_request"].strip() + "\n")
    _write(
        dest / "fp" / "originals.sha256",
        "# sha256 fingerprints of immutable inputs (fill after DOCX materialization)\n"
        "# FORMAT: <sha256>  <relative_path>\n",
    )

    materialize_case(dest, force=True)
    return dest


def list_target_case_ids() -> list[str]:
    """Hand cases + factory → ~24 T2 ids."""
    hand = ["case_000", "case_001", "case_002"]
    return hand + [p["case_id"] for p in PROFILES] + [p["case_id"] for p in FAILURE_MODE_PROFILES]


def bootstrap_factory_cases(*, force: bool = True) -> list[str]:
    """Create all factory profiles; return case_ids."""
    ids: list[str] = []
    for profile in PROFILES:
        path = create_case_from_profile(profile, force=force)
        ids.append(path.name)
    return ids


def bootstrap_failure_mode_cases(*, force: bool = True) -> list[str]:
    """Create T2 diversity failure-mode cases (conflict / must-not-touch / multi-Req)."""
    ids: list[str] = []
    for profile in FAILURE_MODE_PROFILES:
        path = create_case_from_profile(profile, force=force)
        ids.append(path.name)
    return ids


if __name__ == "__main__":
    print(bootstrap_factory_cases(force=True))
    print(bootstrap_failure_mode_cases(force=True))
