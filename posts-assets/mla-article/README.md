# MLA (Multi-head Latent Attention) 미니 구현체 및 벤치마크

본 디렉토리에는 블로그 포스트 "GQA의 한계, 그리고 MLA로 넘어가기 — 논문 스터디와 직접 구현"에서 사용한 코드들이 포함되어 있습니다. GPU 없이 CPU만으로도 실행 가능하도록 작성되었습니다.

## 파일 구성

*   `model.py`: nanoGPT 스타일의 decoder-only Transformer 모델에 MLA (Multi-head Latent Attention) 모듈을 추가한 구현체입니다. `n_kv_head` 파라미터 설정을 통해 MHA, GQA, MQA 그리고 MLA까지 전환하며 비교할 수 있습니다.
*   `benchmark_gqa_mla.py`: 파라미터 수, KV 캐시 메모리 사용량 (이론값 및 실측값), 프롬프트 길이별 추론 속도를 측정하고 비교하는 벤치마크 스크립트입니다.
*   `mla_train_sanity.py`: 합성 데이터를 사용하여 300 스텝 동안 학습을 진행하고 정상적으로 Loss가 수렴하는지 확인하는 sanity check 스크립트입니다.

## 실행 방법

`torch` 패키지만 설치되어 있으면 바로 실행할 수 있습니다.

```bash
# 벤치마크 실행 (KV 캐시 및 속도 비교)
python benchmark_gqa_mla.py

# 학습 Sanity Check (Loss 수렴 확인)
python mla_train_sanity.py
```
