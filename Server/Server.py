import serial
from io import StringIO
from .Errors import *
from .Errors import _error2string


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
    # Return a forking server instance corresponding to the specified server type.
    # The specified server type is case insensitive and can be one of:
    #
    # * tcp : create a TCP/IP socket server.
    # * unix: create a UNIX domain socket server.
    # * serial: create a serial port server.
    #
    @classmethod
    def create_forking(cls, server_type, handler, *args, **kwargs):
        #
        # Avoid circular imports.
        #
        from .SocketServer import _ForkingTCPSocketServer, _ForkingUNIXSocketServer
        from .SerialServer import _ForkingSerialServer
        #
        # Map a server type to an instance of a corresponding server class.
        #
        _server_type2class = {
            'tcp': lambda _handler, address, port, max_connections=1: _ForkingTCPSocketServer(_handler, address, port, max_connections),
            'unix': lambda _handler, path, max_connections=1: _ForkingUNIXSocketServer(_handler, path, max_connections),
            'serial': lambda _handler, port, baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=None, xonxoff=False, rtscts=False, write_timeout=None, dsrdtr=False, inter_byte_timeout=None, exclusive=None: _ForkingSerialServer(_handler, port, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts, write_timeout, dsrdtr, inter_byte_timeout, exclusive)
        }
        return _server_type2class[server_type.lower()](handler, *args, **kwargs)

    #
    # Return a forking server instance corresponding to the specified server type.
    # The specified server type is case insensitive and can be one of:
    #
    # * tcp : create a TCP/IP socket server.
    # * unix: create a UNIX domain socket server.
    # * serial: create a serial port server.
    #
    @classmethod
    def create_threading(cls, server_type, handler, *args, **kwargs):
        #
        # Avoid circular imports.
        #
        from .SocketServer import _ThreadingTCPSocketServer, _ThreadingUNIXSocketServer
        from .SerialServer import _ThreadingSerialServer
        #
        # Map a server type to an instance of a corresponding server class.
        #
        _server_type2class = {
            'tcp': lambda _handler, address, port, max_connections=1: _ThreadingTCPSocketServer(_handler, address, port, max_connections),
            'unix': lambda _handler, path, max_connections=1: _ThreadingUNIXSocketServer(_handler, path, max_connections),
            'serial': lambda _handler, port, baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=None, xonxoff=False, rtscts=False, write_timeout=None, dsrdtr=False, inter_byte_timeout=None, exclusive=None: _ThreadingSerialServer(_handler, port, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts, write_timeout, dsrdtr, inter_byte_timeout, exclusive)
        }
        return _server_type2class[server_type.lower()](handler, *args, **kwargs)


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
            raise ServerError(E_INVALID_BUFFER_TYPE, _error2string[E_INVALID_BUFFER_TYPE])
        return bytes(buffer, encoding)

    #
    # Decode a received buffer. Raise an exception when
    # buffer has an invalid type. When encoding is not
    # None, the buffer is decoded and the universal newlines
    # are replaced by '\n'.
    #
    @staticmethod
    def _decode(buffer, encoding='utf8'):
        if not isinstance(buffer, (bytes, bytearray, memoryview)):
            raise ServerError(E_INVALID_BUFFER_TYPE, _error2string[E_INVALID_BUFFER_TYPE])
        if encoding is not None:
            decoded = StringIO(str(buffer, encoding, errors='replace'), newline=None)
            decoded = decoded.getvalue()
        else:
            decoded = bytes(buffer)
        return decoded

    #
    # Receive a single line of text from peer; read
    # max chunk-size bytes at once.
    #
    def _receive_line(self, chunk_size, buffer_size=None, encoding='utf8'):
        if buffer_size is not None:
            buffer_size = max(1, buffer_size)                                          # Buffer size is at least 1 byte.
        if encoding is None:
            raise ServerError(E_INVALID_ENCODING_NONE, _error2string[E_INVALID_ENCODING_NONE])
        nl = self._line_buffer.find('\n')
        while nl < 0:
            self._line_buffer += self.receive(chunk_size, encoding)
            nl = self._line_buffer.find('\n')
            if buffer_size is not None and len(self._line_buffer) > buffer_size and (nl > buffer_size or nl < 0):
                nl = buffer_size - 1
        line = self._line_buffer[:nl + 1]
        self._line_buffer = self._line_buffer[nl + 1:]
        return line

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
        raise NotImplementedError("%s: The receive_line() method shall be implemented in a subclass" % type(self).__name__)

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
