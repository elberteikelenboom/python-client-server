import os
import errno
import serial
from .Server import Server, Connection, UNUSED


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
    def sendall(self, buffer, encoding='utf8'):
        total = 0
        while total < len(buffer):
            sent = self._serial.write(self._encode(buffer[total:], encoding))
            total += sent

    #
    # Receive data from peer.
    #
    def receive(self, encoding='utf8'):
        return self._decode(self._serial.read(1), encoding)


#
# Define a serial server.
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
    # Run the socket server forever. For each connection fork()
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
            self._serial.open()
            pid = os.fork()
            if pid == 0:
                status = 0                                             # Path executed in the child process.
                try:
                    status = self._handler(_SerialConnection(self._serial))
                except Exception as e:
                    UNUSED(e)
                finally:
                    if not isinstance(status, int):
                        status = 0                                     # When status is not integral, overrule.
                    # noinspection PyProtectedMember
                    os._exit(status)                                   # Exit the child process.
            else:
                try:                                                   # Path executed in the parent process.
                    finished_pid, finished_status = os.waitpid(pid, 0)    # Wait until child process has finished before opening a new connection.
                    UNUSED(finished_pid, finished_status)              # Return values are not used at the moment.
                except OSError as e:
                    if e.errno != errno.ECHILD:
                        raise e
                    #
                    # The child as already exited, which is fine.
                    #
                finally:
                    self._close_connection()                           # When the child has exited, close the connection.
