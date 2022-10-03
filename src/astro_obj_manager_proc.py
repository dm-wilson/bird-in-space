import asyncio
import logging
import os
from astroworkers.manager import TLEManager

# init && run TLE source manager
tlem = TLEManager(
    tle_source_url=os.environ.get(
        "TLE_SOURCE_URL",
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle",
    ),
    refresh_source_interval_s=os.environ.get("TLE_REFRESH_SOURCE_INTERVAL_S", 3600),
    refresh_position_interval_s=os.environ.get("TLE_POSITION_INTERVAL_S", 10),
    host=os.environ.get("TLE_MGMT_BIND_ADDR", "*"),
    port=os.environ.get("TLE_MGMT_BIND_PORT", 5555),
    log_level=os.environ.get("LOG_LEVEL", logging.INFO),
)

asyncio.run(tlem.run())
