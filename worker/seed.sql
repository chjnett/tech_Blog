INSERT INTO posts (id, slug, title, content_md, excerpt, source_type, source_ref, status, tags, cover_image_key, created_at, published_at)
VALUES
  (
    '11111111-1111-1111-1111-111111111111',
    'hello-world',
    'Hello World',
    '# Hello

This is the **first** post.

- one
- two',
    'The first post on this blog.',
    'manual',
    NULL,
    'published',
    '["intro"]',
    NULL,
    '2026-08-01T00:00:00Z',
    '2026-08-01T00:00:00Z'
  ),
  (
    '22222222-2222-2222-2222-222222222222',
    'second-post',
    'Second Post',
    '## Section

Some [link](https://example.com) and more text.',
    'A second sample post.',
    'manual',
    NULL,
    'published',
    '["notes"]',
    NULL,
    '2026-08-02T00:00:00Z',
    '2026-08-02T00:00:00Z'
  ),
  (
    '33333333-3333-3333-3333-333333333333',
    'draft-only',
    'Draft Only',
    'Should never appear publicly.',
    'Draft excerpt.',
    'manual',
    NULL,
    'draft',
    '[]',
    NULL,
    '2026-08-02T00:00:00Z',
    NULL
  ),
  (
    '44444444-4444-4444-4444-444444444444',
    'code-terminal-demo',
    'Code + Terminal Demo',
    '# Code + Terminal Demo

Testing syntax highlighting.

```python
# multiply two numbers
def multiply(a, b):
    return a * b
```

```terminal
$ python demo.py
result: 42
```',
    'Demo post exercising code and terminal blocks.',
    'manual',
    NULL,
    'published',
    '["demo"]',
    NULL,
    '2026-08-03T00:00:00Z',
    '2026-08-03T00:00:00Z'
  );
