import sys, os, time
import torch

repo_root = '/Users/cheonhyeonjun/tech_blog'
os.chdir(repo_root)
sys.path.append(repo_root)
from model import MiniGPT, GPTConfig
sys.path.append(os.path.join(repo_root, 'scripts'))
from mla_train_sanity import MiniMLA, MLAConfig

# Monkey patch generate method to MiniMLA
@torch.no_grad()
def mla_generate(self, idx, max_new_tokens):
    logits, _, kv_caches = self.forward(idx, use_cache=True, start_pos=0)
    pos = idx.shape[1]
    next_id = torch.argmax(logits[:, -1, :], dim=-1, keepdim=True)
    out = torch.cat([idx, next_id], dim=1)
    for _ in range(max_new_tokens - 1):
        logits, _, kv_caches = self.forward(next_id, use_cache=True, kv_caches=kv_caches, start_pos=pos)
        pos += 1
        next_id = torch.argmax(logits[:, -1, :], dim=-1, keepdim=True)
        out = torch.cat([out, next_id], dim=1)
    return out, kv_caches
MiniMLA.generate = mla_generate

torch.manual_seed(0)

VOCAB_SIZE = 65
N_LAYER, N_EMBD, N_HEAD = 6, 256, 8
BLOCK_SIZE = 4096

CONFIGS = {
    "MHA  (n_kv=8)": ("gqa", 8),
    "GQA-4 (n_kv=4)": ("gqa", 4),
    "GQA-2 (n_kv=2)": ("gqa", 2),
    "MQA  (n_kv=1)": ("gqa", 1),
    "MLA (latent=32)": ("mla", 32),
}
SEQ_LENS_FOR_SPEED = [64, 256, 1024]
NEW_TOKENS = 64
BYTES_PER_PARAM = 4

def theoretical_kv_cache_bytes(arch_type, n_layer, seq_len, val, head_dim, bytes_per_val=4):
    if arch_type == "gqa":
        return 2 * n_layer * seq_len * val * head_dim * bytes_per_val
    else:
        return n_layer * seq_len * val * bytes_per_val

def build_model(arch_type, val):
    if arch_type == "gqa":
        cfg = GPTConfig(vocab_size=VOCAB_SIZE, block_size=BLOCK_SIZE, n_layer=N_LAYER,
                         n_head=N_HEAD, n_kv_head=val, n_embd=N_EMBD, dropout=0.0)
        model = MiniGPT(cfg)
    else:
        cfg = MLAConfig(vocab_size=VOCAB_SIZE, block_size=BLOCK_SIZE, n_layer=N_LAYER,
                         n_head=N_HEAD, latent_dim=val, n_embd=N_EMBD, dropout=0.0)
        model = MiniMLA(cfg)
    model.eval()
    return model, cfg

def measured_kv_cache_bytes(model, cfg, seq_len):
    x = torch.randint(0, VOCAB_SIZE, (1, seq_len))
    with torch.no_grad():
        _, _, kv_caches = model(x, use_cache=True)
    total = 0
    for cache in kv_caches:
        if isinstance(cache, tuple):
            k, v = cache
            total += k.element_size() * k.nelement()
            total += v.element_size() * v.nelement()
        else:
            total += cache.element_size() * cache.nelement()
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
    print("1) Parameter count")
    for name, (arch, val) in CONFIGS.items():
        model, cfg = build_model(arch, val)
        models[name] = (model, cfg, arch, val)
        print(f"{name:>16}: {model.num_params():>10,} params")

    print("\n2) KV cache memory (theoretical, per seq_len)")
    for seq_len in [512, 4096, 32768, 131072]:
        print(f"-- seq_len={seq_len:,} --")
        for name, (model, cfg, arch, val) in models.items():
            bytes_req = theoretical_kv_cache_bytes(arch, N_LAYER, seq_len, val, head_dim)
            print(f"{name:>16}: {bytes_req / 1024**2:>8.2f} MB")

    print("\nMeasured values (seq_len=1024)")
    for name, (model, cfg, arch, val) in models.items():
        meas = measured_kv_cache_bytes(model, cfg, 1024) / 1024**2
        theo = theoretical_kv_cache_bytes(arch, N_LAYER, 1024, val, head_dim) / 1024**2
        print(f"{name:>16}: measured {meas:>8.3f} MB  |  theoretical {theo:>8.3f} MB")

    print("\n3) Inference speed (tokens/sec)")
    for prompt_len in SEQ_LENS_FOR_SPEED:
        print(f"-- prompt_len={prompt_len} --")
        for name, (model, cfg, arch, val) in models.items():
            tps = measure_tokens_per_sec(model, prompt_len, NEW_TOKENS)
            print(f"{name:>16}: {tps:>8.1f} tokens/sec")

if __name__ == "__main__":
    main()
