from io import StringIO
from .Errors import *
from .Errors import _error2string


#
# Exception class to be generated by the Connection package.
#
# noinspection PyShadowingBuiltins
class ConnectionError(Exception):
    def __init__(self, error_code, message):
        super(ConnectionError, self).__init__(message)
        self.error_code = error_code


#
# Base class for connections.
#
class Connection(object):
    def __init__(self):
        self._line_buffer = ''

    #
    # Encode a buffer for sending. Raise an exception
    # when buffer has an invalid type.
    #
    @staticmethod
    def _encode(buffer, encoding='utf8'):
        if not isinstance(buffer, (str, bytes, bytearray, memoryview)):
            raise ConnectionError(E_INVALID_BUFFER_TYPE, _error2string[E_INVALID_BUFFER_TYPE])
        return bytes(buffer, encoding)

    #
    # Decode a received buffer. Raise an exception when
    # buffer has an invalid type. When encoding is not
    # None, the buffer is decoded and the universal newlines
    # are replaced by '\n'. When encoding is None, return a
    # bytes object.
    #
    @staticmethod
    def _decode(buffer, encoding='utf8'):
        if not isinstance(buffer, (bytes, bytearray, memoryview)):
            raise ConnectionError(E_INVALID_BUFFER_TYPE, _error2string[E_INVALID_BUFFER_TYPE])
        if encoding is not None:
            decoded = StringIO(str(buffer, encoding, errors='replace'), newline=None)
            decoded = decoded.getvalue()
        else:
            decoded = bytes(buffer)
        return decoded

    #
    # Send buffer to peer. If the encoding is not None,
    # the buffer is encoded using the specified encoding.
    # Otherwise the buffer is expected to be a bytes-object.
    #
    def send(self, buffer, encoding='utf8'):
        raise NotImplementedError("%s: The send() method shall be implemented in a subclass" % type(self).__name__)

    #
    # Receive data from peer. If encoding is not None,
    # the buffer is decoded using the specified encoding.
    # Otherwise a bytes() object is returned.
    #
    def receive(self, buffer_size=1024, encoding='utf8'):
        raise NotImplementedError("%s: The receive() method shall be implemented in a subclass" % type(self).__name__)

    #
    # Receive a single line of text from peer. The encoding
    # must be a valid string and cannot be None. If buffer
    # size is None, the line length is unlimited. If a buffer
    # size is specified, the returned line may be truncated.
    # In this situation the line may not contain a newline
    # character.
    #
    def receive_line(self, buffer_size=None, encoding='utf8'):
        if encoding is None:
            raise ConnectionError(E_INVALID_ENCODING_NONE, _error2string[E_INVALID_ENCODING_NONE])
        if buffer_size is not None:
            buffer_size = max(1, buffer_size)                                          # Buffer size is at least 1 byte.
        nl = self._line_buffer.find('\n')
        while nl < 0:
            self._line_buffer += self.receive(encoding=encoding)
            nl = self._line_buffer.find('\n')
            if buffer_size is not None and len(self._line_buffer) > buffer_size and (nl > buffer_size or nl < 0):
                nl = buffer_size - 1
        line, self._line_buffer = self._line_buffer[:nl + 1], self._line_buffer[nl + 1:]
        return line

    #
    # Receive one or more lines of text from peer. The encoding
    # must be a valid string and cannot be None. If buffer
    # size is None, the line length is unlimited. If a buffer
    # size is specified, the returned line may be truncated.
    # In this situation the line may not contain a newline
    # character.
    #
    def receive_lines(self, buffer_size=None, encoding='utf8'):
        while True:
            yield self.receive_line(buffer_size, encoding)

    #
    # When True a disconnect is requested. This property should
    # be polled regularly.
    #
    @property
    def disconnect(self):
        raise NotImplementedError("%s: The disconnect() method shall be implemented in a subclass" % type(self).__name__)

    #
    # Poll the connection. Return a tuple holding two boolean
    # values: (read, write). When a value is True, the connection
    # is ready for reading and/or writing respectively.
    #
    def poll(self):
        raise NotImplementedError("%s: The poll() method shall be implemented in a subclass" % type(self).__name__)

    #
    # Return a connection instance corresponding to the specified connection
    # type. The specified server type is case insensitive and can be one of:
    #
    # * tcp : create a TCP/IP connection.
    # * unix: create a UNIX domain connection.
    # * serial: create a serial port connection.
    #
    @classmethod
    def create(cls, connection_type, *args, **kwargs):
        #
        # Avoid circular imports.
        #
        from .SocketConnection import _SocketConnection
        from .SerialConnection import _SerialConnection

        connection_type = connection_type.lower()
        _server_type2class = {
            'tcp': lambda socket, address, disconnect: _SocketConnection(socket, address, disconnect),
            'unix': lambda socket, address, disconnect: _SocketConnection(socket, address, disconnect),
            'serial': lambda serial, disconnect: _SerialConnection(serial, disconnect)
        }
        return _server_type2class[connection_type](*args, **kwargs)
