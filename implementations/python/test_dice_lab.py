import unittest

import dice_lab


class DiceLabTests(unittest.TestCase):
    def test_seeded_runs_are_deterministic(self) -> None:
        first = dice_lab.run_simulation(rolls=1000, sides=6, seed=42)
        second = dice_lab.run_simulation(rolls=1000, sides=6, seed=42)

        self.assertEqual(first.distribution, second.distribution)
        self.assertEqual(first.mean, second.mean)
        self.assertEqual(first.variance, second.variance)
        self.assertEqual(first.std_dev, second.std_dev)

    def test_distribution_keys_cover_all_faces(self) -> None:
        result = dice_lab.run_simulation(rolls=50, sides=20, seed=7)
        self.assertEqual(sorted(result.distribution.keys()), list(range(1, 21)))

    def test_json_distribution_ordering_is_ascending(self) -> None:
        result = dice_lab.run_simulation(rolls=100, sides=6, seed=12)
        payload = dice_lab.format_json(result)

        first_index = payload.find('"1"')
        second_index = payload.find('"2"')
        sixth_index = payload.find('"6"')
        self.assertTrue(first_index < second_index < sixth_index)

    def test_invalid_rolls_returns_exit_code_1(self) -> None:
        code = dice_lab.main(["--rolls", "0"])
        self.assertEqual(code, 1)

    def test_unsupported_parallel_returns_exit_code_1(self) -> None:
        code = dice_lab.main(["--rolls", "10", "--parallel"])
        self.assertEqual(code, 1)

    def test_text_output_has_summary_statistics_section(self) -> None:
        result = dice_lab.run_simulation(rolls=25, sides=6, seed=5)
        output = dice_lab.format_text(result)
        self.assertIn("Summary Statistics", output)

    def test_csv_output_has_separated_summary_block(self) -> None:
        result = dice_lab.run_simulation(rolls=25, sides=6, seed=5)
        output = dice_lab.format_csv(result)
        self.assertIn("summary_metric,value", output)


if __name__ == "__main__":
    unittest.main()
