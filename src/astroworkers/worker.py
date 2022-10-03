import io
import json
import logging
import os
import sys
import time
import uuid
import urllib.parse

from multiprocessing.dummy import Pool
import requests
import zmq

import astropy.units
import astropy.time
import astropy.coordinates

import sgp4.api

from astroworkers.base import Worker

# environment vars for management...
TB_WORKSPACE_RW_TOKEN = os.environ.get("TB_WORKSPACE_RW_TOKEN")
TB_TARGET_ENDPOINT = os.environ.get(
    "TB_TARGET_ENDPOINT", "https://api.tinybird.co/v0/events"
)
TB_TARGET_TABLE = os.environ.get("TB_TARGET_TABLE", "astro_obj_positions")


class TLEWorker(Worker):
    """
    Two-Line Element Set Worker (TLEW) is one of a group of workers that calculate the current position of
    a set of NORAD objects, `X`

    TLEW maintans a TLE source in memory and evaluates TLE_POS(t, x) -> (lat, lng, elev)` at the current
    time (`t`) for all `x ∈ X`. The position tuple from this process is sent to an HTTP endpoint.
    """

    def __init__(
        self,
        host: str = "*",
        port: int = 5555,
        req_threadpool_size: int = 10,
        log_level: int = logging.INFO,
    ):
        super().__init__(host=host, port=port, log_level=logging.INFO)
        self.pool = Pool(req_threadpool_size)

    def on_error(self, ex: Exception = None, detail: str = None):
        self._log(
            {"err": ex.__str__(), "msg": "failed post to tinybird", "detail": detail},
            logging.ERROR,
        )

    def on_success(self, resp) -> None:
        try:
            # escape hatch for getting rate limited -> add a sleep job to the pool
            if resp.status_code == 429:
                self.logger.warn("applying 2s blockng backoff")
                self.pool.apply(time.sleep, (2,))
            resp.raise_for_status()
        except Exception as e:
            self.on_error(e, resp.text)

    def post_positions_to_tinybird(self, msg: dict) -> None:
        """fire-and-forget a message to the tinybird hfi endpoint"""

        self.pool.apply_async(
            requests.post,
            kwds={
                "url": TB_TARGET_ENDPOINT,
                "params": {
                    "token": TB_WORKSPACE_RW_TOKEN,
                    "name": TB_TARGET_TABLE,
                },
                "data": json.dumps(msg),
            },
            error_callback=self.on_error,
            callback=self.on_success,
        )

    def propogate_position(self, msg: dict) -> None:
        """calculate current position of object parameterized by TLE in `msg`"""

        t = astropy.time.Time(float(msg.get("exec_t")), format="unix")
        sat = sgp4.api.Satrec.twoline2rv(msg.get("tle_l1"), msg.get("tle_l2"))
        error_code, teme_p, teme_v = sat.sgp4(t.jd1, t.jd2)

        if error_code != 0:
            self.logger.error(RuntimeError(sgp4.api.SGP4_ERRORS[error_code]))
            return

        itrs = astropy.coordinates.ITRS(
            astropy.coordinates.CartesianRepresentation(
                teme_p * astropy.units.km,
                differentials=astropy.coordinates.CartesianDifferential(
                    teme_v * astropy.units.km / astropy.units.s
                ),
            ),
            obstime=t,
        )

        self.post_positions_to_tinybird(
            {
                "satnum": str(sat.satnum),
                "name": msg.get("name"),
                "time": int(t.unix),
                "e_lat": itrs.earth_location.lat.value,
                "e_lng": itrs.earth_location.lon.value,
                "e_alt": itrs.earth_location.height.value,
                "d_x": itrs.v_x.value,
                "d_y": itrs.v_y.value,
                "d_z": itrs.v_z.value,
            }
        )
        return

    def run(self) -> None:
        self._zmq_pull(func=self.propogate_position)
