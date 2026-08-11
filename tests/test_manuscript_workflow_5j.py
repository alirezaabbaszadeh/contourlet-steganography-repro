from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/manuscript.yml"

class ManuscriptWorkflow5JTests(unittest.TestCase):
    def test_workflow_is_final_5j_and_not_historical_archive_driven(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("agent/server-control-plane",text)
        self.assertIn("publication/**",text)
        self.assertIn("scripts/5j/build_tables.py",text)
        self.assertIn("scripts/5j/build_figures.py",text)
        self.assertNotIn("CTSteg-reproduction-capsule",text)
        self.assertNotIn("CTSteg-final-PDFB",text)
        self.assertNotIn("agent/runtime-resume-gate",text)
        self.assertNotIn("git push",text)
        self.assertIn("contents: read",text)

if __name__=="__main__": unittest.main()
