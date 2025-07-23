import logging

logger = logging.getLogger("appLogger")

def log_attempt_number(retry_state):
    """Log retry attempt details: function name, exception, attempt number."""
    fn = retry_state.fn.__name__
    attempt = retry_state.attempt_number
    exception = retry_state.outcome.exception() if retry_state.outcome and retry_state.outcome.failed else None

    logger.info(f"Attempt #{attempt} for function '{fn}'")
    if exception:
        logger.error(f"Function {fn} raised exception: {type(exception).__name__}: {exception}")