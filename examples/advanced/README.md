# Advanced Example

Demonstrates an explicit session maker, a custom `base_url` with logo,
`column_exclude_list`, view categories, and a custom stats page.

```bash
# Run the example
uvicorn examples.advanced.main:app --port 5000

# Seed sample data
curl -X POST http://localhost:5000/seed

# Visit admin interface
open http://localhost:5000/backend/
```
