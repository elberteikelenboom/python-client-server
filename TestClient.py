import sys
import threading
import time
import logging
from Client import Client


def handler(connection):
    while True:
        with open('./TestClient.py') as fp:
            for line in fp:
                time.sleep(0.1)
                connection.send(line)
                sys.stdout.write(connection.receive_line())
        time.sleep(1.0)


class TimedClient(threading.Thread):
    def __init__(self, **kwargs):
        super(TimedClient, self).__init__(**kwargs)
        self._keep_running = False
#       self._client = Client.create('tcp', handler, '127.0.0.1', 8080, 1.5)
        self._client = Client.create('serial', handler, '/dev/ttyUSB1', 1.5)

    def start(self):
        self._keep_running = True
        super(TimedClient, self).start()

    def run(self):
        self._client.connect(lambda: not self._keep_running)

    def stop(self):
        self._keep_running = False


def main():
    logging.basicConfig(level=logging.INFO)
    # client = Client.create('unix', handler, '/home/elbert/server', 5.0)
    # client = Client.create('serial', handler, '/dev/ttyUSB1', rtscts=True, baudrate=115200)
    client = TimedClient()
    client.start()
    time.sleep(60.0)
    client.stop()


if __name__ == '__main__':
    main()

