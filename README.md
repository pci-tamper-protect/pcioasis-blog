# PCI Oasis Blog

Engineering content for teams building and operating PCI-compliant systems.

Published at: https://www.pcioasis.com/blog

## Structure

```
posts/
├── secure-devops/          # CI/CD, pipeline security, credential-free deployments
├── identity-and-access/    # IAM, WIF, OAuth, RBAC, zero-trust identity
├── compliance-engineering/ # PCI DSS translated into engineering practice
├── cloud-security/         # GCP/Firebase/multi-cloud configurations
├── threat-intel/           # E-skimming patterns, adversary TTPs
└── detection-and-response/ # Monitoring, alerting, incident response
```

See [CATEGORIES.md](./CATEGORIES.md) for full category descriptions and PCI requirement mappings.

## Cross-posting to planetkesten.com

Posts are automatically synced to [www.planetkesten.com/blog](https://www.planetkesten.com/blog) whenever changes to `content/posts/**` are merged to `main`.

### How it works

1. Merging a post triggers [`.github/workflows/sync-to-planetkesten.yml`](./.github/workflows/sync-to-planetkesten.yml)
2. The workflow runs [`agents/sync_blog_posts.py`](https://github.com/pci-tamper-protect/pcioasis-ops/blob/main/agents/sync_blog_posts.py) from [pcioasis-ops](https://github.com/pci-tamper-protect/pcioasis-ops)
3. The script converts each Hugo post to plain markdown (strips frontmatter, converts `{{< figure >}}` shortcodes, prefixes image paths)
4. Converted content and images are written into [planet-kesten-site](https://github.com/kbroughton/planet-kesten-site) and a PR is opened for review

The Cloudflare Worker serving planetkesten.com injects `<link rel="canonical" href="https://blog.pcioasis.com/posts/...">` into the raw HTML at the edge, so blog.pcioasis.com remains the authoritative SEO source.

### Adding a new post

No extra steps needed — write and merge as normal. The sync PR will appear on [planet-kesten-site](https://github.com/kbroughton/planet-kesten-site/pulls) automatically.

### Manual trigger

```bash
gh workflow run sync-to-planetkesten.yml \
  --repo pci-tamper-protect/pcioasis-blog \
  --ref main
```

## Post Format

Each post is a Markdown file with YAML frontmatter. Compatible with Medium import and static site generators (Hugo, Jekyll, Ghost).

Frontmatter fields:
- `title` — display title
- `slug` — URL slug
- `date` — publication date (YYYY-MM-DD)
- `category` — one of the categories above
- `tags` — array of relevant tags
- `author`
- `canonical_url` — the pcioasis.com URL (set this before cross-posting to Medium)
