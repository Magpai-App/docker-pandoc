#!/usr/bin/env python3
from argparse import ArgumentParser
from base64 import b64decode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import JSONDecodeError, loads
from logging import getLogger
from pathlib import Path
from signal import SIGINT, SIGTERM, signal
from subprocess import PIPE, Popen
from sys import argv, exit
from tempfile import TemporaryDirectory
from threading import Thread
from typing import Union
from urllib.request import urlopen

logger = getLogger(__name__)


def create_server(host: str, port: int, token: Union[str, None]) -> ThreadingHTTPServer:
    class RequestHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/":
                logger.warning(f"Invalid path: {self.path}")
                self.send_response(404)
                self.end_headers()
                return

            if token is not None:
                if "Authorization" not in self.headers:
                    logger.warning("No Authorization header")
                    self.send_response(401)
                    self.end_headers()
                    return

                if self.headers["Authorization"] != f"Bearer {token}":
                    logger.warning("Invalid Authorization header")
                    self.send_response(403)
                    self.end_headers()
                    return

            content_type = self.headers.get("Content-Type")
            if content_type != "application/json":
                logger.warning(f"Invalid Content-Type: {content_type}")
                self.send_response(400)
                self.end_headers()
                return

            content_length = int(self.headers["Content-Length"])
            content = self.rfile.read(content_length)

            try:
                payload = loads(content)
            except JSONDecodeError as e:
                logger.warning("Error parsing content as JSON", exc_info=e)
                self.send_response(400)
                self.end_headers()
                return
            except Exception as e:
                logger.exception("Unexpected error occured while parsing the request", exc_info=e)
                self.send_response(500)
                self.end_headers()
                return

            if "files" not in payload:
                logger.warning("No \"files\" in payload")
                self.send_response(400)
                self.end_headers()
                return
            if not isinstance(files := payload.pop("files"), dict):
                logger.warning("Invalid \"files\" in payload")
                self.send_response(400)
                self.end_headers()
                return

            if not isinstance(extra_files := payload.pop("extra_files", {}), dict):
                logger.warning("Invalid \"extra_files\" in payload")
                self.send_response(400)
                self.end_headers()
                return

            if "args" not in payload:
                logger.warning("No \"args\" in payload")
                self.send_response(400)
                self.end_headers()
                return
            if not isinstance(args := payload.pop("args"), list):
                logger.warning("Invalid \"args\" in payload")
                self.send_response(400)
                self.end_headers()
                return

            with TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir).resolve()

                files_path = tmp_path / "files"
                files_path.mkdir(parents=True)

                for file_name, file_content in ({ **files, **extra_files }).items():
                    file_path = (files_path / file_name).resolve()
                    if not file_path.is_relative_to(files_path):
                        logger.warning(f"Invalid file path: {file_path}")
                        self.send_response(400)
                        self.end_headers()
                        return

                    if file_content is None:
                        logger.warning(f"Invalid file content: {file_name}")
                        self.send_response(400)
                        self.end_headers()
                        return

                    if file_content.startswith("data:"):
                        logger.info(f"Decoding {file_name} from data URI...")
                        with file_path.open("wb") as file, urlopen(file_content) as response:
                            file.write(response.read())
                    elif file_content.startswith("http:") or file_content.startswith("https:"):
                        logger.info(f"Downloading {file_name} from {file_content}...")
                        with file_path.open("wb") as file, urlopen(file_content) as response:
                            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                                file.write(chunk)
                    else:
                        logger.info(f"Decoding {file_name} from base64...")
                        with file_path.open("wb") as file:
                            file.write(b64decode(file_content))

                with Popen(
                    [
                        "pandoc",
                        *args,
                        *files.keys(),
                        "-o",
                        "-",
                    ],
                    cwd=str(files_path),
                    stdout=PIPE,
                    stderr=PIPE,
                ) as pandoc_process:
                    pandoc_stdout, pandoc_stderr = pandoc_process.communicate()

                    if pandoc_process.returncode != 0:
                        logger.warning(f"Error running pandoc: {pandoc_process.returncode}")
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(pandoc_stderr)
                        return

                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(pandoc_stdout)))
                    self.end_headers()
                    self.wfile.write(pandoc_stdout)

    return ThreadingHTTPServer((host, port), RequestHandler)


def main(args: list[str]) -> int:
    argparser = ArgumentParser(description="Pandoc Server")
    argparser.add_argument("-H", "--host", type=str, default="0.0.0.0", help="Host to listen on")
    argparser.add_argument("-p", "--port", type=int, default=8080, help="Port to listen on")
    argparser.add_argument("-t", "--token", type=str, default=None, help="If set, a Bearer token to check for")
    args = argparser.parse_args(args[1:])

    http_server = create_server(args.host, args.port, args.token)

    def server_worker():
        with http_server:
            http_server.serve_forever()

    server_thread = Thread(target=server_worker)
    server_thread.start()

    def signal_handler(signum, frame):
        print(f"Shutting down...", flush=True)
        http_server.shutdown()
        server_thread.join()
        exit(0)

    signal(SIGINT, signal_handler)
    signal(SIGTERM, signal_handler)

    print(f"Starting Pandoc Server on {args.host}:{args.port}...", flush=True)
    server_thread.join()
    return 0


if __name__ == "__main__":
    exit(main(argv))
