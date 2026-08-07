"""
2_image_search.py - CLIP 기반 이미지 검색

Zero-shot 이상 탐지: 라벨 없이 결함 이미지 검색
- 이미지 → CLIP 임베딩
- 유사도 검색 (cosine similarity)
- 성능 평가 (Recall@5, Recall@10)
"""

import torch
import numpy as np
from pathlib import Path
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from sklearn.metrics.pairwise import cosine_similarity
import json
import time
from tqdm import tqdm

print("=" * 80)
print("Step 2: Image Search with CLIP")
print("=" * 80)

# ─────────────────────────────────────────────────────────────
# 1. 환경 설정
# ─────────────────────────────────────────────────────────────

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"\n[Setup] Device: {device}")

# CLIP 모델 로드
print("[Setup] Loading CLIP model...")
start = time.time()
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
model.eval()
print(f"  ✓ CLIP loaded in {time.time() - start:.1f}s")

# ─────────────────────────────────────────────────────────────
# 2. 데이터셋 준비
# ─────────────────────────────────────────────────────────────

print("\n[Data] Scanning image directories...")

data_dirs = [
    "data/images/Magnetic-Tile-Defects-Dataset-master/Tiles-Collected-Pictures",
    "data/images/mvtec_ad",  # 수동 다운로드 시
]

image_files = []
for data_dir in data_dirs:
    if Path(data_dir).exists():
        print(f"  Found: {data_dir}")
        # 모든 이미지 수집
        for img_path in Path(data_dir).rglob("*.jpg"):
            image_files.append(str(img_path))
        for img_path in Path(data_dir).rglob("*.png"):
            image_files.append(str(img_path))

if not image_files:
    print("  ⚠ No images found!")
    print("  → Run 1_setup.py first or manually download MVTec AD")
    exit(1)

image_files = sorted(image_files)
print(f"  ✓ Found {len(image_files)} images")

# ─────────────────────────────────────────────────────────────
# 3. 이미지 임베딩 생성
# ─────────────────────────────────────────────────────────────

print(f"\n[Embedding] Encoding {len(image_files)} images with CLIP...")

embeddings = []
valid_images = []

with torch.no_grad():
    for img_path in tqdm(image_files, desc="Encoding"):
        try:
            image = Image.open(img_path).convert("RGB")
            # 이미지 크기 정규화 (224x224)
            image = image.resize((224, 224), Image.LANCZOS)

            # CLIP 인코딩
            inputs = processor(images=image, return_tensors="pt").to(device)
            image_features = model.get_image_features(**inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            embeddings.append(image_features.cpu().numpy())
            valid_images.append(img_path)

        except Exception as e:
            print(f"  ✗ Error processing {img_path}: {e}")
            continue

embeddings = np.concatenate(embeddings, axis=0)
print(f"  ✓ Embedded {len(embeddings)} images")
print(f"    Shape: {embeddings.shape}")

# ─────────────────────────────────────────────────────────────
# 4. 유사도 검색 평가
# ─────────────────────────────────────────────────────────────

print("\n[Retrieval] Evaluating image search performance...")

# 파일명으로 카테고리 추론 (defect vs normal)
def get_category(path):
    """파일명으로 카테고리 분류"""
    path_lower = path.lower()
    if "defect" in path_lower or "bad" in path_lower or "ng" in path_lower:
        return "defect"
    elif "normal" in path_lower or "ok" in path_lower or "good" in path_lower:
        return "normal"
    else:
        return "unknown"

categories = [get_category(p) for p in valid_images]

# 카테고리별로 그룹화
defect_indices = [i for i, c in enumerate(categories) if c == "defect"]
normal_indices = [i for i, c in enumerate(categories) if c == "normal"]

print(f"  Defects: {len(defect_indices)}, Normal: {len(normal_indices)}")

# 검색 성능 평가: 결함 이미지 쿼리 → 같은 유형의 결함 검색
retrieval_results = {
    "queries": len(defect_indices),
    "top1": 0,
    "top5": 0,
    "top10": 0,
    "mean_rank": 0,
    "search_times": []
}

for query_idx in tqdm(defect_indices[:100], desc="Searching"):  # 샘플링 (속도)
    query_emb = embeddings[query_idx:query_idx+1]

    # 유사도 계산
    start = time.time()
    similarities = cosine_similarity(query_emb, embeddings)[0]
    retrieval_results["search_times"].append(time.time() - start)

    # Top-K 검색
    top_indices = np.argsort(similarities)[::-1]

    # 같은 카테고리 (결함)의 다른 이미지가 Top-K에 있는가?
    same_category_in_top = 0
    for k in [1, 5, 10]:
        if any(idx in defect_indices and idx != query_idx for idx in top_indices[:k]):
            same_category_in_top = k
            if k == 1:
                retrieval_results["top1"] += 1
            if k >= 5:
                retrieval_results["top5"] += 1
            if k >= 10:
                retrieval_results["top10"] += 1

# ─────────────────────────────────────────────────────────────
# 5. 결과 저장 및 출력
# ─────────────────────────────────────────────────────────────

retrieval_results["recall_top1"] = retrieval_results["top1"] / retrieval_results["queries"]
retrieval_results["recall_top5"] = retrieval_results["top5"] / retrieval_results["queries"]
retrieval_results["recall_top10"] = retrieval_results["top10"] / retrieval_results["queries"]
retrieval_results["mean_search_time"] = np.mean(retrieval_results["search_times"])

print("\n[Results] Image Search Performance:")
print(f"  Recall@1:  {retrieval_results['recall_top1']:.1%}")
print(f"  Recall@5:  {retrieval_results['recall_top5']:.1%}")
print(f"  Recall@10: {retrieval_results['recall_top10']:.1%}")
print(f"  Avg Search Time: {retrieval_results['mean_search_time']*1000:.1f}ms")

# 임베딩 저장 (다음 단계에서 사용)
print("\n[Save] Storing embeddings and metadata...")

np.save("results/embeddings/clip_embeddings.npy", embeddings)

metadata = {
    "image_paths": valid_images,
    "categories": categories,
    "model": "openai/clip-vit-base-patch32",
    "device": device,
    "embedding_dim": embeddings.shape[1],
}

with open("results/embeddings/metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

# 검색 결과 저장
with open("results/image_search_results.json", "w") as f:
    json.dump(retrieval_results, f, indent=2)

print(f"  ✓ Embeddings: results/embeddings/clip_embeddings.npy ({embeddings.nbytes / 1e6:.1f}MB)")
print(f"  ✓ Metadata: results/embeddings/metadata.json")
print(f"  ✓ Results: results/image_search_results.json")

print("\n" + "=" * 80)
print("Next: python 3_document_search.py")
print("=" * 80)
