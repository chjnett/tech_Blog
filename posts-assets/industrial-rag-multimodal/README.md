# Industrial Multimodal RAG — CLIP으로 결함 이미지와 기술 문서를 잇는 실험

블로그 글 [산업 현장 데이터는 텍스트만이 아니다](https://chjnett.dev/posts/industrial-rag-multimodal)의
측정 코드. 글에 나오는 모든 숫자는 이 디렉토리의 스크립트 한 번의 실행에서 나온다.

## 결론부터

| 과제 | 지표 | 결과 | 판정 |
|---|---|---|---|
| 이미지 ↔ 이미지 | Recall@1 / @5 | 95% / 100% | 됨 (단, 쉬운 데이터) |
| 이미지 ↔ 문서 | 평균 유사도 | 0.236 | 낮음 |
| 이미지 ↔ 문서 | 표준편차 | 0.011 | **안 됨** |
| 이미지 ↔ 문서 | 쿼리 간 최대차 | 0.032 | **안 됨** |

핵심은 마지막 두 줄이다. 일반 CLIP은 이미지와 산업 문서를 같은 임베딩 공간에
놓기는 하지만 **그 안에서 순위를 매기지 못한다**. 8개 문서 쿼리의 평균 유사도가
0.216~0.248 사이에 전부 몰려 있어서, 문서 추천을 붙이면 사실상 무작위가 된다.

## 이 실험이 증명하지 못하는 것

- **이미지가 합성이다.** MVTec AD를 받지 못해 4가지 결함(scratch, dent, stain,
  crack)을 PIL로 그린 20장으로 대체했다. 실제 제조 이미지의 조명·질감·노이즈가 없다.
- **그래서 Recall@5 100%는 쉬운 과제다.** 4개 클래스가 시각적으로 확연히 다르다.
  실제 MVTec에서 재현될 거라고 기대하면 안 된다.
- **N=20은 통계가 아니다.** 이미지 한 장이 Recall을 5%씩 움직인다.

반대로 **낮게 나온 쪽(0.236, std 0.011)은 신뢰할 만하다.** 조건을 유리하게 줬는데도
이미지-텍스트 정렬이 안 됐다는 뜻이라, 실제 데이터에서 더 좋아질 이유가 없다.

## 실행

```bash
pip install -r requirements.txt

python run_real_clip.py    # 측정 → results/real_results.json
python make_figures.py     # json → results/figures/*.png
```

CPU에서 몇 초면 끝난다(모델 다운로드 제외). GPU 불필요. `seed=42`로 고정돼 있어
그대로 재현된다.

## 파일

| File | Purpose |
|------|---------|
| `run_real_clip.py` | 합성 이미지 생성 → CLIP 인코딩 → Recall/유사도 측정. **모든 숫자의 출처** |
| `make_figures.py` | `real_results.json`만 읽어서 figure 생성. 하드코딩 수치 없음 |
| `results/real_results.json` | 측정 결과 + raw 유사도 160개 |
| `results/figures/` | 블로그에 실린 그림 |

`make_figures.py`가 JSON만 읽도록 만든 건 의도적이다. 초기 버전에서는 그림이
하드코딩된 샘플 값으로 그려져 **본문 숫자와 그림이 어긋난 채로 배포된 적이 있다.**
지금 구조에서는 그게 불가능하다.

## 다음

1. **실제 MVTec AD로 재측정** — 지금 숫자는 합성 이미지 기준이라 그대로 인용 불가
2. **도메인 특화 fine-tuning** — 목표는 유사도 절대값이 아니라 **표준편차를 키우는 것**.
   문서 간 순위가 갈려야 검색이 성립한다
3. OCR / Graph DB는 하지 않는다 — 하위 레이어가 깨진 상태에서 위에 구조를 얹어봐야
   의미가 없다

## References

- **CLIP**: *Learning Transferable Visual Models From Natural Language Supervision*
  (Radford et al., 2021) — [arXiv:2103.00020](https://arxiv.org/abs/2103.00020)
- **MVTec AD**: *MVTec AD — A Comprehensive Real-World Dataset for Unsupervised
  Anomaly Detection* (Bergmann et al., CVPR 2019) —
  [dataset](https://www.mvtec.com/company/research/datasets/mvtec-ad)
- **RAG**: *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*
  (Lewis et al., 2020) — [arXiv:2005.11401](https://arxiv.org/abs/2005.11401)
