# Building AstroChecker

The supported development path runs the Python source locally. Install runtime dependencies from `requirements.txt`, then start the server with `python run.py`.

To rebuild the bundled catalog offline:

```bash
python tools/build_catalog.py
```

The Windows packaging workflow is kept for release experiments. It creates a single executable with the project toolchain; source execution remains the clearest way to develop and troubleshoot the app.
