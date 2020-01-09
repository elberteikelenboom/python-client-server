import os
import stat
import errno
import time
import socket
import threading
import logging
from .Server import Server, Connection, ServerError, UNUSED
from .Errors import *
from .Errors import _error2string

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


#
# Define a socket connection.
#
class _SocketConnection(Connection):
    def __init__(self, socket_, address):
        super(_SocketConnection, self).__init__()
        self._socket = socket_
        self._address = address

    #
    # Send buffer to peer.
    #
    def send(self, buffer, encoding='utf8'):
        self._socket.sendall(self._encode(buffer, encoding))

    #
    # Receive data from peer.
    #
    def receive(self, buffer_size=1024, encoding='utf8'):
        buffer_size = max(1, buffer_size)                                              # Buffer size is at least 1 byte.
        buffer = self._socket.recv(buffer_size)
        if len(buffer) == 0:
            raise socket.error(errno.ECONNRESET, os.strerror(errno.ECONNRESET))
        return self._decode(buffer, encoding)

    #
    # Receive a single line of text from peer.
    #
    def receive_line(self, buffer_size=None, encoding='utf8'):
        return self._receive_line(1024, buffer_size, encoding)


#
# Define a socket server base class.
#
class _SocketServer(Server):
    #
    # Initialize a socket server.
    #
    def __init__(self, family, type_, address, handler, max_connections):
        super(_SocketServer, self).__init__(address, handler)
        self._socket = socket.socket(family, type_)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(self._address)
        self._max_connections = max_connections

    #
    # Close a connection and ignore any errors
    # while doing so.
    #
    @staticmethod
    def _close_connection(connection):
        try:
            connection.shutdown(socket.SHUT_RDWR)
            connection.close()
        except Exception as e:
            UNUSED(e)

    #
    # Return True when address is a valid IPv4 address.
    #
    @staticmethod
    def _is_ip_address(address):
        try:
            socket.inet_aton(address)
        except OSError:
            is_address = False
        else:
            is_address = True
        return is_address

    #
    # Return True if path refers to a Unix socket.
    #
    @staticmethod
    def _is_socket(path):
        is_socket = False
        if os.path.exists(path):
            mode = os.stat(path).st_mode
            is_socket = stat.S_ISSOCK(mode)
        return is_socket

    #
    # Abstract method that must be defined in a subclass.
    #
    def serve_forever(self):
        raise NotImplementedError("%s: The serve_forever() method shall be implemented in a subclass" % type(self).__name__)


#
# Define a forking socket server.
#
class _ForkingSocketServer(_SocketServer):
    #
    # Run the socket server forever. For each connection fork()
    # a new process and run the connection handler. Do not accept
    # more then _max_connections at the same time.
    #
    # When the handler exits, the connection is shutdown/closed. When
    # the handler returns an integral return value, it is returned to the
    # parent process. Otherwise the return value is set to 0.
    #
    def serve_forever(self):
        children = []
        self._socket.listen(1)
        while True:
            logger.info("%s: serve_forever() -- Accepting connections at: %s.", type(self).__name__, str(self._address))
            connection, address = self._socket.accept()
            pid = os.fork()
            if pid == 0:
                status = 0                                             # Path executed in the child process.
                try:
                    try:
                        #
                        # Call the connection handler.
                        #
                        logger.info("%s: serve_forever() -- Incoming connection from: %s.", type(self).__name__, str(address))
                        status = self._handler(_SocketConnection(connection, address))
                    except socket.error as e:
                        if e.errno != errno.ECONNRESET:
                            logger.error("%s: serve_forever() -- %s.", type(self).__name__, e)
                        else:
                            raise e
                except Exception as e:
                    logger.exception("%s: serve_forever() -- %s", type(self).__name__, e)
                finally:
                    logger.info("%s: serve_forever() -- Closed connection from: %s.", type(self).__name__, str(address))
                    self._close_connection(connection)                 # Always shutdown/close the connection properly.
                    if not isinstance(status, int):
                        status = 0                                     # When status is not integral, overrule.
                    # noinspection PyProtectedMember
                    os._exit(status)                                   # Exit the child process.
            else:
                children.append(pid)                                   # Path executed in the parent process.
                log_max_connections = True
                while True:
                    for pid in children[:]:
                        finished_pid = 0
                        try:
                            finished_pid, finished_status = os.waitpid(pid, os.WNOHANG)
                        except OSError as e:
                            if e.errno != errno.ECHILD:
                                raise e
                            #
                            # The child process does not exist anymore. It can
                            # therefore definitely be removed from the list of
                            # children.
                            #
                            finished_pid = pid
                        finally:
                            if finished_pid != 0:
                                children.remove(finished_pid)
                    if len(children) < self._max_connections:          # Wait until we can accept connections again.
                        break
                    if log_max_connections:
                        logger.info("%s: serve_forever() -- Maximum number of connections (%d) reached.", type(self).__name__, self._max_connections)
                        log_max_connections = False
                    time.sleep(0.01)                                   # Throttle.


#
# Define a threading socket server.
#
class _ThreadingSocketServer(_SocketServer):
    #
    # Define the thread that runs the connection handler.
    #
    class HandlerThread(threading.Thread):
        # noinspection PyDefaultArgument
        def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, *, daemon=None):
            super(_ThreadingSocketServer.HandlerThread, self).__init__(group=group, target=None, name=name, args=args, kwargs=kwargs, daemon=daemon)
            self._connection, self._close_connection, self._socket, self._address = args
            self._target = target
            self._status = 0

        #
        # Run the handler, catch the exit status and handle exceptions.
        #
        def run(self):
            try:
                try:
                    self._status = self._target(self._connection)
                except socket.error as e:
                    if e.errno == errno.ECONNRESET:
                        logger.error("%s: serve_forever() -- %s.", type(self).__name__, e)
                    else:
                        raise e
            except Exception as e:
                logger.exception("%s: serve_forever() -- %s", type(self).__name__, e)
            finally:
                logger.info("%s: serve_forever() -- Closed connection from: %s.", type(self).__name__, str(self._address))
                self._close_connection(self._socket)                           # Always shutdown/close the connection properly.
                if not isinstance(self._status, int):
                    self._status = 0

        #
        # Return the exit status of the handler.
        #
        @property
        def status(self):
            return self._status

    #
    # Run the socket server forever. For each connection create
    # a new thread and run the connection handler in it. Do not accept
    # more then _max_connections at the same time.
    #
    # When the handler exits, the connection is shutdown/closed. When
    # the handler returns an integral return value, it is returned to the
    # parent process. Otherwise the return value is set to 0.
    #
    def serve_forever(self):
        threads = []
        self._socket.listen(1)
        while True:
            logger.info("%s: serve_forever() -- Accepting connections at: %s.", type(self).__name__, str(self._address))
            connection, address = self._socket.accept()
            #
            # Start the connection handler in a new thread.
            #
            logger.info("%s: serve_forever() -- Incoming connection from: %s.", type(self).__name__, str(address))
            thread = _ThreadingSocketServer.HandlerThread(target=self._handler, args=(_SocketConnection(connection, address), self._close_connection, connection, address))
            thread.start()
            threads.append(thread)
            log_max_connections = True
            while True:
                for thread in threads[:]:
                    if not thread.is_alive():
                        #
                        # Here, thread.status contains the handler's exit status.
                        #
                        threads.remove(thread)
                if len(threads) < self._max_connections:
                    break
                if log_max_connections:
                    logger.info("%s: serve_forever() -- Maximum number of connections (%d) reached.", type(self).__name__, self._max_connections)
                    log_max_connections = False
                time.sleep(0.1)                                        # Throttle.


#
# Define an iterative socket server.
#
class _IterativeSocketServer(_SocketServer):
    #
    # Run the socket server forever. Accept a connection, handle it and
    # then handle the next connection. Do not fork() nor create threads.
    #
    # When the handler exits, the connection is shutdown/closed. When
    # the handler returns an integral return value, it is returned to the
    # parent process. Otherwise the return value is set to 0.
    #
    def serve_forever(self):
        self._socket.listen(1)
        while True:
            logger.info("%s: serve_forever() -- Accepting connections at: %s.", type(self).__name__, str(self._address))
            connection, address = self._socket.accept()
            status = 0                                                 # Path executed in the child process.
            try:
                try:
                    #
                    # Call the connection handler.
                    #
                    logger.info("%s: serve_forever() -- Incoming connection from: %s.", type(self).__name__, str(address))
                    status = self._handler(_SocketConnection(connection, address))
                except socket.error as e:
                    if e.errno != errno.ECONNRESET:
                        logger.error("%s: serve_forever() -- %s.", type(self).__name__, e)
                    else:
                        raise e
            except Exception as e:
                logger.exception("%s: serve_forever() -- %s", type(self).__name__, e)
            finally:
                logger.info("%s: serve_forever() -- Closed connection from: %s.", type(self).__name__, str(address))
                self._close_connection(connection)                     # Always shutdown/close the connection properly.
                if not isinstance(status, int):
                    status = 0                                         # When status is not integral, overrule.
            UNUSED(status)


#
# Define a forking TCP/IP socket server.
#
class _ForkingTCPSocketServer(_ForkingSocketServer):
    def __init__(self, handler, address, port, max_connections):
        if not self._is_ip_address(address):
            raise ServerError(E_INVALID_IP_ADDRESS, _error2string[E_INVALID_IP_ADDRESS] % address)
        if not isinstance(port, int):
            raise ServerError(E_INTEGRAL_PORT, _error2string[E_INTEGRAL_PORT] % port)
        super(_ForkingTCPSocketServer, self).__init__(socket.AF_INET, socket.SOCK_STREAM, (address, port), handler, max_connections)


#
# Define a forking Unix socket server.
#
class _ForkingUNIXSocketServer(_ForkingSocketServer):
    def __init__(self, handler, path, max_connections):
        if self._is_socket(path):
            os.remove(path)
        elif os.path.exists(path):
            raise ServerError(E_PATH_EXISTS_BUT_NOT_SOCKET, _error2string[E_PATH_EXISTS_BUT_NOT_SOCKET] % path)
        super(_ForkingUNIXSocketServer, self).__init__(socket.AF_UNIX, socket.SOCK_STREAM, path, handler, max_connections)


#
# Define a threading TCP/IP socket server.
#
class _ThreadingTCPSocketServer(_ThreadingSocketServer):
    def __init__(self, handler, address, port, max_connections):
        if not self._is_ip_address(address):
            raise ServerError(E_INVALID_IP_ADDRESS, _error2string[E_INVALID_IP_ADDRESS] % address)
        if not isinstance(port, int):
            raise ServerError(E_INTEGRAL_PORT, _error2string[E_INTEGRAL_PORT] % port)
        super(_ThreadingTCPSocketServer, self).__init__(socket.AF_INET, socket.SOCK_STREAM, (address, port), handler, max_connections)


#
# Define a threading Unix socket server.
#
class _ThreadingUNIXSocketServer(_ThreadingSocketServer):
    def __init__(self, handler, path, max_connections):
        if self._is_socket(path):
            os.remove(path)
        elif os.path.exists(path):
            raise ServerError(E_PATH_EXISTS_BUT_NOT_SOCKET, _error2string[E_PATH_EXISTS_BUT_NOT_SOCKET] % path)
        super(_ThreadingUNIXSocketServer, self).__init__(socket.AF_UNIX, socket.SOCK_STREAM, path, handler, max_connections)


#
# Define an iterative TCP/IP socket server.
#
class _IterativeTCPSocketServer(_IterativeSocketServer):
    def __init__(self, handler, address, port):
        if not self._is_ip_address(address):
            raise ServerError(E_INVALID_IP_ADDRESS, _error2string[E_INVALID_IP_ADDRESS] % address)
        if not isinstance(port, int):
            raise ServerError(E_INTEGRAL_PORT, _error2string[E_INTEGRAL_PORT] % port)
        super(_IterativeSocketServer, self).__init__(socket.AF_INET, socket.SOCK_STREAM, (address, port), handler, 1)


#
# Define an iterative Unix socket server.
#
class _IterativeUNIXSocketServer(_IterativeSocketServer):
    def __init__(self, handler, path):
        if self._is_socket(path):
            os.remove(path)
        elif os.path.exists(path):
            raise ServerError(E_PATH_EXISTS_BUT_NOT_SOCKET, _error2string[E_PATH_EXISTS_BUT_NOT_SOCKET] % path)
        super(_IterativeUNIXSocketServer, self).__init__(socket.AF_UNIX, socket.SOCK_STREAM, path, handler, 1)
