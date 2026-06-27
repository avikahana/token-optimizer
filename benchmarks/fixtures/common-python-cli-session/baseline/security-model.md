# Security Model Excerpt

Safety warning: no default network calls, daemons, raw transcript capture, raw
file-content persistence, or raw tool-output persistence in MVP.

Commands must be local-first and project-scoped. Hook behavior must be
dry-run inspectable before writes.
