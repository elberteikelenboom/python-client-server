import os
import socket
import select
import errno
from .Connection import Connection
from .Errors import *
from .Errors import _error2string


#
# Define a socket connection.
#
class _SocketConnection(Connection):
    def __init__(self, socket_, address, disconnect):
        super(_SocketConnection, self).__init__()
        if not callable(disconnect):
            raise ConnectionError(E_PARAMETER_IS_NOT_CALLABLE, _error2string[E_PARAMETER_IS_NOT_CALLABLE] % "disconnect")
        self._socket = socket_
        self._address = address
        self._disconnect = disconnect

    #
    # Send buffer to peer.
    #
    def send(self, buffer, encoding='utf8'):
        while True:
            if self.disconnect:
                raise socket.error(errno.ECONNABORTED, os.strerror(errno.ECONNABORTED))
            read, write = self.poll()
            if write:
                break                                                          # Socket ready for writing.
        self._socket.sendall(self._encode(buffer, encoding))

    #
    # Receive data from peer.
    #
    def receive(self, buffer_size=1024, encoding='utf8'):
        while True:
            if self.disconnect:
                raise socket.error(errno.ECONNABORTED, os.strerror(errno.ECONNABORTED))
            read, write = self.poll()
            if read:
                break                                                          # Socket ready for reading.
        buffer_size = max(1, buffer_size)                                      # Buffer size is at least 1 byte.
        buffer = self._socket.recv(buffer_size)
        if len(buffer) == 0:
            raise socket.error(errno.ECONNRESET, os.strerror(errno.ECONNRESET))
        return self._decode(buffer, encoding)

    #
    # Return a tuple indicating whether or not the
    # connection is ready for reading and/or writing.
    #
    def poll(self):
        read, write, error = select.select([self._socket], [self._socket], [], 0.0)
        return len(read) != 0, len(write) != 0

    #
    # Return True when a disconnect is requested.
    #
    @property
    def disconnect(self):
        return self._disconnect()
