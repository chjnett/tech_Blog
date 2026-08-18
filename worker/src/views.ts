// 조회수 카운터 + 인기글 랭킹 (Cloudflare KV).
//
// 이 모듈은 "Redis라면 INCR/ZINCRBY로 원자적 카운터·랭킹이 되는 걸,
// KV에선 왜 못 하나"를 직접 체험하게 하는 학습 목적 구현이다.
// Cloudflare KV 키-값은 원자적 증감(INCR) 메서드가 없어서 read-modify-write가
// 되고, KV는 강한 일관성이 아니므로 스트레스 하에 카운터를 잃을 수 있다.
// (→ Redis의 INCR이 원자적이라는 것의 가치를 코드로 확인)
export interface ViewCount {
  views: number;
  updatedAt: string;
}

const VIEW_PREFIX = 'views:';

/** 조회수 증가 (best-effort read-modify-write; KV는 INCR 없음). */
export async function incrementViews(kv: KVNamespace, slug: string): Promise<number> {
  const key = VIEW_PREFIX + slug;
  const prev = await kv.get(key, 'json').catch(() => null) as ViewCount | null;
  const next = {
    views: (prev?.views ?? 0) + 1,
    updatedAt: new Date().toISOString(),
  };
  await kv.put(key, JSON.stringify(next));
  return next.views;
}

/** 조회수 조회 (0 기본값). */
export async function getViews(kv: KVNamespace, slug: string): Promise<number> {
  const v = await kv.get(VIEW_PREFIX + slug, 'json').catch(() => null) as ViewCount | null;
  return v?.views ?? 0;
}

// ── 인기 랭킹 (ZSet의 대략적 모사: KV엔 정렬된 순위 타입이 없다) ──
// 실제로는 조회수 기준으로 "상위 N"을 계산해야 하는데, KV는 전역 순위를 지원하지
// 않는다. 여기서는 각 글의 조회수를 읽어 클라이언트/API에서 정렬하는 방식으로
// 제공하고, 그 "KV의 한계"가 Redis ZSet과의 대비 포인트다.
export async function listPopular(kv: KVNamespace, slugs: string[]): Promise<{ slug: string; views: number }[]> {
  const items = await Promise.all(
    slugs.map(async (slug) => ({ slug, views: await getViews(kv, slug) }))
  );
  return items.sort((a, b) => b.views - a.views);
}
