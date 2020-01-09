import socket
import errno
from .Connection import Connection


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
