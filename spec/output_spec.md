# Output Specifications
Defines output format and ensures benchmark comparisons aren't polluted by formatting differences.

## Text Output Format
- Header
- Total rolls
- Distribution table
- Summary stats

## Ordering
Sorted by dice face value ascending (1, 2, ... , n)

## JSON Output Formatting

```json
{
  total_rolls: int,
  sides: int,
  distribution: {
    "1": int,
    "2": int,
    ...
  },
  mean: float,
  variance: float,
  std_dev: float
}
```

## CSV Output Formatting
Includes a header row

Columns:
- face
- count
- percentage


## Text Output Formatting
Pipe (|) delimited text file

Each row in the text file should contain:
face | count | percentage