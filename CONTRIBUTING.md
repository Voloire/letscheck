# Contributing

Thanks for taking a look. Keep changes focused, run the relevant tests, and open a pull request against `main`.

The app is intentionally local and experimental. Avoid adding network calls to runtime code, credentials, private conversation data, or generated environment files. User-facing copy uses friendly US English.

Before opening a PR:

```bash
python -m pytest -q
```

Explain the user-visible behavior and the checks you ran in the PR description.
