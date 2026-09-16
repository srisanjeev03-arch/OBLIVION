"""The Oblivion privileged execution boundary.

The unprivileged API describes work; this package decides whether to do it and
then does it. See ``docs/OBLIVION_DOCUMENTATION.md §24`` for the architecture and
``docs/OBLIVION_DOCUMENTATION.md §24`` for the protocol and its guarantees.

Application code should reach privileged operations through
:class:`~oblivion.privileged.client.PrivilegedClient` and nothing else.
"""

from oblivion.privileged.client import (
    PrivilegedClient,
    PrivilegedClientError,
    new_nonce,
)
from oblivion.privileged.protocol import (
    ALLOWED_PARAMS,
    DESTRUCTIVE_OPERATIONS,
    PROTOCOL_VERSION,
    READ_ONLY_OPERATIONS,
    PrivilegedOperation,
    PrivilegedRequest,
    PrivilegedResponse,
    ProtocolError,
    ResponseStatus,
)
from oblivion.privileged.service import (
    AuthenticationError,
    Capability,
    CapabilityState,
    PrivilegedService,
    PrivilegedServiceError,
    ReplayCache,
    RequestAuthenticator,
    ResponseAuthenticationError,
    ServiceConfig,
    ServiceState,
    build_service_from_env,
)
from oblivion.privileged.transport import (
    DEFAULT_PIPE_NAME,
    InProcessTransport,
    NamedPipeServer,
    NamedPipeTransport,
    PipeInstanceError,
    ServiceUnavailableError,
    Transport,
    TransportError,
)
from oblivion.privileged.validation import (
    OPERATION_PERMISSION,
    PrivilegedRequestValidator,
    ValidationOutcome,
)

__all__ = [
    "ALLOWED_PARAMS",
    "DEFAULT_PIPE_NAME",
    "DESTRUCTIVE_OPERATIONS",
    "OPERATION_PERMISSION",
    "PROTOCOL_VERSION",
    "READ_ONLY_OPERATIONS",
    "AuthenticationError",
    "Capability",
    "CapabilityState",
    "InProcessTransport",
    "NamedPipeServer",
    "NamedPipeTransport",
    "PipeInstanceError",
    "PrivilegedClient",
    "PrivilegedClientError",
    "PrivilegedOperation",
    "PrivilegedRequest",
    "PrivilegedRequestValidator",
    "PrivilegedResponse",
    "PrivilegedService",
    "PrivilegedServiceError",
    "ProtocolError",
    "ReplayCache",
    "RequestAuthenticator",
    "ResponseAuthenticationError",
    "ResponseStatus",
    "ServiceConfig",
    "ServiceState",
    "ServiceUnavailableError",
    "Transport",
    "TransportError",
    "ValidationOutcome",
    "build_service_from_env",
    "new_nonce",
]
