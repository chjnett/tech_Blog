"""
3_document_search.py - ArXiv 논문에서 텍스트 추출 후 이미지와 연결

하이브리드 검색:
  1. 결함 이미지 → CLIP 임베딩
  2. ArXiv 논문 PDF → 텍스트 추출
  3. 논문 텍스트 → CLIP 임베딩 (문장별)
  4. 이미지와 유사한 텍스트 검색
"""

import torch
import numpy as np
import json
from pathlib import Path
from transformers import CLIPProcessor, CLIPModel
from sklearn.metrics.pairwise import cosine_similarity
import time
from tqdm import tqdm

try:
    from pypdf import PdfReader
except ImportError:
    print("Installing pypdf...")
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "pip", "install", "pypdf", "-q"])
    from pypdf import PdfReader

print("=" * 80)
print("Step 3: Document Search & Hybrid Retrieval")
print("=" * 80)

# ─────────────────────────────────────────────────────────────
# 1. CLIP 모델 로드 (이미지 검색과 동일)
# ─────────────────────────────────────────────────────────────

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"\n[Setup] Device: {device}")

print("[Setup] Loading CLIP model...")
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
model.eval()
print("  ✓ CLIP loaded")

# ─────────────────────────────────────────────────────────────
# 2. 이전 단계에서 저장한 이미지 임베딩 로드
# ─────────────────────────────────────────────────────────────

print("\n[Load] Reading image embeddings from previous step...")

embeddings_path = "results/embeddings/clip_embeddings.npy"
metadata_path = "results/embeddings/metadata.json"

if not Path(embeddings_path).exists():
    print("  ✗ Embeddings not found!")
    print("  → Run 2_image_search.py first")
    exit(1)

image_embeddings = np.load(embeddings_path)
with open(metadata_path) as f:
    metadata = json.load(f)

image_paths = metadata["image_paths"]
print(f"  ✓ Loaded {len(image_embeddings)} image embeddings")

# ─────────────────────────────────────────────────────────────
# 3. ArXiv 논문 PDF에서 텍스트 추출
# ─────────────────────────────────────────────────────────────

print("\n[Documents] Extracting text from ArXiv papers...")

doc_dir = Path("data/documents")
pdf_files = list(doc_dir.glob("*.pdf"))

if not pdf_files:
    print("  ⚠ No PDF files found in data/documents/")
    print("  → Run 1_setup.py to download ArXiv papers")
    # 생성 예시 데이터
    sample_texts = {
        "mvtec_ad": [
            "MVTec AD dataset contains 15 categories of industrial defects",
            "Anomaly detection for surface inspection in manufacturing",
            "Normal samples show regular texture patterns",
            "Defective samples include scratches, dents, contamination",
            "Unsupervised anomaly detection methods are crucial",
        ],
        "defect_benchmark": [
            "Deep learning models achieve high accuracy on defect detection",
            "Convolutional neural networks extract spatial features",
            "Transfer learning from ImageNet improves performance",
            "Real-time defect detection in production lines",
        ],
        "anomaly_methods": [
            "Isolation Forest for anomaly detection in high dimensions",
            "Autoencoder-based methods learn normal patterns",
            "One-class SVM for binary normal/abnormal classification",
            "Gaussian mixture models estimate density distributions",
        ]
    }
    documents = sample_texts
    print("  Using sample text data for demonstration")
else:
    documents = {}
    for pdf_path in pdf_files:
        print(f"  Reading {pdf_path.name}...")
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages[:5]:  # 처음 5페이지만
                text += page.extract_text()

            # 문장 단위로 분할
            sentences = text.split(".")
            sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
            documents[pdf_path.stem] = sentences

            print(f"    ✓ Extracted {len(sentences)} sentences")
        except Exception as e:
            print(f"    ✗ Error: {e}")

# ─────────────────────────────────────────────────────────────
# 4. 문서 텍스트를 CLIP으로 임베딩
# ─────────────────────────────────────────────────────────────

print("\n[Embedding] Encoding document texts with CLIP...")

all_sentences = []
sentence_to_doc = []

for doc_name, sentences in documents.items():
    all_sentences.extend(sentences)
    sentence_to_doc.extend([doc_name] * len(sentences))

print(f"  Total sentences: {len(all_sentences)}")

# 텍스트 임베딩
text_embeddings = []
with torch.no_grad():
    for sentence in tqdm(all_sentences, desc="Encoding texts"):
        inputs = processor(text=sentence, return_tensors="pt", padding=True).to(device)
        text_features = model.get_text_features(**inputs)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        text_embeddings.append(text_features.cpu().numpy())

text_embeddings = np.concatenate(text_embeddings, axis=0)
print(f"  ✓ Text embeddings shape: {text_embeddings.shape}")

# ─────────────────────────────────────────────────────────────
# 5. 하이브리드 검색: 이미지 → 관련 문서
# ─────────────────────────────────────────────────────────────

print("\n[Hybrid Search] Finding related documents for images...")

results = {
    "total_images": len(image_embeddings),
    "image_to_documents": [],
}

# 샘플 이미지에 대해 검색 (모든 이미지는 비용 높음)
sample_indices = np.random.choice(len(image_embeddings), min(10, len(image_embeddings)), replace=False)

for img_idx in tqdm(sample_indices, desc="Searching"):
    img_emb = image_embeddings[img_idx:img_idx+1]

    # 이미지-텍스트 유사도 계산
    similarities = cosine_similarity(img_emb, text_embeddings)[0]

    # Top-5 관련 문서
    top_indices = np.argsort(similarities)[::-1][:5]

    image_result = {
        "image_path": image_paths[img_idx],
        "related_documents": []
    }

    for rank, doc_idx in enumerate(top_indices, 1):
        doc_name = sentence_to_doc[doc_idx]
        sentence = all_sentences[doc_idx]
        similarity = float(similarities[doc_idx])

        image_result["related_documents"].append({
            "rank": rank,
            "document": doc_name,
            "text": sentence[:100] + "...",  # 처음 100자
            "similarity": similarity
        })

    results["image_to_documents"].append(image_result)

# ─────────────────────────────────────────────────────────────
# 6. 통계 계산
# ─────────────────────────────────────────────────────────────

print("\n[Statistics] Computing hybrid search metrics...")

doc_relevances = []
for img_result in results["image_to_documents"]:
    avg_sim = np.mean([d["similarity"] for d in img_result["related_documents"]])
    doc_relevances.append(avg_sim)

results["statistics"] = {
    "avg_image_to_document_similarity": float(np.mean(doc_relevances)),
    "std_similarity": float(np.std(doc_relevances)),
    "max_similarity": float(np.max(doc_relevances)),
    "min_similarity": float(np.min(doc_relevances)),
}

# ─────────────────────────────────────────────────────────────
# 7. 결과 저장
# ─────────────────────────────────────────────────────────────

print("\n[Save] Storing results...")

with open("results/document_search_results.json", "w") as f:
    json.dump(results, f, indent=2)

# 문서 임베딩도 저장
np.save("results/embeddings/text_embeddings.npy", text_embeddings)

doc_metadata = {
    "sentences": all_sentences[:len(sentence_to_doc)],
    "document_names": sentence_to_doc,
    "total_documents": len(documents),
}

with open("results/embeddings/doc_metadata.json", "w") as f:
    json.dump(doc_metadata, f, indent=2)

print("  ✓ Results: results/document_search_results.json")
print("  ✓ Text embeddings: results/embeddings/text_embeddings.npy")

# ─────────────────────────────────────────────────────────────
# 8. 샘플 결과 출력
# ─────────────────────────────────────────────────────────────

print("\n[Sample Results] Image → Related Documents:")
if results["image_to_documents"]:
    sample = results["image_to_documents"][0]
    print(f"\nImage: {Path(sample['image_path']).name}")
    print("Top related documents:")
    for doc in sample["related_documents"]:
        print(f"  {doc['rank']}. {doc['document']} (sim: {doc['similarity']:.3f})")
        print(f"     \"{doc['text']}\"")

print("\n" + "=" * 80)
print(f"Hybrid Search Stats:")
print(f"  Avg Image-Document Similarity: {results['statistics']['avg_image_to_document_similarity']:.3f}")
print("=" * 80)
print("Next: python 4_evaluate.py")
print("=" * 80)
