"""
run_real_clip.py — 실제 CLIP으로 측정하고 raw 값까지 저장한다.

이 글의 모든 숫자는 이 스크립트 한 번의 실행에서 나온다.
  - 이미지 20장(합성 결함 4종 x 5장) → CLIP 이미지 임베딩
  - 문서 쿼리 8개 → CLIP 텍스트 임베딩
  - 이미지-이미지 Recall@k, 이미지-텍스트 유사도 분포

출력: results/real_results.json  (raw similarity 배열 포함 — figure가 이걸 그린다)
"""

import json
import time
from pathlib import Path

import numpy as np
import torch
import open_clip
from PIL import Image, ImageDraw

SEED = 42
DEFECT_TYPES = ["scratch", "dent", "stain", "crack"]
N_IMAGES = 20

DOC_QUERIES = [
    "surface defect detection",
    "industrial quality inspection",
    "anomaly detection in manufacturing",
    "automated visual inspection",
    "defect classification",
    "real-time quality control",
    "neural network inspection system",
    "defect analysis",
]


def create_defect_image(defect_type: str, size: int = 224) -> Image.Image:
    """결함 유형별 합성 이미지. 실제 MVTec 이미지를 못 받아서 쓰는 대체물."""
    img = Image.new("RGB", (size, size), color="white")
    draw = ImageDraw.Draw(img)

    # 배경 텍스처 (모든 유형 공통 — 배경만으로 구분되지 않게)
    for y in range(0, size, 20):
        for x in range(0, size, 20):
            if (x + y) % 40 == 0:
                draw.rectangle([x, y, x + 10, y + 10], fill="#f0f0f0")

    if defect_type == "scratch":
        for _ in range(2):
            x1, y1 = np.random.randint(30, size - 30, 2)
            x2 = x1 + np.random.randint(50, 120)
            y2 = y1 + np.random.randint(-20, 20)
            draw.line([(x1, y1), (x2, y2)], fill="black", width=4)
    elif defect_type == "dent":
        x, y = np.random.randint(60, size - 60, 2)
        r = np.random.randint(15, 35)
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill="#cccccc", outline="gray")
        draw.ellipse([(x - r + 5, y - r + 5), (x + r - 5, y + r - 5)], fill="#dddddd")
    elif defect_type == "stain":
        x, y = np.random.randint(60, size - 60, 2)
        for _ in range(3):
            ox, oy = np.random.randint(-25, 25, 2)
            r = np.random.randint(8, 15)
            draw.ellipse([(x + ox - r, y + oy - r), (x + ox + r, y + oy + r)], fill="#8b6f47")
    elif defect_type == "crack":
        x, y = size // 2, size // 2
        for _ in range(5):
            x2 = x + np.random.randint(-30, 30)
            y2 = y + np.random.randint(-30, 30)
            draw.line([(x, y), (x2, y2)], fill="#333333", width=2)
            x, y = x2, y2

    return img


def main() -> None:
    np.random.seed(SEED)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[device] {device}")

    print("[1/5] loading CLIP ViT-B/32 (openai) ...")
    t0 = time.time()
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
    model = model.to(device).eval()
    print(f"      done in {time.time() - t0:.1f}s")

    print(f"[2/5] generating {N_IMAGES} synthetic defect images ...")
    images, labels = [], []
    for i in range(N_IMAGES):
        dtype = DEFECT_TYPES[i % len(DEFECT_TYPES)]
        images.append(create_defect_image(dtype))
        labels.append(dtype)

    print("[3/5] encoding images ...")
    t0 = time.time()
    with torch.no_grad():
        batch = torch.stack([preprocess(im) for im in images]).to(device)
        img_emb = model.encode_image(batch)
        img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True)
    img_emb = img_emb.cpu().numpy()
    encode_s = time.time() - t0
    print(f"      {img_emb.shape} in {encode_s:.2f}s")

    print("[4/5] encoding text queries ...")
    with torch.no_grad():
        tokens = open_clip.tokenize(DOC_QUERIES).to(device)
        txt_emb = model.encode_text(tokens)
        txt_emb = txt_emb / txt_emb.norm(dim=-1, keepdim=True)
    txt_emb = txt_emb.cpu().numpy()

    print("[5/5] computing similarities ...")
    # 이미지 ↔ 이미지: 자기 자신 제외 후 Top-k 안에 같은 라벨이 있는지
    img_sim = img_emb @ img_emb.T
    np.fill_diagonal(img_sim, -np.inf)

    recalls = {}
    for k in (1, 5, 10):
        hit = sum(
            labels[i] in [labels[j] for j in np.argsort(img_sim[i])[-k:]]
            for i in range(N_IMAGES)
        )
        recalls[k] = hit / N_IMAGES
        print(f"      Recall@{k}: {recalls[k]:.0%}")

    # 이미지 ↔ 텍스트: 20 x 8 = 160개 유사도
    img_txt = img_emb @ txt_emb.T
    sims = img_txt.flatten()
    print(f"      image-text sim: {sims.mean():.3f} ± {sims.std():.3f} "
          f"[{sims.min():.3f}, {sims.max():.3f}]")

    # 쿼리별 평균 — 순위가 갈리는지 보는 핵심 지표
    per_query = img_txt.mean(axis=0)
    print(f"      per-query spread: {per_query.max() - per_query.min():.3f}")

    results = {
        "metadata": {
            "model": "open_clip ViT-B-32 / pretrained=openai",
            "device": device,
            "seed": SEED,
            "num_images": N_IMAGES,
            "defect_types": DEFECT_TYPES,
            "doc_queries": DOC_QUERIES,
            "image_encode_seconds": round(encode_s, 3),
            "caveat": "images are synthetic (PIL-drawn), not MVTec AD",
        },
        "image_retrieval": {
            "recall_top1": recalls[1],
            "recall_top5": recalls[5],
            "recall_top10": recalls[10],
            "search_ms_per_query": round(encode_s / N_IMAGES * 1000, 1),
        },
        "hybrid_search": {
            "mean": float(sims.mean()),
            "std": float(sims.std()),
            "min": float(sims.min()),
            "max": float(sims.max()),
            "per_query_mean": [float(v) for v in per_query],
            "per_query_spread": float(per_query.max() - per_query.min()),
            "raw_similarities": [float(v) for v in sims],
        },
    }

    out = Path("results/real_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"\n✓ wrote {out} ({len(sims)} raw similarity values)")


if __name__ == "__main__":
    main()
