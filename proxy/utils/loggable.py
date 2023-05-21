import logging


class Loggable:
    """Auto add logger based on class name."""

    logger: logging.Logger

    def __init_subclass__(cls, **kwargs):
        cls.logger = logging.getLogger(cls.__name__)
        super().__init_subclass__(**kwargs)

    def __init__(self, **kwargs):
        for k in kwargs:
            self.logger.debug('unused kwarg: %s', k)
