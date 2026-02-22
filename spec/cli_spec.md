# CLI Specifications
This is intended to match across implementations

## Command Format

E.g.
``` bash
dice-lab --rolls <int> --sides <int> --seed <int> --output <format> 
```

# Required Arguments
- `--rolls`: integer > 0

# Optional Arguments
- `--sides`: integer, default = 6
- `--seed`: integer, optional
- `--format`: json | text | csv
- `parallel`: boolean

# Error Handling Rules
- Invalid integers -> exit with non-zero code
- Rolls < 1 -> Error
- Sides < 2 -> Error
