import logging as log
import socket
import select
import errno
from Session import Session
from config import config

class ServerSocket(object):
    def init(self):
        self._serversocket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        self._serversocket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._epoll = select.epoll()
        self._sessions = {}
        log.basicConfig(filename=config["log"]["file"], level=config["log"]["level"], format=config["log"]["format"])

    def listen(self, host, port):
        self._serversocket.bind((host, port))
        self._serversocket.listen(10)
        self._serversocket.setblocking(False)
        log.info(f"listen to {host}:{port}")
        self._epoll.register(self._serversocket.fileno(), select.EPOLLIN)

    def _event_process(self, events):
        if not events:
            return

        for fd, event in events:
            # have new connection to server
            if fd == self._serversocket.fileno():
                connection, address = self._serversocket.accept()
                connection.setblocking(False)
                self._epoll.register(
                    connection.fileno(), select.EPOLLIN)
                self._sessions[connection.fileno()] = Session(
                    connection, address)
                self._sessions[connection.fileno()].doConnect()
            # client close
            elif event & select.EPOLLHUP or event & select.EPOLLRDHUP:
                self._epoll.unregister(fd)
                self._sessions[fd].close(1)
                del self._sessions[fd]
            # have some date to read or client close
            elif event & select.EPOLLIN:
                if self._sessions[fd].doRequest():
                    self._epoll.modify(fd, select.EPOLLOUT)
                else:
                    self._epoll.unregister(fd)
                    self._sessions[fd].close(2)
                    del self._sessions[fd]
            # can write data to the socket now
            elif event & select.EPOLLOUT:
                self._sessions[fd].doResponse()
                self._epoll.modify(fd, select.EPOLLIN)

    def run(self):
        try:
            self.init()
            self.listen("0.0.0.0", config["server"]["port"])
            log.info("Starting server...")
            while True:
                try:
                    events = self._epoll.poll(20)
                    self._event_process(events)
                except IOError as e:
                    if e.errno == errno.EPIPE:
                        log.exception(e)
                except (SystemExit, KeyboardInterrupt):
                    self.close()
                    break
                except BaseException as e:
                    log.exception(e)
        except (SystemExit, KeyboardInterrupt):
            self.close()
        except Exception as e:
            log.exception(e)
        finally:
            log.info("finished!")

    def close(self):
        self._epoll.unregister(self._serversocket.fileno())
        self._epoll.close()
        self._serversocket.close()


if __name__ == '__main__':
    server = ServerSocket()
    server.run()