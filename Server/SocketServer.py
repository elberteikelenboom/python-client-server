import os
import stat
import errno
import time
import socket
from .Server import Server, Connection, ServerError, UNUSED
from .Errors import *
from .Errors import _error2string


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
    def sendall(self, buffer, encoding='utf8'):
        return self._socket.sendall(self._encode(buffer, encoding))

    #
    # Receive data from peer.
    #
    def receive(self, encoding='utf8'):
        return self._decode(self._socket.recv(1024), encoding)


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
    # Run the socket server forever. For each connection fork()
    # a new process and run the connection handler. Do not accept
    # more then _max_connections at the same time.
    #
    # When the handler exits, the connection is shutdown/closed. When
    # the handler as an integral return value, it is returned to the
    # parent process. Otherwise the return value is set to 0.
    #
    def serve_forever(self):
        self._socket.listen(1)
        children = []
        while True:
            connection, address = self._socket.accept()
            pid = os.fork()
            if pid == 0:
                status = 0                                             # Path executed in the child process.
                try:
                    #
                    # Call the connection handler.
                    #
                    status = self._handler(_SocketConnection(connection, address))
                except Exception as e:
                    UNUSED(e)
                finally:
                    self._close_connection(connection)                 # Always shutdown/close the connection properly.
                    if not isinstance(status, int):
                        status = 0                                     # When status is not integral, overrule.
                    # noinspection PyProtectedMember
                    os._exit(status)                                   # Exit the child process.
            else:
                children.append(pid)                                   # Path executed in the parent process.
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
                    time.sleep(0.01)                                   # Throttle.


#
# Define a TCP/IP socket server.
#
class _TCPSocketServer(_SocketServer):
    def __init__(self, handler, address, port, max_connections):
        if not self._is_ip_address(address):
            raise ServerError(E_INVALID_IP_ADDRESS, _error2string[E_INVALID_IP_ADDRESS] % address)
        if not isinstance(port, int):
            raise ServerError(E_INTEGRAL_PORT, _error2string[E_INTEGRAL_PORT] % port)
        super(_TCPSocketServer, self).__init__(socket.AF_INET, socket.SOCK_STREAM, (address, port), handler, max_connections)

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
# Define a Unix socket server.
#
class _UNIXSocketServer(_SocketServer):
    def __init__(self, handler, path, max_connections):
        if self._is_socket(path):
            os.remove(path)
        elif os.path.exists(path):
            raise ServerError(E_PATH_EXISTS_BUT_NOT_SOCKET, _error2string[E_PATH_EXISTS_BUT_NOT_SOCKET] % path)
        super(_UNIXSocketServer, self).__init__(socket.AF_UNIX, socket.SOCK_STREAM, path, handler, max_connections)

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
