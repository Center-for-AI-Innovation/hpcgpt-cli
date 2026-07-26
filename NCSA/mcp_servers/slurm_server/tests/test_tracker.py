import json
import sys
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from src.tracker import SlurmTracker  # noqa: E402


FIXTURES = Path(__file__).parent / "fixtures"


class FixtureRunner:
    def __init__(self):
        self.commands = []
        self.squeue = (FIXTURES / "squeue.json").read_text()
        self.sacct = (FIXTURES / "sacct.json").read_text()

    def __call__(self, command):
        self.commands.append(command)
        if command[0] == "squeue":
            return self.squeue
        if command[0] == "sacct":
            return self.sacct
        raise AssertionError(f"unexpected command: {command}")


class SlurmTrackerTests(unittest.TestCase):
    def setUp(self):
        self.runner = FixtureRunner()
        self.tracker = SlurmTracker(identity_mode="explicit", runner=self.runner)

    def test_list_merges_active_and_history_without_duplicates(self):
        result = self.tracker.list_jobs("student1", since="7d")

        self.assertEqual(
            [job["job_id"] for job in result["jobs"]],
            ["41001", "40999", "39998_3"],
        )
        self.assertEqual(result["active_count"], 1)
        self.assertEqual(result["jobs"][0]["source"], "squeue")
        self.assertEqual(result["jobs"][0]["resources"]["gres/gpu"], 1)
        self.assertEqual(
            self.runner.commands[1],
            ["sacct", "-X", "--json", "-u", "student1", "-S", "now-7days"],
        )

    def test_list_filters_states(self):
        result = self.tracker.list_jobs("student1", states=["completed"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["jobs"][0]["job_id"], "40999")

    def test_get_job_prefers_active_record(self):
        result = self.tracker.get_job("41001", "student1")
        self.assertEqual(result["job"]["source"], "squeue")
        self.assertEqual(result["job"]["state"], "RUNNING")

    def test_get_usage_returns_step_metrics(self):
        result = self.tracker.get_job_usage("40999", "student1")
        self.assertEqual(result["steps"][0]["step_id"], "40999.batch")
        self.assertEqual(result["steps"][0]["maximum"]["mem"], 1024)

    def test_normalizes_array_task_ids(self):
        result = self.tracker.get_job("39998_3", "student1")
        self.assertEqual(result["job"]["job_id"], "39998_3")

    def test_rejects_unsafe_identifiers_and_lookbacks(self):
        with self.assertRaises(ValueError):
            self.tracker.get_job("41001;rm -rf /", "student1")
        with self.assertRaises(ValueError):
            self.tracker.list_jobs("student1", since="yesterday")
        with self.assertRaises(ValueError):
            self.tracker.list_jobs("student1", since="91d")
        with self.assertRaises(ValueError):
            self.tracker.list_jobs("student1;id")

    def test_fixture_is_valid_json(self):
        self.assertIn("jobs", json.loads(self.runner.squeue))
        self.assertIn("jobs", json.loads(self.runner.sacct))


if __name__ == "__main__":
    unittest.main()
