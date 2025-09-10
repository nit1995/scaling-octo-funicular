
# PyPSA-India-Datacenters

Reproducible PyPSA study to assess **cost**, **carbon intensity**, and **siting** implications of new datacenter (DC) loads on the Indian grid.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp config/config.example.yaml config/config.yaml

# Optional: place a PyPSA-Earth India network at the configured `network_path`
# Otherwise a synthetic India-like network will be created for testing.

make build
make solve
make plots
```

Results will be in `data/results/`.
