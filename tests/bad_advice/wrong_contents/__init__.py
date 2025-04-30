from advice_animal import BaseCheck


class Check(BaseCheck):
    def run(self):
        """This is a broken advice: it puts the wrong contents in the file."""
        p = (self.env.path / "README.txt")
        p.write_text("Wrong\n")
        return True
