import os
import stat
import socket
import time
import errno

E_INTEGRAL_PORT = 1
E_INVALID_IP_ADDRESS = 2
E_PATH_EXISTS_BUT_NOT_SOCKET = 3
E_HANDLER_NOT_CALLABLE = 4

_error2string = {
    E_INTEGRAL_PORT: "Port number shall be an integral, got: '%r'",
    E_INVALID_IP_ADDRESS: "Invalid IP-address, got: '%r'",
    E_PATH_EXISTS_BUT_NOT_SOCKET: "Path already exists but it is not a socket: '%s'",
    E_HANDLER_NOT_CALLABLE: "The handler is not callable"
}


# noinspection PyPep8Naming,PyUnusedLocal
def UNUSED(*args, **kwargs):
    pass


#
# Exception class to be generated by the Server.py module.
#
class ServerError(Exception):
    def __init__(self, error_code, message):
        super(ServerError, self).__init__(message)
        self.error_code = error_code


#
# Define the server base class.
#
class Server(object):
    #
    # Map a server type to an instance of a corresponding server class.
    #
    _server_type2class = {
        'tcp': lambda handler, address, port, max_connections=1: _TCPSocketServer(handler, address, port, max_connections),
        'unix': lambda handler, path, max_connections=1: _UNIXSocketServer(handler, path, max_connections)
    }

    #
    # Initialize the server base class.
    #
    def __init__(self, address, handler):
        if not callable(handler):
            raise ServerError(E_HANDLER_NOT_CALLABLE, _error2string[E_HANDLER_NOT_CALLABLE])
        self._address = address
        self._handler = handler

    #
    # Abstract method that must be defined in a subclass.
    #
    def serve_forever(self):
        raise NotImplementedError("%s: The serve_forever() method shall be implemented in a subclass" % type(self).__name__)

    #
    # Return a server instance corresponding to the specified server type.
    # The specified server type is case insensitive and can be one of:
    #
    # * tcp : create a TCP/IP socket server.
    # * unix: create a UNIX domain socket server.
    #
    @classmethod
    def create(cls, server_type, handler, *args, **kwargs):
        return cls._server_type2class[server_type.lower()](handler, *args, **kwargs)


#
# Base class for connections.
#
class Connection(object):
    def __init__(self):
        pass

    #
    # Send buffer to peer. The buffer is expected
    # to be a string, which is utf8 encoded before
    # sending.
    #
    def sendall(self, buffer):
        raise NotImplementedError("%s: The sendall() method shall be implemented in a subclass" % type(self).__name__)

    #
    # Receive data from peer. The data is expected to
    # to be utf8 encoded and is return as a string.
    #
    def receive(self):
        raise NotImplementedError("%s: The receive() method shall be implemented in a subclass" % type(self).__name__)


#
# Create a socket connection.
#
class _SocketConnection(Connection):
    def __init__(self, socket_, address):
        super(_SocketConnection, self).__init__()
        self._socket = socket_
        self._address = address

    #
    # Send buffer to peer encoded in utf8.
    #
    def sendall(self, buffer):
        buffer = bytes(buffer, 'utf8')
        return self._socket.sendall(buffer)

    #
    # Receive data from peer. Decode from
    # utf8 and return as a string.
    #
    def receive(self):
        data = self._socket.recv(1024)
        data = data.decode('utf8')
        return data


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
    # parent process. Otherwise the return value is set to 0
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
