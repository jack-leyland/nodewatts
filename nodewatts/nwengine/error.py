class EngineError(Exception):
    def __init__(self, msg, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)
