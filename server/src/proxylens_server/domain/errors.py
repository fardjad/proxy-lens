class ServerError(RuntimeError):
    pass


class ServerConflictError(ServerError):
    pass


class ServerNotFoundError(ServerError):
    pass
