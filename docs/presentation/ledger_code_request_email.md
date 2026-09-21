# LEDGER code / artifact request — email draft

**Paper:** Hang Wang et al., *LEDGER: Scaling Agentic Document Editing with Dependency-aware Graph Retrieval*, Findings of ACL 2026  
**Anthology:** https://aclanthology.org/2026.findings-acl.515/  
**arXiv:** https://arxiv.org/abs/2606.28379  

**To (suggested):** corresponding / first authors listed on the paper (Hang Wang, and co-authors Utkarsh Garg, Reza Davari, Huitian Jiao, Hao Cheng, Baolin Peng, Si-Qing Chen, Tao Ge — Microsoft)  
**Subject options:** pick one

1. Request for LEDGER code and benchmark artifacts (Findings of ACL 2026)
2. Reproducibility inquiry: LEDGER dependency-graph retrieval for document editing

---

## English version (recommended for authors)

Dear LEDGER authors,

I am a graduate student / researcher working on **agentic editing of regulatory document sets** (requirements and design specifications for digital medical-device software). We read your Findings of ACL 2026 paper *LEDGER: Scaling Agentic Document Editing with Dependency-aware Graph Retrieval* with great interest.

LEDGER is the closest prior work to ours: natural-language edit instructions over long structured documents, dependency-aware retrieval (target → dependent context → edit → verification), and a large consistency-oriented benchmark with rule-based checkers. Your formalization of consistency-preserving retrieval is exactly the problem setting we build on.

Our follow-up setting differs in three ways that we would like to compare against LEDGER as a baseline:

1. **Real regulatory form structure** (public MFDS-style templates) rather than only programmatically generated single documents  
2. **Cross-document change propagation** (e.g., requirements → design / traceability), not only intra-document edits  
3. A **checkable write-safety contract** (no unapproved writes; originals preserved via fingerprints; gated copy-only updates), in addition to post-edit consistency checks

To make that comparison rigorous and fair, would you be willing to share any of the following under a research-use license (or point us to a public release if one already exists)?

- Source code for graph construction, dependency-aware retrieval, editing loop, and consistency validators  
- Benchmark generation scripts and/or the 1.9k evaluation suite (or a documented subset)  
- Documentation for reproducing the main consistency / token-efficiency tables  
- Preferred citation and any license constraints we should respect

We are happy to:
- cite LEDGER prominently as the nearest baseline,
- share our evaluation protocol so the comparison stays faithful to your metrics where applicable, and
- acknowledge any artifact release in our paper.

Thank you very much for the inspiring work, and for considering this request.

Best regards,  
[Full name]  
[Affiliation]  
[Email]  
[GitHub / project page if any]  
[Advisor name, optional]

---

## 한국어 메모 (팀 내부용 — 메일 본문은 영문 권장)

- 목적: 재현·베이스라인 비교 (우리 기여 = 규제 양식 · 문서 간 전파 · μ=0 안전 계약)  
- 톤: 감사 + 구체적 artifact 목록 + 라이선스/인용 약속  
- 과장 금지: “단일 문서 한계를 저자가 Limitations에 자백” 같은 표현은 메일에 넣지 말 것  
- 코드가 비공개여도 Appendix 프로토콜로 재구현 fallback이 있음을 팀에선 알고 있기

---

## Short follow-up (1 week later, if no reply)

Dear authors,

I am writing a brief follow-up on my earlier request regarding LEDGER code/benchmark artifacts for a research baseline comparison on regulatory document-set editing. Please let us know if a public release exists or if research-use sharing is possible. Thank you again for your time.

Best regards,  
[Name]
