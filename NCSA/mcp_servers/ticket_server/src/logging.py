import os
import sys
import logging


ANSI_CODES = {
    'red': "\x1b[31;20m",
    'bold_red': "\x1b[31;1m",
    'green': "\x1b[32;20m",
    'yellow': "\x1b[33;20m",
    'bold_yellow': "\x1b[33;1m",
    'blue': "\x1b[34;20m",
    'magenta': "\x1b[35;20m",
    'cyan': "\x1b[36;20m",
    'white': "\x1b[37;20m",
    'grey': "\x1b[38;20m",
    'reset': "\x1b[0m",
}


class ColoredConsoleFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: ANSI_CODES['cyan'],
        logging.INFO: ANSI_CODES['green'],
        logging.WARNING: ANSI_CODES['yellow'],
        logging.ERROR: ANSI_CODES['red'],
        logging.CRITICAL: ANSI_CODES['bold_red'],
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno)
        record.levelname = color + record.levelname + ANSI_CODES['reset']
        if record.levelno >= logging.WARNING:
            record.msg = color + record.msg + ANSI_CODES['reset']
        return logging.Formatter.format(self, record)


def setup_logging(filepath: str, log_level: int = logging.INFO, console_log_level: int = None, use_color: bool = True, writemode: str = 'a') -> logging.Logger:
    """
    Setup logging to file and console.
    Args:
        filepath: The path to the log file.
        log_level: The level to log at.
        console_log_level: The level to log to the console at. If None, console logging is turned off.
        use_color: Whether to use color in the console output.
        writemode: The mode to write the log file in.
    Returns:
        The logger.
    """
    log = logging.getLogger()
    
    dirname = os.path.dirname(filepath)
    if not os.path.exists(dirname) and dirname != '':
        os.makedirs(os.path.dirname(filepath))


    if os.path.exists(filepath) and os.path.splitext(os.path.basename(filepath.lower()))[0] == 'latest':
        if not os.stat(filepath).st_size == 0:
            with open(filepath) as fh:
                newfilename = '{}_{}.log'.format(*(fh.readline().split(' ')[0:2]))
                newfilename = newfilename.replace('/', '-').replace(':', '-')
            os.rename(filepath, os.path.join(dirname, newfilename))
    lineformat = '%(asctime)s %(levelname)s - %(message)s'
    file_formatter = logging.Formatter(lineformat, datefmt='%d/%m/%Y %H:%M:%S')
    if use_color:
        stream_formatter = ColoredConsoleFormatter(lineformat, datefmt='%d/%m/%Y %H:%M:%S')
    else:
        stream_formatter = file_formatter
    file_handler = logging.FileHandler(filepath, mode=writemode)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(log_level)
    log.addHandler(file_handler)
    if console_log_level is not None:
        stream_handler = logging.StreamHandler(stream=sys.stdout)
        stream_handler.setFormatter(stream_formatter)
        stream_handler.setLevel(console_log_level)
        log.addHandler(stream_handler)
        log.setLevel(min(log_level, console_log_level))
    else:
        log.setLevel(log_level)

    return log


def route_fastmcp_logs_to_root(level: int = logging.INFO) -> None:
    """
    Make FastMCP's library logger use the root logging tree (e.g. your file handler).
    FastMCP configures ``logging.getLogger("fastmcp")`` at import with
    ``propagate = False`` and stderr handlers. Call this after ``setup_logging()``.
    When starting the server, also pass ``log_level=None`` to ``mcp.run()`` so
    FastMCP does not reinstall console handlers, and use
    ``uvicorn_config={"log_config": None}`` so Uvicorn does not either.
    """
    fm = logging.getLogger("fastmcp")
    for h in fm.handlers[:]:
        fm.removeHandler(h)
    fm.propagate = True
    fm.setLevel(level)