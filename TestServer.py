import logging
from Server import Server


def echo_server(connection):
    connection.send('Hello\n')
    for line in connection.receive_lines():
        if line.strip() == 'quit':
            break
        connection.send(line)
    return 0


def main():
    logging.basicConfig(level=logging.INFO)
    server = Server.create('tcp', echo_server, '127.0.0.1', 8080, max_connections=2)
    # server = Server.create('unix', echo_server, '/home/elbert/server', max_connections=2)
    # server = Server.create('serial', echo_server, '/dev/ttyUSB0', rtscts=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
