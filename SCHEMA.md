# Structured Output Schema

`rdt-cli` uses a shared agent-friendly envelope for machine-readable output.

## Success

```yaml
ok: true
schema_version: "1"
data: ...
```

## Error

```yaml
ok: false
schema_version: "1"
error:
  code: not_authenticated
  message: need login
```

## Notes

- `--json` and `--yaml` both use this envelope
- non-TTY stdout defaults to YAML
- reading and search commands return their payload under `data`
- `status` returns `data.authenticated` plus `data.cookie_count`
- `whoami` returns `data.user`
- common `error.code` values include `not_authenticated`, `rate_limited`, `not_found`, `forbidden`, and `api_error`
- set `OUTPUT=yaml|json|rich|auto` environment variable to override default format
