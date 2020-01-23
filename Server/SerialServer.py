import os
import errno
import serial
import threading
import logging
import time
from multiprocessing import Pipe
from Connection import Connection, ConnectionError, E_CONNECTION_ABORTED, E_CONNECTION_RESET
from .Server import Server, ServerError, UNUSED
from .Errors import *
from .Errors import _error2string

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


#
# Define a serial server base class.
#
class _SerialServer(Server):
    #
    # Initialize serial port, but do not open it yet.
    #
    # noinspection SpellCheckingInspection
    def __init__(self, server_type, handler, port, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts, write_timeout, dsrdtr, inter_byte_timeout, exclusive):
        super(_SerialServer, self).__init__(server_type, port, handler)
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
    # Abstract method that must be defined in a subclass.
    #
    def serve_until(self, serve):
        raise NotImplementedError("%s: The serve_until() method shall be implemented in a subclass" % type(self).__name__)


#
# Define a forking serial server.
#
class _ForkingSerialServer(_SerialServer):
    #
    # Return True when the parent process
    # requests a disconnect.
    #
    @staticmethod
    def _disconnect(pipe_read):
        #
        # Closure function.
        #
        # When the parent send the 'disconnect' message
        # this indicates that we are requested to disconnect
        # from the client and terminate the handler.
        #
        def _closure():
            disconnect = False
            if pipe_read.poll():
                message = pipe_read.recv_bytes()
                if message.decode() == 'disconnect':
                    disconnect = True
            return disconnect
        return _closure

    #
    # Run the serial server forever.
    #
    def serve_forever(self):
        self.serve_until(lambda: True)

    #
    # Run the serial server as long as the serve callable returns True.
    # For each connection fork() a new process and run the connection
    # handler. Do not accept more then 1 connection at the same time.
    #
    # When the handler exits, the connection is closed. When the handler
    # as an integral return value, it is returned to the parent process.
    # Otherwise the return value is set to 0.
    #
    def serve_until(self, serve):
        if not callable(serve):
            raise ServerError(E_PARAMETER_IS_NOT_CALLABLE, _error2string[E_PARAMETER_IS_NOT_CALLABLE] % "serve")
        self._serial.port = self._address
        while serve():
            logger.info("%s: serve_until() -- Waiting for connections at: %s.", type(self).__name__, str(self._address))
            try:
                self._serial.open()
            except serial.SerialException as e:
                if e.errno in [errno.ENOENT, errno.EACCES]:
                    time.sleep(1.0)
                    continue
                else:
                    raise e
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            pipe_read, pipe_write = Pipe(False)                                # Create an unidirectional pipe; only send data from parent to child process.
            pid = os.fork()
            if pid < 0:
                raise ServerError(E_PROCESS_CREATION_ERROR, _error2string[E_PROCESS_CREATION_ERROR])
            elif pid == 0:
                status = 0                                                     # Path executed in the child process.
                try:
                    try:
                        logger.info("%s: serve_until() -- Incoming connection.", type(self).__name__)
                        status = self._handler(Connection.create(self._server_type, self._serial, self._disconnect(pipe_read)))
                    except ConnectionError as e:
                        if e.error_code in [E_CONNECTION_RESET, E_CONNECTION_ABORTED]:
                            logger.info("%s: serve_until() -- %s.", type(self).__name__, e)
                        else:
                            raise e
                except Exception as e:
                    logger.exception("%s: serve_forever() -- %s.", type(self).__name__, e)
                finally:
                    logger.info("%s: serve_until() -- Closed connection.", type(self).__name__)
                    if not isinstance(status, int):
                        status = 0                                             # When status is not integral, overrule.
                    # noinspection PyProtectedMember
                    os._exit(status)                                           # Exit the child process.
            else:
                logger.info("%s: serve_until() -- Maximum number of connections (%d) reached.", type(self).__name__, 1)
                while serve():
                    finished_pid = 0
                    try:
                        finished_pid, finished_status = os.waitpid(pid, os.WNOHANG)
                    except OSError as e:
                        if e.errno != errno.ECHILD:
                            raise e
                        #
                        # The child process does not exist anymore, we
                        # can therefor break from the loop.
                        #
                        finished_pid = pid
                    finally:
                        if finished_pid != 0:
                            break
                pipe_write.send_bytes('disconnect'.encode())                   # Send the disconnect message.
                pipe_write.close()                                             # Close our end of the pipe.
                self._close_connection()                                       # When the child has exited, close the connection.


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
                try:
                    self._status = self._target(self._connection)
                except ConnectionError as e:
                    if e.error_code in [E_CONNECTION_RESET, E_CONNECTION_ABORTED]:
                        logger.info("%s: serve_until() -- %s.", type(self).__name__, e)
                    else:
                        raise e
            except Exception as e:
                logger.exception("%s: serve_until() -- %s.", type(self).__name__, e)
            finally:
                logger.info("%s: serve_until() -- Closed connection.", type(self).__name__)
                if not isinstance(self._status, int):
                    self._status = 0

        #
        # Return the exit status of the handler.
        #
        @property
        def status(self):
            return self._status

    #
    # Run the serial server forever.
    #
    def serve_forever(self):
        self.serve_until(lambda: True)

    #
    # Run the serial server as long as the serve callable returns True.
    # For each connection create a new thread and run the connection handler
    # in it. Do not accept more then 1 connection at the same time.
    #
    # When the handler exits, the connection is closed. When the handler
    # as an integral return value, it is returned to the parent process.
    # Otherwise the return value is set to 0.
    #
    def serve_until(self, serve):
        if not callable(serve):
            raise ServerError(E_PARAMETER_IS_NOT_CALLABLE, _error2string[E_PARAMETER_IS_NOT_CALLABLE] % "serve")
        self._serial.port = self._address
        while serve():
            logger.info("%s: serve_until() -- Waiting for connections at: %s.", type(self).__name__, str(self._address))
            try:
                self._serial.open()
            except serial.SerialException as e:
                if e.errno in [errno.ENOENT, errno.EACCES]:
                    time.sleep(1.0)
                    continue
                else:
                    raise e
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            logger.info("%s: serve_until() -- Incoming connection.", type(self).__name__)
            thread = _ThreadingSerialServer.HandlerThread(target=self._handler, args=(Connection.create(self._server_type, self._serial, lambda: not serve()),))
            logger.info("%s: serve_until() -- Maximum number of connections (%d) reached.", type(self).__name__, 1)
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
    # Run the serial server forever.
    #
    def serve_forever(self):
        self.serve_until(lambda: True)

    #
    # Run the serial server as long as the serve callable returns True.
    # Accept a connection, handle it and then handle the next connection.
    # Do not fork() nor create threads.
    #
    # When the handler exits, the connection is closed. When the handler
    # as an integral return value, it is returned to the parent process.
    # Otherwise the return value is set to 0.
    #
    def serve_until(self, serve):
        if not callable(serve):
            raise ServerError(E_PARAMETER_IS_NOT_CALLABLE, _error2string[E_PARAMETER_IS_NOT_CALLABLE] % "serve")
        self._serial.port = self._address
        while serve():
            logger.info("%s: serve_until() -- Waiting for connections at: %s.", type(self).__name__, str(self._address))
            try:
                self._serial.open()
            except serial.SerialException as e:
                if e.errno in [errno.ENOENT, errno.EACCES]:
                    time.sleep(1.0)
                    continue
                else:
                    raise e
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            status = 0
            try:
                try:
                    logger.info("%s: serve_until() -- Incoming connection.", type(self).__name__)
                    status = self._handler(Connection.create(self._server_type, self._serial, lambda: not serve()))
                except ConnectionError as e:
                    if e.error_code in [E_CONNECTION_RESET, E_CONNECTION_ABORTED]:
                        logger.info("%s: serve_until() -- %s.", type(self).__name__, e)
                    else:
                        raise e
            except Exception as e:
                logger.exception("%s: serve_until() -- %s.", type(self).__name__, e)
            finally:
                logger.info("%s: serve_until() -- Closed connection.", type(self).__name__)
                self._close_connection()                                       # When the child has exited, close the connection.
                if not isinstance(status, int):
                    status = 0                                                 # When status is not integral, overrule.
            UNUSED(status)
