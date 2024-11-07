from advice_animal import BaseCheck, FixConfidence

class Check(BaseCheck):
    order = 10
    def run(self):
        p = (self.env.path / "README.txt")
        cur = p.read_text()
        new = cur.upper()
        p.write_text(new)
        return cur != new
