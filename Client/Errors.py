E_INTEGRAL_PORT = 1
E_INVALID_IP_ADDRESS = 2
E_PATH_EXISTS_BUT_NOT_SOCKET = 3
E_HANDLER_NOT_CALLABLE = 4
E_PATH_DOES_NOT_EXIST = 5
E_PARAMETER_IS_NOT_CALLABLE = 6

_error2string = {
    E_INTEGRAL_PORT: "Port number shall be an integral, got: '%r'",
    E_INVALID_IP_ADDRESS: "Invalid IP-address, got: '%r'",
    E_PATH_EXISTS_BUT_NOT_SOCKET: "Path already exists but it is not a socket: '%s'",
    E_HANDLER_NOT_CALLABLE: "The handler is not callable",
    E_PATH_DOES_NOT_EXIST: "Path does not exist: '%s'",
    E_PARAMETER_IS_NOT_CALLABLE: "Callable expected for parameter: '%s'"
}
