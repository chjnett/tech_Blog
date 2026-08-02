# 논문 소싱 & 분석 파이프라인 스펙

`docs/HANDOFF.md`의 논문 추천 cron(섹션 3.2)을 대체/확장하는 상세 스펙. `papers` 테이블
스키마와 워커 로직은 이 문서 기준으로 구현한다. Phase 1(기반) 이후의 별도 구현 단계이며,
아직 브레인스토밍/플랜 작성 전 — 이 문서는 그 입력이 되는 스펙이다.

## 1. 참고 — Papers with Code는 종료됨

Papers with Code는 2025년 7월에 Meta가 서비스를 종료했다 (데이터는 GitHub
`paperswithcode/paperswithcode-data`에 아카이브로만 남아있고 갱신되지 않음). 그래서 지금은
아래 3개 API 조합이 사실상 표준이다.

## 2. 사용할 API

| API | 용도 | 인증 | 비고 |
|---|---|---|---|
| **arXiv API** (`export.arxiv.org/api`) | cs.CL/cs.AI/cs.LG/cs.AR 최신 프리프린트 수집 | 불필요 | Atom/XML, 실시간성 좋지만 피어리뷰 안 됨 |
| **OpenReview API v2** (`api2.openreview.net`) | ICLR/NeurIPS/ICML의 decision(oral/spotlight/poster/reject) 조회 | 불필요(공개 데이터) | "진짜 탑티어"를 거르는 핵심 소스 |
| **Semantic Scholar Academic Graph API** | arXiv ID 매칭으로 인용수·TLDR·저자 정보 붙이기, dedupe | 무료(키 없이 100req/5분, 키 신청 시 상향) | 여러 소스에서 모은 논문 통합용 |
| Hugging Face Daily/Trending Papers | "요즘 화제인 논문" 커뮤니티 시그널 | 비공식(스크래핑) | 보조 신호로만, 필수는 아님 |

**탑티어를 거르는 핵심 트릭**: arXiv만 쓰면 "최신"은 알아도 "잘 만든 논문"인지는 모른다.
OpenReview로 decision까지 가져와서 Oral/Spotlight만 필터링하면 상위 1~5%만 남는다.

## 3. D1 스키마 (papers 테이블)

`docs/HANDOFF.md`의 papers 테이블을 아래로 대체한다.

```sql
CREATE TABLE papers (
  id TEXT PRIMARY KEY,
  arxiv_id TEXT UNIQUE,
  title TEXT NOT NULL,
  authors TEXT,
  abstract TEXT,
  source TEXT NOT NULL DEFAULT 'arxiv',   -- 'arxiv' | 'openreview'
  venue TEXT,                             -- 'ICLR2026' | 'NeurIPS2025' | 'ICML2025' | null(arxiv only)
  decision TEXT,                          -- 'oral' | 'spotlight' | 'poster' | 'reject' | null
  semantic_scholar_id TEXT,
  citation_count INTEGER,
  relevance_score REAL,
  relevance_reason TEXT,
  analysis_md TEXT,                       -- 딥 분석 결과 (아키텍처/한계점/관련연구)
  status TEXT NOT NULL DEFAULT 'suggested', -- 'suggested' | 'analyzed' | 'posted' | 'skipped'
  fetched_at TEXT NOT NULL,
  linked_post_id TEXT
);
```

## 4. 파이프라인 단계

```
1. 수집
   ├─ arXiv API: cs.CL/cs.AI/cs.LG/cs.AR 최신 논문
   └─ OpenReview API: ICLR/NeurIPS/ICML 최근 accept 목록 (decision 포함)
2. 정제 (Semantic Scholar)
   └─ arXiv ID로 매칭 → 인용수/TLDR/저자 정보 붙이기 → 중복 제거
      → venue, decision, citation_count 컬럼 채움
3. 탑티어 필터
   └─ decision이 oral/spotlight인 논문 최우선
      OpenReview 매칭 없는 arXiv 단독 논문은 인용 증가 속도(citation velocity)로 대체 신호 사용
4. 관심사 매칭 스코어링 (Anthropic API)
   └─ 관심 프로필(transformer 아키텍처 / NPU·AI반도체 / 에이전트 시스템)과 비교
      → relevance_score, relevance_reason 채움
5. 딥 분석 (상위 N편만)
   └─ 아키텍처 분해 + 병목/한계점 + 관련 연구 연결까지 분석
      → analysis_md에 저장, status='analyzed'
6. 초안 생성
   └─ analysis_md 기반으로 docs/HANDOFF.md §2의 figure 블록(아키텍처 다이어그램 포함)을
      사용한 포스트 초안 생성 → posts 테이블에 status='draft'
```

## 5. 딥 분석(4단계) 프롬프트 방향

상위 N편에 대해서만 아래 구조로 분석한다 (모든 후보에 다 적용하면 비용이 커짐):

1. 핵심 기여(contribution) 1~2문장 요약
2. 아키텍처/방법론 분해 — 기존 방식과 뭐가 다른지
3. 한계점 / 왜 이게 완벽하지 않은지
4. 사용자의 관심사(transformer, NPU, 에이전트)와 어떻게 연결되는지, 구현해볼 만한 부분이 있는지
5. 관련 연구 1~2편 (Semantic Scholar 추천 API 활용)

## 6. 이 파이프라인 관련 체크포인트 질문

- [ ] 탑티어 판정 기준(예: oral/spotlight만 vs poster도 포함)을 넓히거나 좁힐 필요가 보이면 → 확인 후 변경
- [ ] Semantic Scholar API 요청이 무료 한도(100req/5분)에 근접하면 → 키 신청 여부를 먼저 확인 (임의로 캐싱 전략 바꾸지 말고 상의)
- [ ] 딥 분석 대상 논문 수(N)를 늘리면 Anthropic API 비용이 커짐 → 기본값에서 변경 전 확인

이 항목들은 `docs/HANDOFF.md` §6의 전역 체크리스트에도 그대로 반영되어 있다.
