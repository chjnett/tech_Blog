"""
train_sanity_check.py — 합성 데이터로 300 스텝만 학습시켜
MHA/GQA/MQA가 모두 정상적으로 loss가 줄어드는지 정성적으로 확인한다.
"""
import random
import torch
from model import MiniGPT, GPTConfig

torch.manual_seed(0)
random.seed(0)

VOCAB = list("abcdefghij")
STOI = {ch: i for i, ch in enumerate(VOCAB)}
VOCAB_SIZE = len(VOCAB)

BLOCK_SIZE, BATCH_SIZE, N_STEPS, LR = 64, 32, 300, 3e-3
N_LAYER, N_EMBD, N_HEAD = 4, 64, 4

CONFIGS = {"MHA  (n_kv=4)": 4, "GQA-2 (n_kv=2)": 2, "MQA  (n_kv=1)": 1}


def make_synthetic_corpus(n_chars=20000):
    """몇 가지 반복 주기를 가진 패턴을 섞어 이어붙인 합성 텍스트 (자체 생성, 저작권 문제 없음)."""
    periods = [2, 3, 4, 5]
    out = []
    while len(out) < n_chars:
        period = random.choice(periods)
        pattern = [random.choice(VOCAB) for _ in range(period)]
        repeats = random.randint(5, 15)
        out.extend(pattern * repeats)
    return "".join(out[:n_chars])


def get_batch(data_ids, block_size, batch_size):
    ix = torch.randint(0, len(data_ids) - block_size - 1, (batch_size,))
    x = torch.stack([data_ids[i:i + block_size] for i in ix])
    y = torch.stack([data_ids[i + 1:i + block_size + 1] for i in ix])
    return x, y


def train_one_config(n_kv_head, data_ids):
    cfg = GPTConfig(vocab_size=VOCAB_SIZE, block_size=BLOCK_SIZE, n_layer=N_LAYER,
                     n_head=N_HEAD, n_kv_head=n_kv_head, n_embd=N_EMBD, dropout=0.0)
    model = MiniGPT(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    losses = []
    for _ in range(N_STEPS):
        x, y = get_batch(data_ids, BLOCK_SIZE, BATCH_SIZE)
        _, loss, _ = model(x, targets=y)
        opt.zero_grad(); loss.backward(); opt.step()
        losses.append(loss.item())
    return losses


def main():
    text = make_synthetic_corpus()
    data_ids = torch.tensor([STOI[c] for c in text], dtype=torch.long)
    for name, n_kv in CONFIGS.items():
        losses = train_one_config(n_kv, data_ids)
        print(f"{name}: 최종 loss(마지막 30스텝 평균) = {sum(losses[-30:])/30:.4f}")


if __name__ == "__main__":
    main()
