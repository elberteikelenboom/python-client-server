import logging
from Client import Client


def handler(connection):
    buffer = []
    with open('./TestClient.py') as fp:
        for line in fp:
            connection.send(line)
            buffer.append(connection.receive_line())
        connection.send('quit\n')
    print(''.join(buffer))


def main():
    logging.basicConfig(level=logging.INFO)
    client = Client.create('tcp', handler, '127.0.0.1', 8080, 5.0)
    # client = Client.create('unix', handler, '/home/elbert/server', 5.0)
    # client = Client.create('serial', handler, '/dev/ttyUSB1', rtscts=True, baudrate=115200)
    client.connect()


if __name__ == '__main__':
    main()

