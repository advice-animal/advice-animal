from advice_animal import BaseCheck


class Check(BaseCheck):
    def run(self):
        """This is a broken advice: it makes a file it shouldn't have."""
        p = (self.env.path / "extra_file.txt")
        p.write_text("I shouldn't be here\n")
        return True
