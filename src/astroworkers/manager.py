import json
import logging
import os
import time
import asyncio
import requests
import urllib.parse

import zmq
import astropy
import sgp4
from astroworkers.base import Worker

# constamts for management...
TLE_EXPECTED_LINE_LEN = 69


class TLEManager(Worker):
    """
    The Two-Line Element Manager (TLEM) is a glorified timer. TLEM is initialised with a
    TLE source (e.g. NORAD, Celestrak, JSOC, etc.), every `T_s` seconds following init,
    gets all objects, `X` from the TLE source. Then, every `T_p` seconds after initialization,
    the TLEM pushes a trigger calculation message thru ZMQ.
    """

    def __init__(
        self,
        tle_source_url: str,
        refresh_source_interval_s: int = 3600,
        refresh_position_interval_s: int = 15,
        src_get_params: dict = {
            "max_attempts": 5,
            "backoff_factor": 2,
            "timeout_s": 1,
        },
        host: str = "*",
        port: int = 5555,
        log_level: int = logging.INFO,
    ):
        super().__init__(host=host, port=port, log_level=logging.INFO)
        self.refresh_source_interval_s = refresh_source_interval_s
        self.refresh_position_interval_s = refresh_position_interval_s
        self.tle_source_url = tle_source_url
        self.src_get_params = src_get_params

    async def _task_refresh_tle_source(self) -> None:
        try:
            s = requests.Session()
            retries = requests.adapters.Retry(
                total=self.src_get_params.get("max_attempts"),
                backoff_factor=self.src_get_params.get("backoff_factor"),
                status_forcelist=[301, 400, 402, 403, 404, 500, 502, 503, 504],
            )

            tle_src = urllib.parse.urlsplit(self.tle_source_url)
            s.mount(
                f"{tle_src.scheme}://",
                requests.adapters.HTTPAdapter(max_retries=retries),
            )
            r = s.get(
                self.tle_source_url,
                timeout=self.src_get_params.get("timeout_s"),
                stream=True,
            )
            r.raise_for_status()
        except Exception as err:
            self._log(
                {
                    "msg": "request to TLE source failed; using cached tle parameters",
                    "source": self.tle_source_url,
                    "error": err.__str__(),
                },
                logging.ERROR,
            )
            return

        tles = list(filter(lambda x: len(x) > 0, r.text.split("\n")))
        if len(tles) % 3 != 0:
            self._log(
                {
                    "msg": "failed to update tle parameters",
                    "source": self.tle_source_url,
                    "n_lines": len(tles),
                    "err": "malformed tle data, failed n_lines check",
                },
                logging.ERROR,
            )
            return

        self.tles = []
        for n in range(0, len(tles), 3):
            name, tle_l1, tle_l2 = tles[n], tles[n + 1].strip(), tles[n + 2].strip()
            if (len(tle_l1) != TLE_EXPECTED_LINE_LEN) | (
                len(tle_l2) != TLE_EXPECTED_LINE_LEN
            ):
                self._log(
                    {
                        "name": name.strip(),
                        "msg": "failed to update tle parameters",
                        "source": self.tle_source_url,
                        "tle_lens": (len(tle_l1), len(tle_l2)),
                        "err": "malformed tle data, failed fixed-size check",
                    },
                    logging.ERROR,
                )
                continue

            self.tles.append(
                {
                    "name": name.strip(),
                    "tle_l1": tle_l1,
                    "tle_l2": tle_l2,
                }
            )

        self._log(
            {
                "msg": "updated tle parameterizatons",
                "source": self.tle_source_url,
                "n_objects": len(self.tles),
            }
        )
        return

    async def _task_trigger_position_update(self):
        exec_t = time.time_ns() / 1_000_000_000
        self._log({"msg": "triggered tle calculation", "exec_t": exec_t})
        for tle in self.tles:
            self._zmq_push({"exec_t": exec_t, **tle})

    async def run_position_update_loop(self):
        while True:
            await asyncio.gather(
                self._task_trigger_position_update(),
                asyncio.sleep(self.refresh_position_interval_s),
                return_exceptions=True,
            )

    async def run_source_update_loop(self):
        while True:
            await asyncio.gather(
                self._task_refresh_tle_source(),
                asyncio.sleep(self.refresh_source_interval_s),
                return_exceptions=True,
            )

    async def run(self):
        t1 = asyncio.create_task(self.run_source_update_loop())
        t2 = asyncio.create_task(self.run_position_update_loop())
        await t1
        await t2
