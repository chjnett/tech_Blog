# attention-is-all-you-need-kv-cache-gqa

이 글의 코드 전체: [chjnett.dev/posts/attention-is-all-you-need-kv-cache-gqa](https://chjnett.dev/posts/attention-is-all-you-need-kv-cache-gqa)

MHA/GQA/MQA를 `n_kv_head` 파라미터 하나로 전환할 수 있는 미니 GPT 구현 + 벤치마크 + 학습 sanity check.

- `model.py` — decoder-only Transformer, KV 캐시 지원
- `benchmark.py` — 파라미터 수 / KV 캐시 메모리 / 추론 속도 비교
- `train_sanity_check.py` — 합성 데이터로 300 스텝 학습, loss 수렴 확인

## 실행

```
pip install torch --break-system-packages
python benchmark.py
python train_sanity_check.py
```

GPU 없이 CPU에서 그대로 재현 가능하다.
