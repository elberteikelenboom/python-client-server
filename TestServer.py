from Server import Server


def handler(connection):
    connection.sendall('Hello\n')
    data = connection.receive()
    print(data)
    return 0


def main():
    # server = Server.create('tcp', handler, '127.0.0.1', 8080)
    # server = Server.create('unix', handler, '/home/elbert/server', max_connections=2)
    server = Server.create('serial', handler, '/dev/ttyUSB1', rtscts=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
