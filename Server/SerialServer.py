import os
import errno
import serial
import threading
import logging
from .Server import Server, Connection, UNUSED

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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


#
# Define a serial server base class.
#
class _SerialServer(Server):
    #
    # Initialize serial port, but do not open it yet.
    #
    def __init__(self, handler, port, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts, write_timeout, dsrdtr, inter_byte_timeout, exclusive):
        super(_SerialServer, self).__init__(port, handler)
        self._serial = serial.Serial(None, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts, write_timeout, dsrdtr, inter_byte_timeout, exclusive)

    #
    # Close the connection and ignore any
    # errors while doing so.
    #
    def _close_connection(self):
        try:
            self._serial.close()
        except Exception as e:
            UNUSED(e)

    #
    # Abstract method that must be defined in a subclass.
    #
    def serve_forever(self):
        raise NotImplementedError("%s: The serve_forever() method shall be implemented in a subclass" % type(self).__name__)


#
# Define a forking serial server.
#
class _ForkingSerialServer(_SerialServer):
    #
    # Run the serial server forever. For each connection fork()
    # a new process and run the connection handler. Do not accept
    # more then 1 connection at the same time.
    #
    # When the handler exits, the connection is closed. When the handler
    # as an integral return value, it is returned to the parent process.
    # Otherwise the return value is set to 0.
    #
    def serve_forever(self):
        self._serial.port = self._address
        while True:
            logger.info("%s: serve_forever() -- Accepting connections at: %s.", type(self).__name__, str(self._address))
            self._serial.open()
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            pid = os.fork()
            if pid == 0:
                status = 0                                                     # Path executed in the child process.
                try:
                    logger.info("%s: serve_forever() -- Incoming connection.", type(self).__name__)
                    status = self._handler(_SerialConnection(self._serial))
                except Exception as e:
                    logger.exception("%s: serve_forever() -- %s", type(self).__name__, e)
                finally:
                    logger.info("%s: serve_forever() -- Closed connection.", type(self).__name__)
                    if not isinstance(status, int):
                        status = 0                                             # When status is not integral, overrule.
                    # noinspection PyProtectedMember
                    os._exit(status)                                           # Exit the child process.
            else:
                try:                                                           # Path executed in the parent process.
                    logger.info("%s: serve_forever() -- Maximum number of connections (%d) reached.", type(self).__name__, 1)
                    finished_pid, finished_status = os.waitpid(pid, 0)         # Wait until child process has finished before opening a new connection.
                    UNUSED(finished_pid, finished_status)                      # Return values are not used at the moment.
                except OSError as e:
                    if e.errno != errno.ECHILD:
                        raise e
                    #
                    # The child as already exited, which is fine.
                    #
                finally:
                    self._close_connection()                                   # When the child has exited, close the connection.


#
# Define a threading serial server.
#
class _ThreadingSerialServer(_SerialServer):
    #
    # Define the thread that runs the connection handler.
    #
    class HandlerThread(threading.Thread):
        # noinspection PyDefaultArgument
        def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, *, daemon=None):
            super(_ThreadingSerialServer.HandlerThread, self).__init__(group=group, target=None, name=name, args=args, kwargs=kwargs, daemon=daemon)
            self._connection, = args
            self._target = target
            self._status = 0

        #
        # Run the handler, catch the exit status and handle exceptions.
        #
        def run(self):
            try:
                self._status = self._target(self._connection)
            except Exception as e:
                logger.exception("%s: serve_forever() -- %s", type(self).__name__, e)
            finally:
                logger.info("%s: serve_forever() -- Closed connection.", type(self).__name__)
                if not isinstance(self._status, int):
                    self._status = 0

        #
        # Return the exit status of the handler.
        #
        @property
        def status(self):
            return self._status

    #
    # Run the serial server forever. For each connection create
    # a new thread and run the connection handler in it. Do not
    # accept more then 1 connection at the same time.
    #
    # When the handler exits, the connection is closed. When the handler
    # as an integral return value, it is returned to the parent process.
    # Otherwise the return value is set to 0.
    #
    def serve_forever(self):
        self._serial.port = self._address
        while True:
            logger.info("%s: serve_forever() -- Accepting connections at: %s.", type(self).__name__, str(self._address))
            self._serial.open()
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            logger.info("%s: serve_forever() -- Incoming connection.", type(self).__name__)
            thread = _ThreadingSerialServer.HandlerThread(target=self._handler, args=(_SerialConnection(self._serial),))
            logger.info("%s: serve_forever() -- Maximum number of connections (%d) reached.", type(self).__name__, 1)
            thread.start()
            thread.join()
            #
            # Here, thread.status contains the handler's exit status.
            #
            self._close_connection()                                           # When the child has exited, close the connection.


#
# Define a iterative serial server.
#
class _IterativeSerialServer(_SerialServer):
    #
    # Run the serial server forever. Accept a connection, handle it and
    # then handle the next connection. Do not fork() nor create threads.
    #
    # When the handler exits, the connection is closed. When the handler
    # as an integral return value, it is returned to the parent process.
    # Otherwise the return value is set to 0.
    #
    def serve_forever(self):
        self._serial.port = self._address
        while True:
            logger.info("%s: serve_forever() -- Accepting connections at: %s.", type(self).__name__, str(self._address))
            self._serial.open()
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            status = 0
            try:
                logger.info("%s: serve_forever() -- Incoming connection.", type(self).__name__)
                status = self._handler(_SerialConnection(self._serial))
            except Exception as e:
                logger.exception("%s: serve_forever() -- %s", type(self).__name__, e)
            finally:
                logger.info("%s: serve_forever() -- Closed connection.", type(self).__name__)
                self._close_connection()                                       # When the child has exited, close the connection.
                if not isinstance(status, int):
                    status = 0                                                 # When status is not integral, overrule.
            UNUSED(status)
