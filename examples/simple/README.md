# Simple Example

Complete working example with `User` and `Post` models (list, detail, create,
edit, and delete views with pagination).

```bash
# Run the example
uvicorn examples.simple.main:app --port 5000

# Seed sample data
curl -X POST http://localhost:5000/seed

# Visit admin interface
open http://localhost:5000/admin/
```
