"""
benchmark.py — MHA / GQA / MQA 세 구성에 대해
  1) 파라미터 수
  2) KV 캐시 메모리 (이론값 계산 + torch로 실측)
  3) 시퀀스 길이별 추론 속도 (tokens/sec, KV 캐시 사용)
를 비교한다.
"""
import time
import torch
from model import MiniGPT, GPTConfig

torch.manual_seed(0)

VOCAB_SIZE = 65
N_LAYER, N_EMBD, N_HEAD = 6, 256, 8
BLOCK_SIZE = 4096

CONFIGS = {
    "MHA  (n_kv=8)": 8,
    "GQA-4 (n_kv=4)": 4,
    "GQA-2 (n_kv=2)": 2,
    "MQA  (n_kv=1)": 1,
}
SEQ_LENS_FOR_SPEED = [64, 256, 1024]
NEW_TOKENS = 64
BYTES_PER_PARAM = 4  # float32


def theoretical_kv_cache_bytes(n_layer, seq_len, n_kv_head, head_dim, bytes_per_val=4):
    return 2 * n_layer * seq_len * n_kv_head * head_dim * bytes_per_val


def build_model(n_kv_head):
    cfg = GPTConfig(vocab_size=VOCAB_SIZE, block_size=BLOCK_SIZE, n_layer=N_LAYER,
                     n_head=N_HEAD, n_kv_head=n_kv_head, n_embd=N_EMBD, dropout=0.0)
    model = MiniGPT(cfg)
    model.eval()
    return model, cfg


def measured_kv_cache_bytes(model, cfg, seq_len):
    x = torch.randint(0, VOCAB_SIZE, (1, seq_len))
    with torch.no_grad():
        _, _, kv_caches = model(x, use_cache=True)
    total = 0
    for k, v in kv_caches:
        total += k.element_size() * k.nelement()
        total += v.element_size() * v.nelement()
    return total


def measure_tokens_per_sec(model, prompt_len, new_tokens):
    x = torch.randint(0, VOCAB_SIZE, (1, prompt_len))
    with torch.no_grad():
        t0 = time.perf_counter()
        model.generate(x, max_new_tokens=new_tokens)
        t1 = time.perf_counter()
    return new_tokens / (t1 - t0)


def main():
    head_dim = N_EMBD // N_HEAD
    models = {}
    print("1) 파라미터 수")
    for name, n_kv in CONFIGS.items():
        model, cfg = build_model(n_kv)
        models[name] = (model, cfg)
        print(f"{name:>16}: {model.num_params():>10,} params")

    print("\n2) KV 캐시 메모리 (이론값, seq_len별)")
    for seq_len in [512, 4096, 32768, 131072]:
        print(f"-- seq_len={seq_len:,} --")
        for name, n_kv in CONFIGS.items():
            theo = theoretical_kv_cache_bytes(N_LAYER, seq_len, n_kv, head_dim, BYTES_PER_PARAM)
            print(f"  {name:>16}: {theo/1e6:8.2f} MB")

    print("\n실측값 (seq_len=1024)")
    for name, (model, cfg) in models.items():
        measured = measured_kv_cache_bytes(model, cfg, seq_len=1024)
        theo = theoretical_kv_cache_bytes(N_LAYER, 1024, CONFIGS[name], head_dim, BYTES_PER_PARAM)
        print(f"  {name:>16}: 실측 {measured/1e6:8.3f} MB  |  이론값 {theo/1e6:8.3f} MB")

    print("\n3) 추론 속도 (tokens/sec)")
    for prompt_len in SEQ_LENS_FOR_SPEED:
        print(f"-- prompt_len={prompt_len} --")
        for name, (model, cfg) in models.items():
            tps = measure_tokens_per_sec(model, prompt_len, NEW_TOKENS)
            print(f"  {name:>16}: {tps:8.1f} tokens/sec")


if __name__ == "__main__":
    main()
