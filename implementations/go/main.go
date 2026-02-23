package main

import (
	"errors"
	"flag"
	"fmt"
	"math"
	"math/rand"
	"os"
	"strings"
	"time"
)

// CliOptions stores validated command-line options.
// Keeping this in a struct makes the rest of the program easier to reason about.
type CliOptions struct {
	Rolls    int
	Sides    int
	HasSeed  bool
	Seed     int64
	Format   string
	Parallel bool
}

// SimulationResult captures all values required by the output spec.
type SimulationResult struct {
	TotalRolls   int
	Sides        int
	Distribution []int
	Mean         float64
	Variance     float64
	StdDev       float64
}

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	options, err := parseAndValidateArgs(args)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Input error: %v\n", err)
		return 1
	}

	result := runSimulation(options)
	output, err := renderOutput(result, options.Format)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Internal error: %v\n", err)
		return 2
	}

	fmt.Println(output)
	return 0
}

func parseAndValidateArgs(args []string) (CliOptions, error) {
	// We use a custom FlagSet with ContinueOnError so we can return exit code 1
	// for parsing problems instead of the default abrupt exit behavior.
	flagSet := flag.NewFlagSet("dice-lab", flag.ContinueOnError)
	flagSet.SetOutput(os.Stderr)

	rolls := flagSet.Int("rolls", -1, "Total number of rolls (required, must be > 0)")
	sides := flagSet.Int("sides", 6, "Number of die sides (must be >= 2)")
	seed := flagSet.Int64("seed", 0, "Optional RNG seed for deterministic behavior")
	format := flagSet.String("format", "text", "Output format: text|json|csv")
	parallel := flagSet.Bool("parallel", false, "Enable parallel mode (currently unsupported)")

	flagSet.Usage = func() {
		fmt.Fprintln(os.Stdout, "Usage: dice-lab --rolls <int> [options]")
		fmt.Fprintln(os.Stdout)
		fmt.Fprintln(os.Stdout, "Required:")
		fmt.Fprintln(os.Stdout, "  --rolls <int>      Total rolls to simulate (must be > 0)")
		fmt.Fprintln(os.Stdout)
		fmt.Fprintln(os.Stdout, "Optional:")
		fmt.Fprintln(os.Stdout, "  --sides <int>      Number of sides (must be >= 2, default: 6)")
		fmt.Fprintln(os.Stdout, "  --seed <int>       Seed for deterministic pseudorandom behavior")
		fmt.Fprintln(os.Stdout, "  --format <string>  text|json|csv (default: text)")
		fmt.Fprintln(os.Stdout, "  --parallel         Recognized but unsupported in baseline")
		fmt.Fprintln(os.Stdout, "  --help             Show this help output")
		fmt.Fprintln(os.Stdout)
		fmt.Fprintln(os.Stdout, "Example:")
		fmt.Fprintln(os.Stdout, "  dice-lab --rolls 10000 --sides 20 --seed 42 --format json")
	}

	if err := flagSet.Parse(args); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			// Go's flag package uses ErrHelp when --help is requested.
			flagSet.Usage()
			os.Exit(0)
		}
		return CliOptions{}, err
	}

	if flagSet.NArg() > 0 {
		return CliOptions{}, fmt.Errorf("unexpected positional argument(s): %s", strings.Join(flagSet.Args(), " "))
	}

	if *rolls <= 0 {
		return CliOptions{}, fmt.Errorf("--rolls must be greater than 0")
	}
	if *sides < 2 {
		return CliOptions{}, fmt.Errorf("--sides must be greater than or equal to 2")
	}
	if *parallel {
		return CliOptions{}, fmt.Errorf("--parallel is not supported yet in Go baseline")
	}
	if *format != "text" && *format != "json" && *format != "csv" {
		return CliOptions{}, fmt.Errorf("--format must be one of: text, json, csv")
	}

	parsed := CliOptions{
		Rolls:    *rolls,
		Sides:    *sides,
		HasSeed:  flagSet.Lookup("seed") != nil && wasFlagProvided(args, "--seed", "-seed"),
		Seed:     *seed,
		Format:   *format,
		Parallel: *parallel,
	}

	return parsed, nil
}

// wasFlagProvided checks whether a specific flag token appeared in raw args.
// Go's standard flag package does not directly expose this information.
func wasFlagProvided(args []string, names ...string) bool {
	for _, arg := range args {
		for _, name := range names {
			if arg == name || strings.HasPrefix(arg, name+"=") {
				return true
			}
		}
	}
	return false
}

func runSimulation(options CliOptions) SimulationResult {
	// Determinism rule:
	// - with --seed: deterministic within this implementation
	// - without --seed: use time-based entropy
	var rng *rand.Rand
	if options.HasSeed {
		rng = rand.New(rand.NewSource(options.Seed))
	} else {
		rng = rand.New(rand.NewSource(time.Now().UnixNano()))
	}

	counts := make([]int, options.Sides)
	total := 0.0
	totalSquares := 0.0

	for i := 0; i < options.Rolls; i++ {
		// Intn(n) returns 0..n-1, so we shift by +1 for die faces.
		value := rng.Intn(options.Sides) + 1
		counts[value-1]++
		asFloat := float64(value)
		total += asFloat
		totalSquares += asFloat * asFloat
	}

	mean := total / float64(options.Rolls)
	variance := (totalSquares / float64(options.Rolls)) - (mean * mean)
	if variance < 0 {
		// Floating-point rounding can create tiny negatives near zero.
		variance = 0
	}

	return SimulationResult{
		TotalRolls:   options.Rolls,
		Sides:        options.Sides,
		Distribution: counts,
		Mean:         mean,
		Variance:     variance,
		StdDev:       math.Sqrt(variance),
	}
}

func renderOutput(result SimulationResult, format string) (string, error) {
	switch format {
	case "text":
		return formatText(result), nil
	case "json":
		return formatJSON(result), nil
	case "csv":
		return formatCSV(result), nil
	default:
		return "", fmt.Errorf("unsupported format: %s", format)
	}
}

func formatText(result SimulationResult) string {
	var builder strings.Builder
	builder.WriteString("DiceLab Results\n")
	builder.WriteString(fmt.Sprintf("Total rolls: %d\n", result.TotalRolls))
	builder.WriteString(fmt.Sprintf("Sides: %d\n", result.Sides))
	builder.WriteString("Distribution\n")
	builder.WriteString("face | count | percentage\n")

	for face := 1; face <= result.Sides; face++ {
		count := result.Distribution[face-1]
		pct := (float64(count) / float64(result.TotalRolls)) * 100
		builder.WriteString(fmt.Sprintf("%d | %d | %.4f\n", face, count, pct))
	}

	builder.WriteString("\nSummary Statistics\n")
	builder.WriteString(fmt.Sprintf("Mean: %.6f\n", result.Mean))
	builder.WriteString(fmt.Sprintf("Variance: %.6f\n", result.Variance))
	builder.WriteString(fmt.Sprintf("Std Dev: %.6f", result.StdDev))
	return builder.String()
}

func formatJSON(result SimulationResult) string {
	// Manual JSON writing keeps distribution key order deterministic.
	var builder strings.Builder
	builder.WriteString("{\n")
	builder.WriteString(fmt.Sprintf("  \"total_rolls\": %d,\n", result.TotalRolls))
	builder.WriteString(fmt.Sprintf("  \"sides\": %d,\n", result.Sides))
	builder.WriteString("  \"distribution\": {\n")

	for face := 1; face <= result.Sides; face++ {
		count := result.Distribution[face-1]
		comma := ","
		if face == result.Sides {
			comma = ""
		}
		builder.WriteString(fmt.Sprintf("    \"%d\": %d%s\n", face, count, comma))
	}

	builder.WriteString("  },\n")
	builder.WriteString(fmt.Sprintf("  \"mean\": %.6f,\n", result.Mean))
	builder.WriteString(fmt.Sprintf("  \"variance\": %.6f,\n", result.Variance))
	builder.WriteString(fmt.Sprintf("  \"std_dev\": %.6f\n", result.StdDev))
	builder.WriteString("}")
	return builder.String()
}

func formatCSV(result SimulationResult) string {
	var builder strings.Builder
	builder.WriteString("face,count,percentage\n")

	for face := 1; face <= result.Sides; face++ {
		count := result.Distribution[face-1]
		pct := (float64(count) / float64(result.TotalRolls)) * 100
		builder.WriteString(fmt.Sprintf("%d,%d,%.4f\n", face, count, pct))
	}

	builder.WriteString("\nsummary_metric,value\n")
	builder.WriteString(fmt.Sprintf("total_rolls,%d\n", result.TotalRolls))
	builder.WriteString(fmt.Sprintf("sides,%d\n", result.Sides))
	builder.WriteString(fmt.Sprintf("mean,%.6f\n", result.Mean))
	builder.WriteString(fmt.Sprintf("variance,%.6f\n", result.Variance))
	builder.WriteString(fmt.Sprintf("std_dev,%.6f", result.StdDev))
	return builder.String()
}
