import serial
from .Errors import *
from .Errors import _error2string


# noinspection PyPep8Naming,PyUnusedLocal
def UNUSED(*args, **kwargs):
    pass


#
# Exception class to be generated by the Server package.
#
class ClientError(Exception):
    def __init__(self, error_code, message):
        super(ClientError, self).__init__(message)
        self.error_code = error_code


#
# Define the client base class.
#
class Client(object):
    def __init__(self, client_type, address, handler):
        if not callable(handler):
            raise ClientError(E_HANDLER_NOT_CALLABLE, _error2string[E_HANDLER_NOT_CALLABLE])
        self._client_type = client_type
        self._address = address
        self._handler = handler

    #
    # Connect to the server as long as the disconnect
    # callable returns False.
    #
    def connect(self, disconnect):
        NotImplementedError("%s: The connect() method shall be implemented in a subclass" % type(self).__name__)

    #
    # Return a client instance corresponding to the specified client type.
    # The specified client type is case insensitive and can be one of:
    #
    # * tcp : create a TCP/IP socket client.
    # * unix: create a UNIX domain socket client.
    # * serial: create a serial port client.
    #
    # noinspection SpellCheckingInspection
    @classmethod
    def create(cls, client_type, handler, *args, **kwargs):
        #
        # Avoid circular imports.
        #
        from .SocketClient import _TCPSocketClient, _UNIXSocketClient
        from .SerialClient import _SerialClient
        #
        # Map a server type to an instance of a corresponding server class.
        #
        client_type = client_type.lower()
        _server_type2class = {
            'tcp': lambda _handler, address, port, reconnect=None: _TCPSocketClient(client_type, _handler, address, port, reconnect),
            'unix': lambda _handler, path, reconnect=None: _UNIXSocketClient(client_type, _handler, path, reconnect),
            'serial': lambda _handler, port, reconnect=None, baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=None, xonxoff=False, rtscts=False, write_timeout=None, dsrdtr=False, inter_byte_timeout=None, exclusive=None: _SerialClient(client_type, _handler, reconnect, port, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts, write_timeout, dsrdtr, inter_byte_timeout, exclusive)
        }
        return _server_type2class[client_type](handler, *args, **kwargs)
