export interface PostRow {
  id: string;
  slug: string;
  title: string;
  content_md: string;
  excerpt: string | null;
  source_type: string;
  source_ref: string | null;
  status: string;
  tags: string | null;
  cover_image_key: string | null;
  created_at: string;
  published_at: string | null;
}
