import io
import json
import logging
import sys
import zmq


class Worker:
    """base class for higher-level TLE workers/managers"""

    def __init__(
        self, host: str = "*", port: int = 5555, log_level: int = logging.INFO
    ):
        self._init_logging(log_level)
        self.context = zmq.Context()
        self.host, self.port = host, port
        self._is_pushing = False
        self.push_socket, self.pull_socket = None, None

    def __del__(self):
        """teardown all push/pull contexts - no lingering processes!"""
        for s in [self.push_socket, self.pull_socket]:
            if (s) and (not s._closed):
                s.close()

    def _log(self, d: dict, level: int = logging.INFO) -> None:
        """slim wrapper around self.logger._log to save a few LOC"""
        self.logger._log(level, json.dumps(d), dict())

    def _init_logging(
        self,
        log_level: int = logging.INFO,
        location: io.TextIOWrapper = sys.stdout,
        msg_fmt: str = "%(asctime)s %(levelname)s [%(process)s] [%(thread)s] %(message)s",
    ):
        """initialize logger for all worker classes"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.getLevelName(log_level))
        logging.basicConfig(stream=location, format=msg_fmt)
        self.logger = logger

    def _zmq_init_push_socket(self) -> None:
        """intialize worker to push over ZMQ"""
        bind_address = f"tcp://{self.host}:{self.port}"

        self._log(
            {
                "msg": "initializing zmq push context",
                "bind_addr": bind_address,
            }
        )

        socket = self.context.socket(zmq.PUSH)
        socket.bind(bind_address)

        self.push_socket = socket
        self._is_pushing = True

    def _zmq_init_pull_socket(self) -> None:
        """intialize worker to pull over ZMQ"""
        conn_addr = f"tcp://{self.host}:{self.port}"
        self._log(
            {
                "msg": "initializing zmq pull context",
                "connect_addr": conn_addr,
            }
        )
        socket = self.context.socket(zmq.PULL)
        socket.connect(conn_addr)
        self.pull_socket = socket

    def _zmq_pull(self, func) -> None:
        """initialize long-running pull job from ZMQ, run until canceled"""
        self._zmq_init_pull_socket()
        while True:
            msg = self.pull_socket.recv_json()
            func(msg)
        self.pull_socket.close()

    def _zmq_push(self, msg: dict) -> None:
        """push a single message over ZMQ"""
        if not (self._is_pushing):
            self._zmq_init_push_socket()
        self.push_socket.send_json(msg)
