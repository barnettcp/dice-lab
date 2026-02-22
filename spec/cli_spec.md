# cli_spec.md

## 1. Purpose

This document defines the command-line interface (CLI) contract for all DiceLab implementations.

All language implementations must conform to this interface specification to ensure consistency across benchmarking and comparative analysis.

If any ambiguity arises, this file is the authoritative reference for CLI behavior.


## 2. Command Format

All implementations must expose a single executable named: `dice-lab`

Invocation Pattern: `dice-lab --rolls <int> [options]`



## 3. Required Arguments

### `--rolls <int>`

- Type: Integer  
- Required: Yes  
- Constraint: Must be greater than 0  
- Description: Total number of dice rolls to simulate.

Example:
`dice-lab --rolls 10000`



## 4. Optional Arguments

### `--sides <int>`

- Type: Integer  
- Required: No  
- Default: 6  
- Constraint: Must be ≥ 2  
- Description: Number of sides on the die.

Example:
`dice-lab --rolls 10000 --sides 20`



### `--seed <int>`

- Type: Integer  
- Required: No  
- Description: Seed value for deterministic pseudorandom number generation.

Behavior:
- If provided, results must be reproducible within the same implementation.
- If omitted, system entropy may be used.

Example:
`dice-lab --rolls 10000 --seed 42`



### `--format <string>`

- Type: String  
- Required: No  
- Default: text  
- Allowed values:
  - `text`
  - `json`
  - `csv`

Description:  
Specifies output format.

Example:
`dice-lab --rolls 10000 --format json`



### `--parallel`

- Type: Boolean flag  
- Required: No  
- Default: false  
- Description: Enables parallel execution where supported.

Behavior:
- If unsupported in a language implementation, the flag must either:
  - Produce a clear error message, or
  - Be documented as unsupported.

Parallel execution must not alter statistical results.

Example:
`dice-lab --rolls 100000 --parallel`



## 5. Help Command

All implementations must support:
`dice-lab --help`


The help output must:

- List all supported flags
- Indicate required vs optional arguments
- Provide a short usage example
- Exit with status code 0



## 6. Error Handling Behavior

### Invalid Input

The program must:

- Exit with a non-zero status code
- Print a human-readable error message
- Not produce partial statistical output

### Error Conditions

The following must trigger an error:

- Missing `--rolls`
- `--rolls <= 0`
- `--sides < 2`
- Non-integer numeric input
- Unsupported format value



## 7. Exit Codes

Standardized exit codes:

- `0` — Successful execution  
- `1` — Invalid input or CLI parsing error  
- `2` — Internal execution error (optional distinction)

Implementations may expand on these but must document deviations.



## 8. Deterministic Behavior

When `--seed` is provided:

- Identical CLI arguments must produce identical output within the same implementation.
- Cross-language deterministic equality is not required.



## 9. Output Ordering Rules

For consistency across implementations:

- Distribution results must be ordered by face value ascending.
- Output must not contain nondeterministic ordering artifacts.



## 10. Benchmarking Mode Constraints

For benchmark runs:

- No debug logging
- No interactive prompts
- No progress indicators
- No additional console output beyond defined format

All implementations must remain silent except for specified output.



## 11. Non-Goals (CLI Scope)

The CLI specification does not include:

- Interactive prompts
- Real-time roll visualization
- Network access
- File-based persistence beyond explicit output modes



## 12. Future Extensions (Not Required)

Potential future CLI flags (not part of baseline spec):

- `--dice-per-roll`
- `--weighted`
- `--output-file <path>`
- `--benchmark`

These must not be implemented unless standardized across all language versions.