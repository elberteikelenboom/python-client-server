import logging
from Server import Server


def echo_server(connection):
    connection.send('Hello\n')
    for line in connection.receive_lines():
        if line.strip() == 'quit':
            break
        connection.send(line.upper())
    return 0


def main():
    logging.basicConfig(level=logging.INFO)
    server = Server.create_forking('tcp', echo_server, '127.0.0.1', 8080, max_connections=2)
    # server = Server.create_forking('unix', echo_server, '/home/elbert/server', max_connections=2)
    # server = Server.create_forking('serial', echo_server, '/dev/ttyUSB0', rtscts=True, baudrate=115200)
    # server = Server.create_threading('tcp', echo_server, '127.0.0.1', 8080, max_connections=2)
    # server = Server.create_threading('unix', echo_server, '/home/elbert/server', max_connections=2)
    # server = Server.create_threading('serial', echo_server, '/dev/ttyUSB0', rtscts=True, baudrate=115200)
    # server = Server.create_iterative('tcp', echo_server, '127.0.0.1', 8080)
    # server = Server.create_iterative('unix', echo_server, '/home/elbert/server')
    # server = Server.create_iterative('serial', echo_server, '/dev/ttyUSB0', rtscts=True, baudrate=115200)
    server.serve_forever()


if __name__ == '__main__':
    main()
