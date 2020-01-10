import serial
import logging
from Connection import Connection
from .Client import Client, UNUSED

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


#
# Define a serial server base class.
#
class _SerialClient(Client):
    #
    # Initialize serial port, but do not open it yet.
    #
    def __init__(self, client_type, handler, port, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts, write_timeout, dsrdtr, inter_byte_timeout, exclusive):
        super(_SerialClient, self).__init__(client_type, port, handler)
        self._serial = serial.Serial(None, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts, write_timeout, dsrdtr, inter_byte_timeout, exclusive)

    def connect(self):
        self._serial.port = self._address
        self._serial.open()
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        logger.info("%s: connect() -- Connected to server.", type(self).__name__)
        status = 0
        try:
            #
            # Connected to server, call the connection handler.
            #
            self._handler(Connection.create(self._client_type, self._serial))
        finally:
            logger.info("%s: connect() -- Closing the connection.", type(self).__name__)
            self._close_connection()                                           # When the child has exited, close the connection.
            if not isinstance(status, int):
                status = 0  # When status is not integral, overrule.
            UNUSED(status)                                                     # The returned status is currently not used.

    #
    # Close the connection and ignore any errors while doing so.
    #
    def _close_connection(self):
        try:
            self._serial.close()
        except Exception as e:
            UNUSED(e)
