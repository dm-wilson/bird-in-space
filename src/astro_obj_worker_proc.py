import os
import logging
from astroworkers.worker import TLEWorker

tlew = TLEWorker(
    log_level=os.environ.get("LOG_LEVEL", logging.INFO),
    host=os.environ.get("TLEW_WORKER_CONNECT_ADDR", "tlepub"),
    port=os.environ.get("TLEW_WORKER_CONNECT_PORT", 5555),
)
tlew.run()
