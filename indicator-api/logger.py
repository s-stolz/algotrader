import logging

LOG_LEVEL_APP = logging.DEBUG
LOG_LEVEL_UVICORN = logging.WARNING

logging.basicConfig(level=LOG_LEVEL_APP)
logger = logging.getLogger
