E_INVALID_BUFFER_TYPE = 1
E_INVALID_ENCODING_NONE = 2
E_PARAMETER_IS_NOT_CALLABLE = 3
E_CONNECTION_ABORTED = 4
E_CONNECTION_RESET = 5

_error2string = {
    E_INVALID_BUFFER_TYPE: "Invalid buffer type",
    E_INVALID_ENCODING_NONE: "The encoding cannot be None",
    E_PARAMETER_IS_NOT_CALLABLE: "Callable expected for parameter: '%s'",
    E_CONNECTION_ABORTED: "The connection is aborted by software",
    E_CONNECTION_RESET: "The connection was reset"
}
