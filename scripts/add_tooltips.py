import re
import os

TOOLTIPS = {
    r'\bKV 캐시\b': '<span class="tooltip" data-tooltip="(Key-Value Cache) 이전 토큰들의 K, V 벡터를 메모리에 저장해 재계산 방지" tabindex="0">KV 캐시</span>',
    r'\bMHA\b': '<span class="tooltip" data-tooltip="(Multi-Head Attention) 쿼리마다 독립적인 K, V 헤드를 갖는 기본 어텐션" tabindex="0">MHA</span>',
    r'\bMQA\b': '<span class="tooltip" data-tooltip="(Multi-Query Attention) 모든 쿼리 헤드가 단 1개의 K, V 헤드를 공유" tabindex="0">MQA</span>',
    r'\bGQA\b': '<span class="tooltip" data-tooltip="(Grouped-Query Attention) 쿼리 헤드들을 그룹으로 묶어 K, V 헤드를 공유" tabindex="0">GQA</span>',
    r'\bMLA\b': '<span class="tooltip" data-tooltip="(Multi-head Latent Attention) K, V를 저랭크 잠재 공간으로 압축하는 어텐션" tabindex="0">MLA</span>',
    r'\bUp-projection\b': '<span class="tooltip" data-tooltip="잠재 벡터(Latent Vector)를 원래 차원 크기의 K, V 행렬로 복원하는 선형 변환" tabindex="0">Up-projection</span>',
    r'\b자기회귀 디코딩\b': '<span class="tooltip" data-tooltip="(Autoregressive Decoding) 이전 토큰들로 다음 토큰을 하나씩 순차 예측" tabindex="0">자기회귀 디코딩</span>'
}

def process_file(filename):
    with open(filename, 'r') as f:
        text = f.read()
    
    # Split by code blocks, html tags, image links, table pipes, frontmatter
    parts = re.split(r'(```.*?```|<[^>]+>|!\[.*?\]\(.*?\)|\|.*?\||---.*?---)', text, flags=re.DOTALL)
    
    replaced = {k: False for k in TOOLTIPS.keys()}
    
    for i in range(0, len(parts), 2):
        if not parts[i].strip():
            continue
        for pattern, replacement in TOOLTIPS.items():
            # Replace only if not yet replaced
            if not replaced[pattern]:
                if re.search(pattern, parts[i]):
                    parts[i] = re.sub(pattern, replacement, parts[i], count=1)
                    replaced[pattern] = True
                    
    with open(filename, 'w') as f:
        f.write(''.join(parts))

for fn in ['posts-source/attention-is-all-you-need-kv-cache-gqa.md', 'posts-source/mla-article.md']:
    process_file(fn)
    print(f"Processed {fn}")
