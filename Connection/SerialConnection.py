import errno
from threading import Lock
from serial.threaded import Protocol, ReaderThread
from serial import SerialException
from .Connection import Connection, ConnectionError
from .Errors import *
from .Errors import _error2string


#
# Define a protocol that simply stores the
# received data in a buffer.
#
class _BufferProtocol(Protocol):
    def __init__(self):
        super(_BufferProtocol, self).__init__()
        self._lock = Lock()
        self._buffer = bytearray()
        self._transport = None
        self._connection_reset = False

    #
    # Return the length of the receive buffer.
    #
    def __len__(self):
        return len(self._buffer)

    #
    # Called when a connection is made.
    #
    def connection_made(self, transport):
        self._transport = transport

    #
    # Called by the transport layer (thread) when bits of data
    # are received. Accumulate them in the receive buffer.
    #
    def data_received(self, data):
        with self._lock:
            self._buffer.extend(data)

    #
    # Called when the connection is lost from reader thread.
    #
    def connection_lost(self, exception):
        if exception is not None:
            if isinstance(exception, SerialException):
                self._connection_reset = True
            elif isinstance(exception, OSError):
                self._connection_reset = exception.errno in [errno.EBADF]
            else:
                raise exception

    #
    # Return true when the connection was lost
    # in the reader thread.
    #
    def connection_reset(self):
        return self._connection_reset

    #
    # Return max buffer size bytes from the
    # received buffer.
    #
    def read(self, buffer_size):
        with self._lock:
            buffer, self._buffer = self._buffer[:buffer_size], self._buffer[buffer_size:]
        return bytes(buffer)

    #
    # Use the transport layer to send the data.
    #
    def write(self, data):
        try:
            self._transport.write(data)                                # This function does not return the number of bytes send.
        except SerialException:
            raise ConnectionError(E_CONNECTION_RESET, _error2string[E_CONNECTION_RESET])
        return len(data)                                               # Assume all data has been written.


#
# Wrapper class around ReadThread in order to catch exceptions
# in the run() method and treat them as a connection lost error.
#
class ExceptionReaderThread(ReaderThread):
    def run(self):
        try:
            super(ExceptionReaderThread, self).run()
        except Exception as e:
            self.protocol.connection_lost(e)


#
# Define a serial connection. Reading the serial port
# is done in a separate thread by using ReaderThread()
#
class _SerialConnection(Connection):
    def __init__(self, serial_, disconnect):
        super(_SerialConnection, self).__init__()
        self._disconnect = disconnect
        self._transport = ExceptionReaderThread(serial_, _BufferProtocol)
        self._transport.start()
        self._transport, self._protocol = self._transport.connect()

    #
    # Stop the transport thread when the object is deleted.
    #
    def __del__(self):
        self._transport.stop()

    #
    # Send buffer to peer.
    #
    def send(self, buffer, encoding='utf8'):
        total = 0
        while total < len(buffer):
            while True:
                if self.disconnect:
                    raise ConnectionError(E_CONNECTION_ABORTED, _error2string[E_CONNECTION_ABORTED])
                read, write = self.poll()
                if write:
                    break                                                      # Serial connection ready for writing.
            sent = self._protocol.write(self._encode(buffer[total:], encoding))
            total += sent

    #
    # Receive data from peer.
    #
    def receive(self, buffer_size=1024, encoding='utf8'):
        while True:
            if self.disconnect:
                raise ConnectionError(E_CONNECTION_ABORTED, _error2string[E_CONNECTION_ABORTED])
            read, write = self.poll()
            if read:
                break                                                          # Serial connection ready for reading.
        buffer_size = max(1, buffer_size)                                      # Buffer size is at least 1 byte.
        return self._decode(self._protocol.read(buffer_size), encoding)

    #
    # Receive a single line of text from peer.
    #
    def receive_line(self, buffer_size=None, encoding='utf8'):
        return self._receive_line(1024, buffer_size, encoding)

    #
    # Return a tuple indicating whether or not the
    # connection is ready for reading and/or writing.
    #
    # Data can be read when there is data in the protocol receive buffer.
    # A serial connection is always ready for writing (Right?).
    #
    def poll(self):
        return len(self._protocol) != 0, True

    #
    # Return True when a disconnect is requested and
    # stop the transport thread. When the connection
    # is reset, the transport thread is already stopped
    # (because of an exception). Raise the connection
    # reset exception in the main thread to notify
    # the caller.
    #
    @property
    def disconnect(self):
        disconnect = self._disconnect()
        connection_reset = self._protocol.connection_reset()
        if disconnect or connection_reset:
            self._transport.stop()
        if connection_reset:
            raise ConnectionError(E_CONNECTION_RESET, _error2string[E_CONNECTION_RESET])
        return disconnect
