from advice_animal import BaseCheck


class Check(BaseCheck):
    def run(self):
        """This is a broken advice: it doesn't make the file it claims to."""
        return True
