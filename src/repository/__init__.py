"""
Repository (data access) package.

Each module exposes a repository class that encapsulates all SQL for one
aggregate root.  Repositories are the only layer that touches the database
directly; the API layer must go through them rather than writing raw queries.

Modules:
  company_repository   — queries against the company dimension
  snapshot_repository  — queries against the snapshot fact table
  upload_repository    — queries against the upload audit table
"""
