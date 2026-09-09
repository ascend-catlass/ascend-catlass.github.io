# Ascend CATLASS Python package index

This repository publishes the organization website and a static PEP 503 package
index backed by Wheel assets from `ascend-catlass/actions` releases.

```bash
python -m pip install \
  --pre \
  --extra-index-url https://ascend-catlass.github.io/simple/ \
  ascend-catlass-dsl
```

The index is regenerated every 15 minutes and can also be deployed manually from
the **Deploy Python package index** workflow. Only non-draft
`ascend_catlass_dsl-*.whl` assets with a GitHub-provided SHA256 digest are
published.

The site contains no Wheel binaries. Download links point to GitHub Release
assets, and each Simple API link carries its SHA256 hash.
