"""
1_setup.py - 환경 설정, 데이터 다운로드, 의존성 확인

Google Colab에서 실행:
!pip install -r requirements.txt
!python 1_setup.py
"""

import os
import sys
import subprocess
from pathlib import Path

print("=" * 80)
print("Industrial Multimodal RAG - Setup")
print("=" * 80)

# ─────────────────────────────────────────────────────────────
# 1. 디렉토리 구조 생성
# ─────────────────────────────────────────────────────────────

print("\n[1/4] Creating directory structure...")

dirs = [
    "data/images",
    "data/documents",
    "results/figures",
    "results/embeddings",
    "cache"
]

for dir_name in dirs:
    Path(dir_name).mkdir(parents=True, exist_ok=True)
    print(f"  ✓ Created: {dir_name}")

# ─────────────────────────────────────────────────────────────
# 2. 라이브러리 버전 확인
# ─────────────────────────────────────────────────────────────

print("\n[2/4] Checking library versions...")

try:
    import torch
    print(f"  ✓ PyTorch {torch.__version__}")
except ImportError:
    print("  ✗ PyTorch not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

try:
    import transformers
    print(f"  ✓ Transformers {transformers.__version__}")
except:
    pass

try:
    from PIL import Image
    print(f"  ✓ Pillow available")
except:
    pass

# ─────────────────────────────────────────────────────────────
# 3. 이미지 데이터셋 다운로드 (공개 샘플)
# ─────────────────────────────────────────────────────────────

print("\n[3/4] Downloading image dataset...")
print("  Note: Using public defect detection samples")

# Option A: Download from GitHub (무게 가벼운 샘플)
# https://github.com/abin24/Magnetic-Tile-Defects-Dataset

import subprocess

sample_urls = {
    "images": "https://github.com/abin24/Magnetic-Tile-Defects-Dataset/archive/refs/heads/master.zip"
}

try:
    if not os.path.exists("data/images/sample_defects"):
        print("  Downloading sample defect images from GitHub...")
        os.chdir("data/images")
        subprocess.run(
            ["wget", "-q", sample_urls["images"], "-O", "sample.zip"],
            check=False
        )
        subprocess.run(
            ["unzip", "-q", "sample.zip"],
            check=False
        )
        print("  ✓ Sample images downloaded")
        os.chdir("../..")
    else:
        print("  ✓ Sample images already exist")
except Exception as e:
    print(f"  ⚠ Could not download images automatically: {e}")
    print("  → Manual download: https://github.com/abin24/Magnetic-Tile-Defects-Dataset")

# ─────────────────────────────────────────────────────────────
# 4. ArXiv 논문 다운로드 (기술 문서)
# ─────────────────────────────────────────────────────────────

print("\n[4/4] Preparing document dataset (ArXiv papers)...")

arxiv_papers = {
    "1904.04998": "MVTec_AD_Comprehensive_Dataset.pdf",
    "2011.14654": "Benchmarking_Deep_Learning_Defect.pdf",
    "2112.13624": "Unsupervised_Anomaly_Detection.pdf"
}

try:
    import arxiv

    for paper_id, filename in arxiv_papers.items():
        filepath = f"data/documents/{filename}"

        if not os.path.exists(filepath):
            print(f"  Downloading {paper_id}...")
            try:
                # ArXiv API로 논문 정보 조회
                client = arxiv.Client()
                results = client.results(arxiv.Search(id_list=[paper_id]))

                for paper in results:
                    paper.download_pdf(dirpath="data/documents/", filename=filename)
                    print(f"    ✓ Downloaded: {filename}")
            except Exception as e:
                print(f"    ⚠ Could not download {paper_id}: {e}")
                print(f"      Manual download: https://arxiv.org/pdf/{paper_id}.pdf")
        else:
            print(f"  ✓ Already exists: {filename}")

except ImportError:
    print("  ⚠ ArXiv module not available")
    print("  → Install: pip install arxiv")

# ─────────────────────────────────────────────────────────────
# 5. 최종 확인
# ─────────────────────────────────────────────────────────────

print("\n" + "=" * 80)
print("Setup Complete!")
print("=" * 80)

print("\nNext steps:")
print("  1. !python 2_image_search.py")
print("  2. !python 3_document_search.py")
print("  3. !python 4_evaluate.py")
print("  4. !python 5_visualize.py")

print("\nDataset structure:")
print("""
data/
├── images/
│   └── sample_defects/ (magnetic tile, steel, fabric, etc)
└── documents/
    ├── MVTec_AD_Comprehensive_Dataset.pdf
    ├── Benchmarking_Deep_Learning_Defect.pdf
    └── Unsupervised_Anomaly_Detection.pdf
""")

print("\nNote:")
print("  - For full MVTec AD dataset, download from:")
print("    https://www.mvtec.com/company/research/datasets/mvtec-ad")
print("  - Extract to: data/images/mvtec_ad/")
print("  - The scripts will auto-detect if it exists")
