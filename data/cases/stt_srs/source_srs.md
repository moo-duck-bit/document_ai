# 소프트웨어 요구사항 명세서 (SRS) — STT 서비스

## 1. 서론 (Introduction)

### 1.1 목적 (Purpose)

본 문서는 음성 → 텍스트 변환 서비스 개발을 위한 요구사항을 정의한다.

### 1.2 범위 (Scope)

- 사용자: 일반 기업 직원, 회의 참여자
- 기능: 오디오 파일 업로드, 자동 텍스트 변환, 결과 다운로드
- 목표: 회의록 작성 효율성 향상 및 다국어 지원

### 1.3 참조 문서 (References)

- IEEE 830-1998
- ISO/IEC/IEEE 29148:2018

## 2. 전체 설명 (Overall Description)

### 2.1 제품 관점

Client → API Gateway → STT Engine → DB → File Storage

### 2.4 제약 조건

- 운영 환경: AWS (EC2, S3, RDS)
- 파일 크기: 최대 100MB
- 법규: 개인정보보호법 준수

## 3. 기능 요구사항 (Functional Requirements)

FR-01	사용자는 mp3, wav 파일을 업로드할 수 있어야 한다.	Must	최대 100MB
FR-02	시스템은 업로드된 오디오 파일을 STT 엔진을 통해 변환해야 한다.	Must	한국어/영어 지원
FR-03	변환된 텍스트는 사용자가 다운로드 가능해야 한다.	Must	txt, docx
FR-04	실패 시 사용자에게 에러 메시지를 반환해야 한다.	Must	HTTP 상태 코드
FR-05	관리자는 웹 대시보드를 통해 시스템 로그를 조회할 수 있어야 한다.	Should	보안 인증 필요

## 4. 비기능 요구사항 (Non-functional Requirements)

NFR-01	평균 응답 속도 2초 이내	1분 길이 파일 기준
NFR-02	동시 접속 처리 100명 이상	Auto Scaling
NFR-03	데이터 전송 보안 HTTPS	TLS 1.2 이상
NFR-04	데이터 저장 보안 AES-256	사용자 데이터
NFR-05	가용성 99.9% SLA	클라우드 환경

## 7. 요구사항 추적성 매트릭스 (RTM)

FR-01	TC-01	mp3 업로드 성공 테스트
FR-02	TC-02	한국어/영어 변환 정확도 90% 이상 검증
NFR-01	TC-05	1분 파일 변환 2초 이내 응답 확인
NFR-03	TC-07	HTTPS 통신 암호화 적용 여부 확인
