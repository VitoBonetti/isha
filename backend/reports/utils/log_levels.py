import logging


def set_log_level(log_level):
    log_level_map = {
        'info': logging.INFO,
        'debug': logging.DEBUG,
        'error': logging.ERROR
    }

    logging.basicConfig(level=log_level_map[log_level])
