import serial
import time
import errno
import logging
from Connection import Connection, ConnectionError, E_CONNECTION_ABORTED, E_CONNECTION_RESET
from .Client import Client, ClientError, UNUSED
from .Errors import *
from .Errors import _error2string

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


#
# Define a serial server base class.
#
class _SerialClient(Client):
    #
    # Initialize serial port, but do not open it yet.
    #
    # noinspection SpellCheckingInspection
    def __init__(self, client_type, handler, reconnect, port, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts, write_timeout, dsrdtr, inter_byte_timeout, exclusive):
        super(_SerialClient, self).__init__(client_type, port, handler)
        self._reconnect = reconnect
        self._serial = serial.Serial(None, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts, write_timeout, dsrdtr, inter_byte_timeout, exclusive)

    #
    # Connect to the server, and run the specified handler for the
    # connection. When reconnect is set to None, no attempt is made
    # to reconnect when the connection is lost/refused; the exception
    # will be re-raised in this case. When the reconnect setting is a
    # float, automatically try to reconnect to the server. The reconnect
    # value is used to throttle the reconnection attempts.
    #
    # When the disconnect callable returns True, the client disconnects
    # from the server.
    #
    def connect(self, disconnect):
        if not callable(disconnect):
            raise ClientError(E_PARAMETER_IS_NOT_CALLABLE, _error2string[E_PARAMETER_IS_NOT_CALLABLE] % "disconnect")
        self._serial.port = self._address
        while not disconnect():
            try:
                self._serial.open()
            except serial.SerialException as e:
                if self._reconnect is not None and e.errno in [errno.ENOENT, errno.EACCES]:
                    logger.info("%s: connect() -- Service: %s not available, retrying in %f seconds.", type(self).__name__, str(self._address), self._reconnect)
                    time.sleep(self._reconnect)                                # Throttle the reconnection attempts.
                    continue
                raise e
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            logger.info("%s: connect() -- Connected to server.", type(self).__name__)
            status = 0
            try:
                #
                # Connected to server, call the connection handler.
                #
                self._handler(Connection.create(self._client_type, self._serial, disconnect))
            except ConnectionError as e:
                if e.error_code == E_CONNECTION_ABORTED:
                    logger.info("%s: connect() -- %s.", type(self).__name__, e)
                    break
                elif self._reconnect is not None and e.error_code == E_CONNECTION_RESET:
                    logger.info("%s: connect() -- Lost connection to server: %s, reconnecting in: %f seconds.", type(self).__name__, str(self._address), self._reconnect)
                    time.sleep(self._reconnect)                                    # Throttle reconnection attempts.
                    continue
                raise e                                                            # No reconnect requested, or not connection reset; re-raise the exception.
            finally:
                logger.info("%s: connect() --Closing the connection.", type(self).__name__)
                self._close_connection()                                           # When the child has exited, close the connection.
                if not isinstance(status, int):
                    status = 0                                                     # When status is not integral, overrule.
                UNUSED(status)                                                     # The returned status is currently not used.

    #
    # Close the connection and ignore any errors while doing so.
    #
    def _close_connection(self):
        try:
            self._serial.close()
        except Exception as e:
            UNUSED(e)
