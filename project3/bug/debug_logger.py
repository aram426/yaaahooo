# Dummy DebugLogger to make otherTeam.py work
class DebugLogger:
    def __init__(self, name, echo=False):
        self.name = name
        self.echo = echo

    def step(self):
        pass

    def log(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warn(self, *args, **kwargs):
        pass

    def action(self, *args, **kwargs):
        pass
