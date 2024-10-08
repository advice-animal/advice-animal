import os

import advice_animal


class Check(advice_animal.BaseCheck):
    confidence = advice_animal.FixConfidence.YELLOW
    preview = True

    def run(self):
        p = self.env.path / "requirements.txt"
        if p.is_file():
            os.rename(p, p.with_suffix(".in"))
            return True
        return False
