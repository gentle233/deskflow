"""简单日志"""
import logging
import os

LOG_PATH = os.path.expanduser("~/.deskflow/deskflow.log")

def setup_logger():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )
    return logging.getLogger("deskflow")

logger = setup_logger()
