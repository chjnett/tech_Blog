// 홈 PR 섹션: /api/prs(조회) + /api/prs/refresh(관리자 갱신) + /api/prs/link(기여글 연결).
// 스펙: docs/superpowers/specs/2026-08-16-github-pr-status-design.md
import { listPrs, getPrLastUpdated, upsertPrs, setPrPostSlug } from '../db';
import { fetchMyPrs, fetchPrCheckRuns } from '../github';
import { isAuthorized } from './admin';

export const GITHUB_USERNAME = 'chjnett';

// 검색/status API는 인증 시 제한이 넉넉하지만, 그렇다 해도 홈 새로고침마다
// GitHub를 직접 때리지 않도록 항상 D1 캐시를 읽는다. 갱신은 refresh로만.
export async function handleListPrs(db: D1Database): Promise<Response> {
  const [rows, lastUpdated] = await Promise.all([listPrs(db), getPrLastUpdated(db)]);

  const openCount = rows.filter((r) => r.state === 'open').length;
  const mergedCount = rows.filter((r) => r.merged).length;
  const failureCount = rows.filter((r) => r.ci_combined === 'failure').length;

  return Response.json({
    count: rows.length,
    open: openCount,
    merged: mergedCount,
    // 열린 PR 중 CI 실패한 것만 강조 (머지된 건 CI 무의미)
    failures: failureCount,
    last_updated: lastUpdated,
    items: rows,
  });
}

export async function handleRefreshPrs(
  request: Request,
  db: D1Database,
  githubToken: string | undefined
): Promise<Response> {
  // 관리자 토큰(GITHUB_TOKEN)과 같은 값으로 인증. 열러드는 정책상 잠긴다(401).
  if (!(await isAuthorized(request, githubToken))) {
    return Response.json({ error: 'unauthorized' }, { status: 401 });
  }
  if (!githubToken) {
    return Response.json({ error: 'missing GITHUB_TOKEN' }, { status: 500 });
  }

  try {
    const prs = await fetchMyPrs(GITHUB_USERNAME, githubToken);
    const ci = await fetchPrCheckRuns(prs, githubToken);
    for (const pr of prs) {
      pr.ci_combined = ci.get(`${pr.repo}#${pr.pr_number}`) ?? null;
    }
    await upsertPrs(db, prs);
    return Response.json({ success: true, count: prs.length });
  } catch (err) {
    console.error('PR refresh error:', err);
    return Response.json({ error: 'refresh failed' }, { status: 500 });
  }
}

/**
 * PR에 기여 상세 글(oss-* slug)을 연결한다. 관리자 인증(ADMIN_TOKEN) 필요.
 * body: { repo, pr_number, post_slug }
 * post_slug가 null/'' 이면 연결 해제.
 */
export async function handleLinkPrPost(
  request: Request,
  db: D1Database,
  adminToken: string | undefined
): Promise<Response> {
  if (!(await isAuthorized(request, adminToken))) {
    return Response.json({ error: 'unauthorized' }, { status: 401 });
  }
  const body = (await request.json().catch(() => null)) as
    | { repo?: string; pr_number?: number; post_slug?: string | null }
    | null;
  if (!body || !body.repo || !body.pr_number) {
    return Response.json({ error: 'missing repo/pr_number' }, { status: 400 });
  }
  const postSlug = body.post_slug?.trim() || null;
  await setPrPostSlug(db, body.repo, body.pr_number, postSlug);
  return Response.json({
    success: true,
    repo: body.repo,
    pr_number: body.pr_number,
    post_slug: postSlug,
  });
}
