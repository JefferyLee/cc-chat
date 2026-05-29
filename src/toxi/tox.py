"""Minimal ctypes binding to libtoxcore (see PRD §3.3, revised).

The PyPI `py-toxcore-c` 0.2.0 segfaults against toxcore 0.2.22 (tox_bootstrap /
tox_self_set_name crash), so we bind the stable C ABI directly. Only the handful
of functions the daemon needs are wrapped here.

Requires a system libtoxcore (macOS: `brew install toxcore`).
"""
import ctypes as _C
from ctypes.util import find_library

# --- constants (from tox.h) ---
ADDRESS_SIZE = 38       # TOX_ADDRESS_SIZE: 32-byte key + 4-byte nospam + 2-byte checksum
PUBLIC_KEY_SIZE = 32    # TOX_PUBLIC_KEY_SIZE

CONNECTION_NONE = 0
MESSAGE_TYPE_NORMAL = 0
NO_FRIEND = 0xFFFFFFFF   # sentinel returned by friend_add* / friend_by_public_key on failure
MAX_MESSAGE_LENGTH = 1372  # TOX_MAX_MESSAGE_LENGTH: cap on a single sent message (bytes)
SAVEDATA_TYPE_NONE = 0
SAVEDATA_TYPE_TOX_SAVE = 1


class ToxError(Exception):
    pass


def _load_libtoxcore() -> _C.CDLL:
    candidates = [
        find_library("toxcore"),
        "/opt/homebrew/opt/toxcore/lib/libtoxcore.dylib",  # Homebrew (Apple Silicon)
        "/usr/local/opt/toxcore/lib/libtoxcore.dylib",     # Homebrew (Intel)
        "libtoxcore.so.2",                                  # Linux
        "libtoxcore.so",
    ]
    for name in candidates:
        if not name:
            continue
        try:
            return _C.CDLL(name)
        except OSError:
            continue
    raise ToxError(
        "could not load libtoxcore — install it (macOS: `brew install toxcore`, "
        "Linux: your distro's toxcore package)"
    )


_lib = _load_libtoxcore()


def _setup_signatures(lib: _C.CDLL) -> None:
    lib.tox_options_new.restype = _C.c_void_p
    lib.tox_options_new.argtypes = [_C.c_void_p]
    lib.tox_options_free.argtypes = [_C.c_void_p]
    lib.tox_options_set_savedata_type.argtypes = [_C.c_void_p, _C.c_int]
    lib.tox_options_set_savedata_data.argtypes = [_C.c_void_p, _C.c_char_p, _C.c_size_t]

    lib.tox_new.restype = _C.c_void_p
    lib.tox_new.argtypes = [_C.c_void_p, _C.c_void_p]
    lib.tox_kill.argtypes = [_C.c_void_p]
    lib.tox_iterate.argtypes = [_C.c_void_p, _C.c_void_p]
    lib.tox_iteration_interval.restype = _C.c_uint32
    lib.tox_iteration_interval.argtypes = [_C.c_void_p]

    lib.tox_bootstrap.restype = _C.c_bool
    lib.tox_bootstrap.argtypes = [_C.c_void_p, _C.c_char_p, _C.c_uint16, _C.c_char_p, _C.c_void_p]

    lib.tox_self_get_address.argtypes = [_C.c_void_p, _C.c_char_p]
    lib.tox_self_get_connection_status.restype = _C.c_int
    lib.tox_self_get_connection_status.argtypes = [_C.c_void_p]

    lib.tox_self_set_name.restype = _C.c_bool
    lib.tox_self_set_name.argtypes = [_C.c_void_p, _C.c_char_p, _C.c_size_t, _C.c_void_p]
    lib.tox_self_get_name_size.restype = _C.c_size_t
    lib.tox_self_get_name_size.argtypes = [_C.c_void_p]
    lib.tox_self_get_name.argtypes = [_C.c_void_p, _C.c_char_p]

    lib.tox_get_savedata_size.restype = _C.c_size_t
    lib.tox_get_savedata_size.argtypes = [_C.c_void_p]
    lib.tox_get_savedata.argtypes = [_C.c_void_p, _C.c_char_p]

    lib.tox_friend_add.restype = _C.c_uint32
    lib.tox_friend_add.argtypes = [_C.c_void_p, _C.c_char_p, _C.c_char_p, _C.c_size_t, _C.c_void_p]
    lib.tox_friend_add_norequest.restype = _C.c_uint32
    lib.tox_friend_add_norequest.argtypes = [_C.c_void_p, _C.c_char_p, _C.c_void_p]
    lib.tox_friend_delete.restype = _C.c_bool
    lib.tox_friend_delete.argtypes = [_C.c_void_p, _C.c_uint32, _C.c_void_p]
    lib.tox_friend_by_public_key.restype = _C.c_uint32
    lib.tox_friend_by_public_key.argtypes = [_C.c_void_p, _C.c_char_p, _C.c_void_p]
    lib.tox_friend_send_message.restype = _C.c_uint32
    lib.tox_friend_send_message.argtypes = [
        _C.c_void_p, _C.c_uint32, _C.c_int, _C.c_char_p, _C.c_size_t, _C.POINTER(_C.c_int)
    ]


_setup_signatures(_lib)

# --- callback prototypes ---
_SELF_CONN_CB = _C.CFUNCTYPE(None, _C.c_void_p, _C.c_int, _C.c_void_p)
_FRIEND_REQ_CB = _C.CFUNCTYPE(None, _C.c_void_p, _C.POINTER(_C.c_uint8), _C.c_char_p, _C.c_size_t, _C.c_void_p)
_FRIEND_CONN_CB = _C.CFUNCTYPE(None, _C.c_void_p, _C.c_uint32, _C.c_int, _C.c_void_p)
_FRIEND_MSG_CB = _C.CFUNCTYPE(None, _C.c_void_p, _C.c_uint32, _C.c_int, _C.c_char_p, _C.c_size_t, _C.c_void_p)
_lib.tox_callback_self_connection_status.argtypes = [_C.c_void_p, _SELF_CONN_CB]
_lib.tox_callback_friend_request.argtypes = [_C.c_void_p, _FRIEND_REQ_CB]
_lib.tox_callback_friend_connection_status.argtypes = [_C.c_void_p, _FRIEND_CONN_CB]
_lib.tox_callback_friend_message.argtypes = [_C.c_void_p, _FRIEND_MSG_CB]


class Tox:
    """Owns a single toxcore instance. Not thread-safe; drive it from one thread."""

    def __init__(self, savedata: bytes | None = None):
        opts = _lib.tox_options_new(None)
        if not opts:
            raise ToxError("tox_options_new failed")
        self._savedata_buf = savedata  # keep referenced until tox_new reads it
        if savedata:
            _lib.tox_options_set_savedata_type(opts, SAVEDATA_TYPE_TOX_SAVE)
            _lib.tox_options_set_savedata_data(opts, savedata, len(savedata))
        self._ptr = _lib.tox_new(opts, None)
        _lib.tox_options_free(opts)
        if not self._ptr:
            raise ToxError("tox_new failed")
        self._cbs: dict[str, object] = {}  # keep CFUNCTYPE objects alive

    # --- lifecycle / event loop ---
    def iterate(self) -> None:
        _lib.tox_iterate(self._ptr, None)

    def iteration_interval(self) -> int:
        """Milliseconds to sleep before the next iterate()."""
        return _lib.tox_iteration_interval(self._ptr)

    def kill(self) -> None:
        if self._ptr:
            _lib.tox_kill(self._ptr)
            self._ptr = None

    # --- identity ---
    def self_get_address(self) -> bytes:
        buf = _C.create_string_buffer(ADDRESS_SIZE)
        _lib.tox_self_get_address(self._ptr, buf)
        return buf.raw

    def self_get_address_hex(self) -> str:
        return self.self_get_address().hex().upper()

    def self_get_connection_status(self) -> int:
        return _lib.tox_self_get_connection_status(self._ptr)

    def is_connected(self) -> bool:
        return self.self_get_connection_status() != CONNECTION_NONE

    def self_set_name(self, name: bytes) -> bool:
        return _lib.tox_self_set_name(self._ptr, name, len(name), None)

    def self_get_name(self) -> bytes:
        size = _lib.tox_self_get_name_size(self._ptr)
        if size == 0:
            return b""
        buf = _C.create_string_buffer(size)
        _lib.tox_self_get_name(self._ptr, buf)
        return buf.raw

    def get_savedata(self) -> bytes:
        size = _lib.tox_get_savedata_size(self._ptr)
        buf = _C.create_string_buffer(size)
        _lib.tox_get_savedata(self._ptr, buf)
        return buf.raw

    # --- DHT ---
    def bootstrap(self, host: str, port: int, public_key_hex: str) -> bool:
        return _lib.tox_bootstrap(
            self._ptr, host.encode(), port, bytes.fromhex(public_key_hex), None
        )

    # --- friends ---
    def friend_add(self, address: bytes, message: bytes) -> int:
        return _lib.tox_friend_add(self._ptr, address, message, len(message), None)

    def friend_add_norequest(self, public_key: bytes) -> int:
        return _lib.tox_friend_add_norequest(self._ptr, public_key, None)

    def friend_delete(self, friend_number: int) -> bool:
        return _lib.tox_friend_delete(self._ptr, friend_number, None)

    def friend_by_public_key(self, public_key: bytes) -> int:
        """Friend number for a known public key, or NO_FRIEND (0xFFFFFFFF)."""
        return _lib.tox_friend_by_public_key(self._ptr, public_key, None)

    def friend_send_message(self, friend_number: int, message: bytes,
                            msg_type: int = MESSAGE_TYPE_NORMAL) -> bool:
        """Returns True if toxcore accepted the message (friend was connected)."""
        err = _C.c_int(0)
        _lib.tox_friend_send_message(
            self._ptr, friend_number, msg_type, message, len(message), _C.byref(err)
        )
        return err.value == 0

    # --- callbacks ---
    # Each setter takes a Python callable with already-decoded arguments.
    def on_self_connection_status(self, fn) -> None:
        def trampoline(_t, status, _ud):
            fn(status)
        cb = _SELF_CONN_CB(trampoline)
        self._cbs["self_conn"] = cb
        _lib.tox_callback_self_connection_status(self._ptr, cb)

    def on_friend_request(self, fn) -> None:
        def trampoline(_t, pk_ptr, message, length, _ud):
            pk = bytes(pk_ptr[i] for i in range(PUBLIC_KEY_SIZE))
            fn(pk, message[:length])
        cb = _FRIEND_REQ_CB(trampoline)
        self._cbs["friend_req"] = cb
        _lib.tox_callback_friend_request(self._ptr, cb)

    def on_friend_connection_status(self, fn) -> None:
        def trampoline(_t, friend_number, status, _ud):
            fn(friend_number, status)
        cb = _FRIEND_CONN_CB(trampoline)
        self._cbs["friend_conn"] = cb
        _lib.tox_callback_friend_connection_status(self._ptr, cb)

    def on_friend_message(self, fn) -> None:
        def trampoline(_t, friend_number, msg_type, message, length, _ud):
            fn(friend_number, message[:length], msg_type)
        cb = _FRIEND_MSG_CB(trampoline)
        self._cbs["friend_msg"] = cb
        _lib.tox_callback_friend_message(self._ptr, cb)
