// GitHub API 연동: 내(저자)가 올린 PR 목록 + 각 PR head 커밋의 CI 결합 상태.
// 참고 스펙: docs/superpowers/specs/2026-08-16-github-pr-status-design.md

export interface GitHubPrRow {
  repo: string;           // 'owner/repo'
  pr_number: number;
  title: string;
  url: string;
  state: 'open' | 'closed';
  merged: boolean;
  head_sha: string | null;
  ci_combined: string | null;
  authored_at: string | null;  // PR 생성 시각
  updated_at: string;          // PR 마지막 갱신 시각 (걸러낼 때 기준)
}

interface SearchPrItem {
  number: number;
  title: string;
  html_url: string;
  state: string;
  created_at: string;
  updated_at: string;
  repository_url: string;
  // /search/issues는 PR 항목의 머지 여부를 최상위가 아닌 pull_request.merged_at로 준다.
  pull_request?: { merged_at: string | null } | null;
}

interface PrDetail {
  state: string;
  merged: boolean;
  head: { sha: string };
}

interface CombinedStatus {
  state: string; // success | failure | pending
}

/** Search API 상세 글자 수 제한(기본 100자)에 걸린 PR은 일부만 잘라 저장. */
function truncate(s: string, n = 100): string {
  return s.length <= n ? s : `${s.slice(0, n - 1)}…`;
}

/**
 * 내가 올린 모든 PR을 검색 API로 조회한다.
 * 검색 API는 인증 시 30 req/min. 토큰이 없으면 10 req/min이라 작업에 부적합.
 */
export async function fetchMyPrs(username: string, token: string): Promise<GitHubPrRow[]> {
  const url = `https://api.github.com/search/issues?q=author:${encodeURIComponent(
    username
  )}+type:pr&per_page=50&sort=updated&order=desc`;

  const res = await fetch(url, {
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'User-Agent': 'tech-blog-worker',
    },
  });

  if (!res.ok) {
    // 비공개 repo에 토큰 권한이 없으면 403/404가 날 수 있지만, 공개 search는 대부분 200.
    throw new Error(`GitHub search failed: ${res.status}`);
  }

  const data = (await res.json()) as { items?: SearchPrItem[] };

  // Search API에는 head sha가 없으므로, 각 PR의 상세(/pulls/{number})를 조회해
  // merged + head.sha를 확정한다. 수동 refresh라 1회성이고, 컨커런시로 묶는다.
  const items = data.items ?? [];
  const details = await fetchPrDetails(items, token);

  return items.map((item) => {
    const detail = details.get(item.number);
    return {
      repo: (item.repository_url ?? '').replace('https://api.github.com/repos/', ''),
      pr_number: item.number,
      title: truncate(item.title),
      url: item.html_url,
      state: detail?.state === 'closed' ? 'closed' : 'open',
      merged: detail?.merged ?? Boolean(item.pull_request?.merged_at),
      head_sha: detail?.head?.sha ?? null,
      ci_combined: null, // 아래에서 head 커밋 status로 채운다
      authored_at: item.created_at ?? null,
      updated_at: item.updated_at ?? item.created_at,
    };
  });
}

/** 각 PR 상세를 조회해 merged/head.sha를 확정한다. */
export async function fetchPrDetails(
  items: SearchPrItem[],
  token: string,
  concurrency = 5
): Promise<Map<number, PrDetail>> {
  const result = new Map<number, PrDetail>();

  async function worker(queue: SearchPrItem[]) {
    while (queue.length) {
      const item = queue.shift()!;
      const repo = (item.repository_url ?? '').replace('https://api.github.com/repos/', '');
      // encodeURIComponent를 쓰면 repo의 '/'가 %2F로 인코딩되어 경로가 깨짐(404).
      // repo는 'owner/repo' 형태로 신뢰되므로 그대로 쓴다.
      const url = `https://api.github.com/repos/${repo}/pulls/${item.number}`;
      try {
        const res = await fetch(url, {
          headers: {
            Accept: 'application/vnd.github+json',
            Authorization: `Bearer ${token}`,
            'User-Agent': 'tech-blog-worker',
          },
        });
        if (res.ok) {
          const detail = (await res.json()) as PrDetail;
          result.set(item.number, detail);
        }
      } catch {
        // 상세 조회 실패 시 merged/head는 fallback 값 유지.
      }
    }
  }

  const chunks: SearchPrItem[][] = [];
  for (let i = 0; i < items.length; i += concurrency) {
    chunks.push(items.slice(i, i + concurrency));
  }
  await Promise.all(chunks.map((chunk) => worker(chunk)));

  return result;
}

/**
 * 각 PR의 head 커밋 결합 CI 상태를 조회한다. 병렬로 호출하되 GitHub 제한을 피하기
 * 위해 최대 동시 5개로 묶는다. 상태 API는 토큰 시 5000 req/h라 여유가 있다.
 */
export async function fetchPrCheckRuns(
  rows: GitHubPrRow[],
  token: string,
  concurrency = 5
): Promise<Map<string, string>> {
  const result = new Map<string, string>();

  async function worker(queue: GitHubPrRow[]) {
    while (queue.length) {
      const pr = queue.shift()!;
      if (!pr.head_sha) continue;
      // repo의 '/'를 인코딩하지 않는다 (경로 구분자 유지). head_sha는 hex라 인코딩해도 무해.
      const url = `https://api.github.com/repos/${pr.repo}/commits/${encodeURIComponent(
        pr.head_sha
      )}/status`;
      try {
        const res = await fetch(url, {
          headers: {
            Accept: 'application/vnd.github+json',
            Authorization: `Bearer ${token}`,
            'User-Agent': 'tech-blog-worker',
          },
        });
        if (res.ok) {
          const data = (await res.json()) as CombinedStatus;
          result.set(`${pr.repo}#${pr.pr_number}`, data.state);
        }
      } catch {
        // CI 조회 실패는 목록을 막지 않는다 — null로 남겨두면 "없음" 표시.
      }
    }
  }

  // concurrency 청크로 나눠 병렬 실행
  const chunks: GitHubPrRow[][] = [];
  for (let i = 0; i < rows.length; i += concurrency) {
    chunks.push(rows.slice(i, i + concurrency));
  }
  await Promise.all(chunks.map((chunk) => worker(chunk)));

  return result;
}
