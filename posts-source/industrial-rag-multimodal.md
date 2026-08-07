---
slug: industrial-rag-multimodal
title: "산업 현장 데이터는 텍스트만이 아니다 — 이미지+문서 하이브리드 RAG 구현기"
excerpt: "GQA/MLA 이후의 다음 단계. 결함 이미지와 기술 문서를 CLIP 하나로 잇겠다는 계획은 절반만 성공했다. 이미지끼리는 Recall@1 95%로 잘 묶였지만, 이미지-문서 유사도는 0.236에 표준편차 0.011 — 순위가 아예 안 갈렸다. 안 된 절반을 지우지 않고 남긴 기록."
tags: [rag, multimodal, clip, industrial, defect-detection, hybrid-search, production]
status: published
source_ref: https://github.com/chjnett/tech_Blog/tree/main/posts-assets/industrial-rag-multimodal
---

## 1부. 도입: 산업 현장의 "텍스트 전용 RAG" 문제

지난 3개월간 Attention → KV Cache → GQA → MLA로 거쳐오며 모델 아키텍처를 파고들었다. 각 단계에서 "왜 이게 필요한가"를 직접 미니 구현으로 검증했고, 그 과정이 설득력 있었다.

그런데 한 가지 놓친 게 있었다. **"실제 산업 현장 데이터는 텍스트만이 아니라는 것."**

내가 지원하려는 회사(Field Data Engineer 직군)의 업무를 다시 생각해보니:

- 설비에서 결함이 발생 → **이미지로 캡처됨** (카메라, 센서)
- 기술자가 원인 파악 필요 → **기술 매뉴얼, 도면, 정비 기록 검색** (PDF)
- 문제: 텍스트 전용 RAG는 이미지 속 패턴을 못 본다
- 문제: 하이브리드 검색도 표·차트 같은 구조화된 정보는 놓친다

**이 글의 목표**: "이미지형 산업 데이터 + 문서형 기술 자료"를 CLIP 멀티모달 검색으로 통합하고, 실제로 얼마나 잘 되는지 검증하기.

---

## 2부. 축 1: 이미지형 산업 데이터 — 라벨 없이 결함을 찾는다

### 2-1. 문제: 새로운 결함 유형이 계속 생긴다

제조 현장의 품질 관리 시스템은 보통 다음과 같이 돈다:

1. 설비에서 제품 생산
2. 검사자가 육안 또는 카메라로 검사
3. 결함 발견 → 로깅 (이미지 + 텍스트)
4. 원인 파악 → 기술자 투입

문제는 2단계와 4단계 사이의 "병목"이다.

- **라벨링 비용**: 새로운 결함 유형마다 수백 장을 라벨링 → 모델 재학습
- **시간 지연**: 검사자 경험에만 의존 (신입은 모르는 결함 놓침)
- **일반화 실패**: 조명, 각도, 새로운 기계 → 모델이 안 먹음

### 2-2. 해법: Zero-shot 이상탐지 (CLIP + 문헌 검색)

L-PBF(Laser Powder Bed Fusion) 논문에서 본 접근법:

> "라벨된 학습 데이터가 없으니, 문헌에서 결함 이미지를 검색하고, 그것을 기준으로 삼자."

**아이디어**:
1. CLIP으로 산업 결함 이미지를 임베딩
2. 새로운 결함 사진이 들어오면 유사 이미지 검색
3. 같은 종류인지 판단 → 기술자에게 "이 결함은 과거에 이렇게 처리했습니다" 제안

**장점**:
- 라벨이 필요 없다 (Zero-shot)
- 새로운 결함 유형도 "가장 가까운" 과거 사례를 찾아줄 수 있다
- 재학습 비용 0

### 2-3. 실제 CLIP 모델로 검증

**실험 설정**:
- 모델: OpenAI CLIP-ViT-B/32 (실제 모델)
- 이미지: 20개 합성 결함 이미지 (4가지 타입: scratch, dent, stain, crack)
- 계산: 실제 CLIP 임베딩 벡터 추출 및 유사도 계산

**이미지 검색 성능**:

| 메트릭 | 값 | 의미 |
|--------|-----|------|
| **Recall@1** | **95%** | 가장 유사한 이미지가 같은 유형일 확률 |
| **Recall@5** | **100%** | Top-5 중 정확한 유형이 반드시 있음 |
| **Recall@10** | 100% | Top-10 중 정확한 유형이 반드시 있음 |
| **인코딩 속도** | 20장 0.23초 | 실시간 가능 |

![CLIP 이미지-이미지 검색 Recall. 합성 이미지 20장 기준.](/posts-assets/industrial-rag-multimodal/01_image_retrieval_performance.png)

**결론**: 같은 결함 유형끼리는 CLIP 임베딩 공간에서 잘 뭉친다. 다만 뒤에서 다시
말하겠지만 **이건 쉬운 과제를 푼 결과**다 — 4개 유형이 시각적으로 확연히 다르다.

---

## 3부. 축 2: 문서형 산업 데이터 — 기술 매뉴얼과 이미지를 연결한다

### 3-1. 문제: "결함을 찾았는데, 어쩌지?"

이미지 검색이 "이건 과거에도 발생한 결함이다"를 알려줬다고 하자.

그 다음 질문: **"그럼 어떻게 처리했지?"**

답은 보통:
- 기술 매뉴얼 PDF
- 과거 정비 기록
- 기술자의 경험 메모

**하이브리드 RAG의 역할**: 결함 이미지 → 자동으로 관련 문서 추천

### 3-2. 구현: 이미지 + 문서 CLIP 임베딩

**아이디어**:
- CLIP은 이미지와 텍스트를 **같은 벡터 공간에 임베딩**
- 이미지 임베딩과 텍스트 임베딩을 비교 → 유사도 점수

**아키텍처**:

![Architecture](/posts-assets/industrial-rag-multimodal/05_architecture_diagram.png)

파이프라인 흐름:
1. 결함 이미지 → CLIP Vision Encoder → 임베딩 벡터
2. 기술 매뉴얼 PDF (문장 단위) → CLIP Text Encoder → 임베딩 벡터
3. Cosine Similarity 계산 → 상위 K개 관련 문서 추천

### 3-3. 실제 CLIP 모델로 검증

**하이브리드 검색 설정**:
- 이미지: 20개 결함 이미지 (위와 동일)
- 문서: 8개의 산업 검사 관련 텍스트 쿼리
- 계산: CLIP 이미지-텍스트 유사도 (실제 모델)

**이미지-문서 매칭 성능**:

| 메트릭 | 값 | 평가 |
|--------|-----|------|
| **평균 유사도** | 0.236 | 낮음 |
| **표준편차** | 0.011 | **문제** — 아래 참고 |
| **최대 / 최소** | 0.259 / 0.208 | 전체 폭이 0.051 |

![이미지-문서 유사도 160쌍의 분포. 0~1 구간 중 0.21~0.26에만 몰려 있다.](/posts-assets/industrial-rag-multimodal/02_similarity_distribution.png)

**여기서 평균값보다 중요한 건 표준편차 0.011이다.**

검색은 "점수가 높은가"가 아니라 "점수가 갈리는가"로 동작한다. 8개 쿼리의 평균
유사도를 세워보면 1위(0.248)와 8위(0.216)의 차이가 **0.032**밖에 안 된다.

![쿼리별 평균 유사도 — 1위와 8위 차이가 0.032](/posts-assets/industrial-rag-multimodal/03_query_ranking_spread.png)

"surface defect detection"과 "industrial quality inspection" 중 어느 문서가 이
결함 이미지에 더 맞는지, CLIP은 사실상 대답하지 못한다. 임베딩 값이 조금만 흔들려도
순위가 뒤집히는 폭이다.

**결론**: 일반 CLIP은 이미지와 산업 문서를 같은 공간에 놓기는 하지만, **그 안에서
줄을 세우지는 못한다.** 문서 추천 기능을 이 상태로 붙이면 사실상 무작위 추천이 된다.

---

## 4부. 공통 인사이트: 어디까지 되고 어디서 깨지는가

### 같은 모델, 갈린 결과

| 과제 | 지표 | 결과 | 판정 |
|---|---|---|---|
| **이미지 ↔ 이미지** | Recall@1 | 95% | 쓸 수 있음 (단, 쉬운 데이터) |
| **이미지 ↔ 이미지** | Recall@5 | 100% | 쓸 수 있음 (단, 쉬운 데이터) |
| **이미지 ↔ 문서** | 평균 유사도 | 0.236 | 낮음 |
| **이미지 ↔ 문서** | 표준편차 | 0.011 | **못 씀 — 순위가 안 갈림** |
| **이미지 ↔ 문서** | 쿼리 간 최대차 | 0.032 | **못 씀 — 순위가 안 갈림** |
| 인코딩 속도 | 20장 배치 | 0.23초 | 실시간 가능 |

같은 CLIP 가중치인데 위 둘과 아래 셋의 결론이 정반대다. 이게 이번 실험에서
건진 유일하지만 확실한 사실이다.

### 핵심 발견

**1. 이미지끼리 비교하는 건 잘한다**

CLIP 임베딩 공간에서 "같은 결함 유형끼리 뭉치는가"는 Recall@1 95%로 잘 작동했다.
이건 CLIP이 산업 데이터를 학습해서가 아니라, **시각적으로 다른 것을 다르게 표현하는
일반적인 능력**만으로도 충분한 과제이기 때문이다.

**2. 이미지와 텍스트를 잇는 건 못한다**

같은 모델인데 이미지-텍스트 유사도는 0.236에 그쳤다. 게다가 표준편차가 0.011로
**거의 평평하다** — 8개 문서 쿼리 중 어느 것이 더 관련 있는지 CLIP이 사실상
구분하지 못한다는 뜻이다. 이게 더 뼈아픈 숫자다. 값이 낮은 것보다,
**순위를 못 매기는 것**이 검색 시스템에서는 치명적이다.

**3. 그래서 이 실험의 진짜 결론**

- 이미지 → 유사 사례 검색: 지금 바로 쓸 수 있다
- 이미지 → 관련 문서 추천: **일반 CLIP으로는 안 된다.** 도메인 특화 학습이
  "있으면 좋은 것"이 아니라 **전제 조건**이다
- 검색 속도 <50ms → 병목은 성능이 아니라 품질이다

### 이 실험이 증명하지 못하는 것

숫자를 그대로 믿으면 안 되는 이유를 먼저 적어둔다.

- **이미지가 합성이다.** MVTec AD 원본 다운로드가 막혀서, 4가지 결함 유형(scratch,
  dent, stain, crack)을 PIL로 그린 20장으로 대체했다. 실제 제조 이미지의 조명·질감·
  노이즈가 전혀 없다.
- **그래서 Recall@5 100%는 쉬운 과제다.** 4개 클래스가 시각적으로 확연히 다르고
  각 5장씩이므로, 같은 유형을 Top-5에 넣는 건 어려운 일이 아니다. **실제 MVTec에서
  이 숫자가 재현될 거라고 기대하면 안 된다.**
- **N=20은 통계가 아니다.** 이미지 한 장이 Recall을 5%씩 움직인다.

반대로, **낮게 나온 쪽(0.236, 표준편차 0.011)은 신뢰할 만하다.** 조건을 유리하게
줬는데도 이미지-텍스트 정렬이 안 됐다는 뜻이라, 실제 데이터에서 더 좋아질 이유가 없다.
즉 이 실험의 쓸모는 "CLIP이 잘한다"를 보인 게 아니라, **어디서 깨지는지를 특정한 것**이다.

---

## 5부. 미니 구현과 실제 결과

### 코드 구조

```
posts-assets/industrial-rag-multimodal/
├── 1_setup.py                  # 데이터 다운로드, 환경 설정
├── 2_image_search.py           # CLIP으로 이미지 임베딩 + 유사도 검색
├── 3_document_search.py        # PDF 텍스트 추출 + 하이브리드 검색
├── 4_evaluate.py               # 성능 평가 + 벤치마크
├── 5_visualize.py              # Figure 생성
└── results/
    ├── real_results.json       # 실제 CLIP 측정값 (이 글의 근거)
    └── figures/
        ├── 01_image_retrieval_performance.png
        ├── 02_similarity_distribution.png
        ├── 03_benchmark_comparison.png
        └── 05_architecture_diagram.png
```

### 주요 구현 포인트

**이미지 검색** (2_image_search.py):
```python
# CLIP 로드
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")

# 이미지 임베딩
embeddings = []
for image in images:
    features = model.get_image_features(image)
    features = features / features.norm()  # 정규화
    embeddings.append(features)

# 유사도 검색
similarities = cosine_similarity(query_emb, embeddings)
top_k_idx = argsort(similarities)[::-1][:5]
```

**문서 검색** (3_document_search.py):
```python
# PDF에서 텍스트 추출 → 문장 단위 분할
sentences = extract_text_from_pdf(pdf_path).split('.')

# 문장별 텍스트 임베딩
text_embeddings = []
for sentence in sentences:
    features = model.get_text_features(sentence)
    text_embeddings.append(features)

# 이미지-문서 유사도
similarities = cosine_similarity(image_emb, text_embeddings)
```

### 재현 방법

이 글의 모든 숫자는 스크립트 하나에서 나온다. seed가 고정돼 있어 그대로 재현된다.

```terminal
$ python run_real_clip.py
[device] cpu
[1/5] loading CLIP ViT-B/32 (openai) ...
[3/5] encoding images ...
      (20, 512) in 0.23s
[5/5] computing similarities ...
      Recall@1: 95%
      Recall@5: 100%
      Recall@10: 100%
      image-text sim: 0.236 ± 0.011 [0.208, 0.259]
      per-query spread: 0.032

$ python make_figures.py
✓ 01_image_retrieval_performance.png
✓ 02_similarity_distribution.png
✓ 03_query_ranking_spread.png
```

`make_figures.py`에는 하드코딩된 수치가 없다. `results/real_results.json`만 읽어서
그린다 — 본문 숫자와 그림이 어긋날 수 없게 하려는 장치다. (이 글을 쓰는 도중 실제로
한 번 어긋났고, 그래서 이렇게 바꿨다.)

---

## 6부. 마무리: FDE 역할로 수렴하기

### 이 모든 게 왜 중요한가?

필드 데이터 엔지니어(FDE)의 핵심 역할:

> "산업 현장 문제를 정의하고, LLM/검색으로 **실질적 가치**를 만든다"

여기서 "실질적 가치"는 **동작하는 것과 동작하지 않는 것을 갈라놓는 일**이라고 생각한다.
이번에 실제로 한 일은 그거였다.

1. **문제 정의**: "텍스트 전용 RAG는 이미지를 못 본다" → 맞는 문제 설정이었다
2. **검증 결과**: 같은 CLIP인데 두 과제의 결과가 갈렸다
   - 이미지 ↔ 이미지: Recall@1 95% (단, 쉬운 합성 데이터 기준)
   - 이미지 ↔ 텍스트: 유사도 0.236, 표준편차 0.011 → **순위가 안 갈림**
3. **그래서 내린 판단**:
   - 이미지 검색만 먼저 붙인다
   - 문서 추천은 도메인 학습 전까지 **붙이지 않는다** — 틀린 문서를
     자신 있게 추천하는 게 아무것도 없는 것보다 나쁘다
4. **다음 검증 대상**: 합성이 아닌 실제 MVTec AD 이미지

### 다음으로 해볼 것

1. **실제 MVTec AD로 재측정** (최우선)
   - 지금 숫자는 합성 이미지 20장 기준이라 그대로 인용할 수 없다
   - 같은 스크립트에 원본 이미지만 갈아끼우면 되므로 비용은 데이터 확보뿐

2. **도메인 특화 학습**: 산업 데이터로 CLIP Fine-tuning
   - 목표는 유사도 절대값이 아니라 **표준편차를 키우는 것** — 문서 간 순위가
     갈려야 검색이 성립한다
   - 비용: GPU 시간 몇 시간, 라벨링 작은 규모

3. **OCR / Graph DB**: 지금은 안 한다
   - 이미지-텍스트 정렬이 0.236인 상태에서 그 위에 구조를 얹어봐야
     쓰레기를 더 정교하게 정리하는 것뿐이다
   - 하위 레이어가 고쳐진 뒤에 다시 판단

### 최종 메시지

이 글에서 자랑할 만한 결과는 없다. Recall@5 100%는 쉬운 과제를 푼 것이고,
0.236은 실패한 숫자다.

대신 남은 건 **"어디가 깨지는지 특정했다"**는 것이다.

- CLIP을 이미지 검색에 쓰는 건 → 근거 있음
- CLIP을 이미지-문서 연결에 그대로 쓰는 건 → **하면 안 됨**, 이유는 순위가 안 갈려서

처음엔 "멀티모달 RAG를 만들었다"고 쓰려고 했는데, 실제로 돌려보니 절반은 안 됐다.
그 절반을 지우지 않고 남겨두는 게 이 기록의 유일한 값어치라고 생각한다.

GQA/MLA에서 "왜 이 아키텍처가 필요한가"를 미니 구현으로 확인했던 것처럼,
여기서도 확인한 건 "된다"가 아니라 **"어디까지 되는가"**였다.

---

## 참고

**코드 및 데이터**: [posts-assets/industrial-rag-multimodal](https://github.com/chjnett/tech_Blog/tree/main/posts-assets/industrial-rag-multimodal)

**실행 방법**:
```bash
pip install open-clip-torch matplotlib numpy pillow

python run_real_clip.py    # 측정 → results/real_results.json
python make_figures.py     # json → figure 3장
```

CPU에서 끝까지 몇 초면 끝난다 (모델 로딩 제외). GPU 필요 없음.

**주요 논문**:
- CLIP: *Learning Transferable Visual Models From Natural Language Supervision*
  (Radford et al., 2021) — [arXiv:2103.00020](https://arxiv.org/abs/2103.00020)
- RAG: *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*
  (Lewis et al., 2020) — [arXiv:2005.11401](https://arxiv.org/abs/2005.11401)
- MVTec AD: *A Comprehensive Real-World Dataset for Unsupervised Anomaly Detection*
  (Bergmann et al., 2019) — 이번엔 받지 못해 합성 이미지로 대체했다
