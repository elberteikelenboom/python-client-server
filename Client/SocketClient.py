import os
import stat
import socket
import errno
import time
import logging
from Connection import Connection
from .Client import Client, ClientError, UNUSED
from .Errors import *
from .Errors import _error2string

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


#
# Define a socket client.
#
class _SocketClient(Client):
    #
    # Initialize a socket client.
    #
    def __init__(self, client_type, family, type_, address, handler, reconnect):
        super(_SocketClient, self).__init__(client_type, address, handler)
        self._family = family
        self._type = type_
        self._reconnect = reconnect
        self._socket = None

    #
    # Connect to the server, and run the specified handler for the
    # connection. When reconnect is set to None, the connection reset
    # socket error is reraised. When the reconnect setting is a float,
    # automatically try to reconnect to the server. The reconnect
    # value is used to throttle the reconnection attempts.
    #
    def connect(self):
        while True:
            self._socket = socket.socket(self._family, self._type)
            self._socket.connect(self._address)
            logger.info("%s: connect() -- connected to server: %s", type(self).__name__, str(self._address))
            status = 0
            try:
                #
                # Connected to server, run the connection handler.
                #
                status = self._handler(Connection.create(self._client_type, self._socket, self._socket.getpeername()))
            except socket.error as e:
                if self._reconnect is not None and e.errno == errno.ECONNRESET:
                    logger.info("%s: connect() -- lost connection to server: %s, reconnecting in: %f seconds", type(self).__name__, str(self._address), self._reconnect)
                    time.sleep(self._reconnect)                                # Throttle the reconnection attempts.
                    continue
                raise e                                                        # No reconnect requested, or not connection reset; re-raise the exception.
            else:
                break                                                          # The handler exited normally; exit.
            finally:
                logger.info("%s: connect() -- closing connection to: %s", type(self).__name__, str(self._address))
                self._close_connection()                                       # In all cases close the connection.
                if not isinstance(status, int):
                    status = 0  # When status is not integral, overrule.
                UNUSED(status)                                                 # The returned status is currently not used.

    #
    # Close a connection and ignore any errors
    # while doing so.
    #
    def _close_connection(self):
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
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
# Define a TCP/IP socket client.
#
class _TCPSocketClient(_SocketClient):
    def __init__(self, server_type, handler, address, port, reconnect):
        if not self._is_ip_address(address):
            raise ClientError(E_INVALID_IP_ADDRESS, _error2string[E_INVALID_IP_ADDRESS] % address)
        if not isinstance(port, int):
            raise ClientError(E_INTEGRAL_PORT, _error2string[E_INTEGRAL_PORT] % port)
        super(_TCPSocketClient, self).__init__(server_type, socket.AF_INET, socket.SOCK_STREAM, (address, port), handler, reconnect)


#
# Define a Unix socket client.
#
class _UNIXSocketClient(_SocketClient):
    def __init__(self, server_type, handler, path, reconnect):
        if os.path.exists(path) and not self._is_socket(path):
            raise ClientError(E_PATH_EXISTS_BUT_NOT_SOCKET, _error2string[E_PATH_EXISTS_BUT_NOT_SOCKET] % path)
        elif not os.path.exists(path):
            raise ClientError(E_PATH_DOES_NOT_EXIST, _error2string[E_PATH_DOES_NOT_EXIST] % path)
        super(_UNIXSocketClient, self).__init__(server_type, socket.AF_UNIX, socket.SOCK_STREAM, path, handler, reconnect)
