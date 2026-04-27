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
