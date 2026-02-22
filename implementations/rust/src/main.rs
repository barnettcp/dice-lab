use clap::error::ErrorKind;
use clap::{Parser, ValueEnum};
use rand::distributions::{Distribution, Uniform};
use rand::rngs::StdRng;
use rand::SeedableRng;
use std::fmt::Write;
use std::process::ExitCode;

// This enum limits accepted --format values to exactly the three spec options.
#[derive(Copy, Clone, Debug, ValueEnum)]
enum OutputFormat {
    Text,
    Json,
    Csv,
}

// Clap derives a full CLI parser (including --help) from this struct.
#[derive(Debug, Parser)]
#[command(name = "dice-lab")]
#[command(about = "Simulate dice rolls and report distribution + statistics.")]
struct Cli {
    // Required by spec.
    #[arg(long)]
    rolls: i64,

    // Optional with default 6.
    #[arg(long, default_value_t = 6)]
    sides: i64,

    // Optional deterministic seed.
    #[arg(long)]
    seed: Option<u64>,

    // Optional output format.
    #[arg(long, value_enum, default_value_t = OutputFormat::Text)]
    format: OutputFormat,

    // Optional parallel flag; currently unsupported in baseline.
    #[arg(long)]
    parallel: bool,
}

// Once validated, we convert values to usize/u64 for efficient indexing and RNG setup.
#[derive(Debug)]
struct ValidatedCli {
    rolls: usize,
    sides: usize,
    seed: Option<u64>,
    format: OutputFormat,
    parallel: bool,
}

#[derive(Debug)]
struct SimulationResult {
    total_rolls: usize,
    sides: usize,
    distribution: Vec<usize>,
    mean: f64,
    variance: f64,
    std_dev: f64,
}

fn validate(cli: Cli) -> Result<ValidatedCli, String> {
    if cli.rolls <= 0 {
        return Err("--rolls must be greater than 0.".to_string());
    }
    if cli.sides < 2 {
        return Err("--sides must be greater than or equal to 2.".to_string());
    }
    if cli.parallel {
        return Err("--parallel is not supported yet in Rust baseline.".to_string());
    }

    Ok(ValidatedCli {
        rolls: cli.rolls as usize,
        sides: cli.sides as usize,
        seed: cli.seed,
        format: cli.format,
        parallel: cli.parallel,
    })
}

fn run_simulation(options: &ValidatedCli) -> SimulationResult {
    // Create RNG:
    // - seeded => deterministic output for same args in this implementation
    // - unseeded => system entropy
    let mut rng = match options.seed {
        Some(seed) => StdRng::seed_from_u64(seed),
        None => StdRng::from_entropy(),
    };

    // Uniform distribution across [1, sides] inclusive.
    let die = Uniform::from(1..=options.sides);

    // distribution[0] is face 1, distribution[1] is face 2, etc.
    let mut counts = vec![0usize; options.sides];

    // Streaming aggregates avoid storing all individual rolls.
    let mut total = 0.0_f64;
    let mut total_sq = 0.0_f64;

    for _ in 0..options.rolls {
        let value = die.sample(&mut rng);
        counts[value - 1] += 1;
        let as_f64 = value as f64;
        total += as_f64;
        total_sq += as_f64 * as_f64;
    }

    let mean = total / options.rolls as f64;
    let mut variance = (total_sq / options.rolls as f64) - (mean * mean);
    if variance < 0.0 {
        // Floating-point math can produce tiny negative values around zero.
        variance = 0.0;
    }
    let std_dev = variance.sqrt();

    SimulationResult {
        total_rolls: options.rolls,
        sides: options.sides,
        distribution: counts,
        mean,
        variance,
        std_dev,
    }
}

fn format_text(result: &SimulationResult) -> String {
    let mut out = String::new();
    let _ = writeln!(out, "DiceLab Results");
    let _ = writeln!(out, "Total rolls: {}", result.total_rolls);
    let _ = writeln!(out, "Sides: {}", result.sides);
    let _ = writeln!(out, "Distribution");
    let _ = writeln!(out, "face | count | percentage");

    for face in 1..=result.sides {
        let count = result.distribution[face - 1];
        let pct = (count as f64 / result.total_rolls as f64) * 100.0;
        let _ = writeln!(out, "{} | {} | {:.4}", face, count, pct);
    }

    let _ = writeln!(out);
    let _ = writeln!(out, "Summary Statistics");
    let _ = writeln!(out, "Mean: {:.6}", result.mean);
    let _ = writeln!(out, "Variance: {:.6}", result.variance);
    let _ = write!(out, "Std Dev: {:.6}", result.std_dev);
    out
}

fn format_json(result: &SimulationResult) -> String {
    let mut out = String::new();
    let _ = writeln!(out, "{{");
    let _ = writeln!(out, "  \"total_rolls\": {},", result.total_rolls);
    let _ = writeln!(out, "  \"sides\": {},", result.sides);
    let _ = writeln!(out, "  \"distribution\": {{");

    for face in 1..=result.sides {
        let count = result.distribution[face - 1];
        let trailing = if face == result.sides { "" } else { "," };
        let _ = writeln!(out, "    \"{}\": {}{}", face, count, trailing);
    }

    let _ = writeln!(out, "  }},");
    let _ = writeln!(out, "  \"mean\": {:.6},", result.mean);
    let _ = writeln!(out, "  \"variance\": {:.6},", result.variance);
    let _ = writeln!(out, "  \"std_dev\": {:.6}", result.std_dev);
    let _ = write!(out, "}}");
    out
}

fn format_csv(result: &SimulationResult) -> String {
    let mut out = String::new();
    let _ = writeln!(out, "face,count,percentage");

    for face in 1..=result.sides {
        let count = result.distribution[face - 1];
        let pct = (count as f64 / result.total_rolls as f64) * 100.0;
        let _ = writeln!(out, "{},{},{:.4}", face, count, pct);
    }

    let _ = writeln!(out);
    let _ = writeln!(out, "summary_metric,value");
    let _ = writeln!(out, "total_rolls,{}", result.total_rolls);
    let _ = writeln!(out, "sides,{}", result.sides);
    let _ = writeln!(out, "mean,{:.6}", result.mean);
    let _ = writeln!(out, "variance,{:.6}", result.variance);
    let _ = write!(out, "std_dev,{:.6}", result.std_dev);
    out
}

fn render_output(result: &SimulationResult, format: OutputFormat) -> String {
    match format {
        OutputFormat::Text => format_text(result),
        OutputFormat::Json => format_json(result),
        OutputFormat::Csv => format_csv(result),
    }
}

fn run(cli: Cli) -> Result<(), String> {
    let options = validate(cli)?;

    // Keep this read so it's obvious in code review that the flag is intentionally
    // unsupported for baseline behavior, not accidentally ignored.
    let _parallel_requested = options.parallel;

    let result = run_simulation(&options);
    println!("{}", render_output(&result, options.format));
    Ok(())
}

fn main() -> ExitCode {
    let outcome = std::panic::catch_unwind(|| {
        let cli = match Cli::try_parse() {
            Ok(parsed) => parsed,
            Err(error) => {
                if error.kind() == ErrorKind::DisplayHelp {
                    print!("{}", error.render().to_string());
                    return ExitCode::from(0);
                }
                eprintln!("Input error: {}", error.render().to_string().trim());
                return ExitCode::from(1);
            }
        };

        match run(cli) {
            Ok(()) => ExitCode::from(0),
            Err(message) => {
                eprintln!("Input error: {}", message);
                ExitCode::from(1)
            }
        }
    });

    match outcome {
        Ok(code) => code,
        Err(_) => {
            eprintln!("Internal error: unexpected panic occurred.");
            ExitCode::from(2)
        }
    }
}
