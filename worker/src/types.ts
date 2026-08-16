export type PostStatus = 'draft' | 'in_review' | 'published' | 'rejected';
export type SourceType = 'manual' | 'commit' | 'paper';

/** posts 테이블 전체 컬럼 (마이그레이션 0001_posts.sql과 1:1). */
export interface PostRow {
  id: string;
  slug: string;
  title: string;
  content_md: string;
  excerpt: string | null;
  source_type: SourceType;
  source_ref: string | null;
  status: PostStatus;
  tags: string | null;
  cover_image_key: string | null;
  created_at: string;
  published_at: string | null;
}

/** 목록/RSS 조회용 — 무거운 content_md를 실어 나르지 않는다. */
export interface PostSummary {
  id: string;
  slug: string;
  title: string;
  excerpt: string | null;
  tags: string | null;
  cover_image_key: string | null;
  published_at: string | null;
}

/** 단건 조회용 — 렌더링에 필요한 컬럼만. */
export interface PostDetail {
  id: string;
  slug: string;
  title: string;
  content_md: string;
  excerpt: string | null;
  source_ref: string | null;
  tags: string | null;
  cover_image_key: string | null;
  published_at: string | null;
}
