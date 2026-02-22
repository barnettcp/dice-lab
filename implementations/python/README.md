# Python Implementation

This is the baseline Python implementation of DiceLab.

## Current Scope

- Fully supports required `--rolls`
- Supports optional `--sides`, `--seed`, and `--format`
- Produces `text`, `json`, and `csv` output
- Uses deterministic behavior when `--seed` is provided
- Returns standardized exit codes:
  - `0` success
  - `1` invalid input / CLI errors
  - `2` internal execution error

`--parallel` is currently recognized but intentionally returns a clear error until a parallel version is added.

## Run Examples

```bash
python implementations/python/dice_lab.py --rolls 10000
python implementations/python/dice_lab.py --rolls 10000 --seed 42 --format json
python implementations/python/dice_lab.py --rolls 10000 --sides 20 --format csv
```

## Learning Notes

- The implementation uses a local `random.Random(seed)` instance for reproducibility.
- Statistics are computed during simulation (streaming aggregation) to avoid storing all rolls.
- Output distribution is always sorted by face to keep ordering deterministic.
