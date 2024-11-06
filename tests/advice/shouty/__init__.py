from advice_animal import BaseCheck, FixConfidence

import central_lib  # ensure that project imports work
assert central_lib

class Check(BaseCheck):
    order = 10
    def run(self):
        p = (self.env.path / "README.txt")
        cur = p.read_text()
        new = cur.upper()
        p.write_text(new)
        return cur != new
