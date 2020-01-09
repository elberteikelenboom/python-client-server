from .Connection import Connection


#
# Define a serial connection.
#
class _SerialConnection(Connection):
    def __init__(self, serial_):
        super(_SerialConnection, self).__init__()
        self._serial = serial_

    #
    # Send buffer to peer.
    #
    def send(self, buffer, encoding='utf8'):
        total = 0
        while total < len(buffer):
            sent = self._serial.write(self._encode(buffer[total:], encoding))
            total += sent

    #
    # Receive data from peer.
    #
    def receive(self, buffer_size=1, encoding='utf8'):
        buffer_size = max(1, buffer_size)                                              # Buffer size is at least 1 byte.
        return self._decode(self._serial.read(buffer_size), encoding)

    #
    # Receive a single line of text from peer.
    #
    def receive_line(self, buffer_size=None, encoding='utf8'):
        return self._receive_line(1, buffer_size, encoding)


