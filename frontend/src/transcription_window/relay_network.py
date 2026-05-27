from __future__ import annotations

import json
import socket
import threading
import uuid
from typing import Callable, Optional


def _encode_payload(payload: dict) -> bytes:
    data = json.dumps(payload, ensure_ascii=True)
    return (data + "\n").encode("utf-8")


def _decode_payload(raw: bytes) -> Optional[dict]:
    if not raw:
        return None
    try:
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            return None
        return json.loads(text)
    except Exception:
        return None


class RelayServer:
    """Servidor simples de relay usando JSON por linha."""

    def __init__(self, host: str, port: int, on_status: Optional[Callable[[str], None]] = None):
        self.host = host
        self.port = port
        self._on_status = on_status
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._clients: set[socket.socket] = set()
        self._lock = threading.Lock()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(8)
        self._socket = server_socket
        self._running = True

        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        self._emit_status(f"Relay ativo em {self.host}:{self.port}.")

    def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass

        with self._lock:
            clients = list(self._clients)
            self._clients.clear()

        for client in clients:
            try:
                client.close()
            except OSError:
                pass

        self._emit_status("Relay encerrado.")

    def _accept_loop(self) -> None:
        if self._socket is None:
            return

        while self._running:
            try:
                client, _ = self._socket.accept()
            except OSError:
                break

            with self._lock:
                self._clients.add(client)

            threading.Thread(
                target=self._client_loop,
                args=(client,),
                daemon=True,
            ).start()

    def _client_loop(self, client: socket.socket) -> None:
        buffer = b""
        while self._running:
            try:
                data = client.recv(4096)
            except OSError:
                break

            if not data:
                break

            buffer += data
            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                payload = _decode_payload(raw_line)
                if payload is None:
                    continue
                self._broadcast(payload)

        with self._lock:
            self._clients.discard(client)
        try:
            client.close()
        except OSError:
            pass

    def _broadcast(self, payload: dict) -> None:
        message = _encode_payload(payload)
        with self._lock:
            clients = list(self._clients)

        to_remove = []
        for client in clients:
            try:
                client.sendall(message)
            except OSError:
                to_remove.append(client)

        if to_remove:
            with self._lock:
                for client in to_remove:
                    self._clients.discard(client)
                    try:
                        client.close()
                    except OSError:
                        pass

    def _emit_status(self, message: str) -> None:
        if self._on_status:
            self._on_status(message)


class RelayClient:
    """Cliente simples para envio/recebimento via relay."""

    def __init__(
        self,
        client_id: str,
        on_message: Callable[[str, str], None],
        on_status: Optional[Callable[[str], None]] = None,
    ):
        self.client_id = client_id
        self._on_message = on_message
        self._on_status = on_status
        self._socket: Optional[socket.socket] = None
        self._recv_thread: Optional[threading.Thread] = None
        self._running = False
        self._send_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    def connect(self, host: str, port: int, display_name: str) -> None:
        if self._running:
            return

        self._socket = socket.create_connection((host, port), timeout=3.0)
        self._socket.settimeout(1.0)
        self._running = True

        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

        self._send_payload(
            {
                "type": "hello",
                "client_id": self.client_id,
                "sender_name": display_name,
            }
        )
        self._emit_status(f"Conectado ao relay {host}:{port}.")

    def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

        self._emit_status("Relay desconectado.")

    def send_chunk(self, display_name: str, text: str) -> None:
        if not self._running or not text:
            return

        self._send_payload(
            {
                "type": "chunk",
                "sender_id": self.client_id,
                "sender_name": display_name,
                "text": text,
            }
        )

    def _recv_loop(self) -> None:
        if self._socket is None:
            return

        buffer = b""
        while self._running:
            try:
                data = self._socket.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            if not data:
                break

            buffer += data
            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                payload = _decode_payload(raw_line)
                if not payload:
                    continue

                if payload.get("type") != "chunk":
                    continue

                if payload.get("sender_id") == self.client_id:
                    continue

                sender_name = str(payload.get("sender_name") or "Remoto")
                text = str(payload.get("text") or "")
                if text:
                    self._on_message(sender_name, text)

        self._running = False
        self._emit_status("Conexao encerrada.")

    def _send_payload(self, payload: dict) -> None:
        if not self._socket:
            return

        data = _encode_payload(payload)
        with self._send_lock:
            try:
                self._socket.sendall(data)
            except OSError:
                self.stop()

    def _emit_status(self, message: str) -> None:
        if self._on_status:
            self._on_status(message)


class RelayNode:
    """Coordena servidor (host) e cliente de relay."""

    def __init__(
        self,
        on_message: Callable[[str, str], None],
        on_status: Optional[Callable[[str], None]] = None,
    ):
        self._on_message = on_message
        self._on_status = on_status
        self._client_id = uuid.uuid4().hex
        self._server: Optional[RelayServer] = None
        self._client: Optional[RelayClient] = None
        self._mode = "off"

    @property
    def is_active(self) -> bool:
        return self._client is not None and self._client.is_running

    def start(self, mode: str, host: str, port: int, display_name: str) -> None:
        normalized = (mode or "off").strip().lower()
        if normalized in {"off", "disabled", "desativado"}:
            self._mode = "off"
            return

        self._mode = normalized
        if normalized == "host":
            self._server = RelayServer(host="0.0.0.0", port=port, on_status=self._on_status)
            try:
                self._server.start()
            except OSError as exc:
                self._emit_status(f"Nao foi possivel iniciar relay: {exc}.")
                self._server = None

        self._client = RelayClient(
            client_id=self._client_id,
            on_message=self._on_message,
            on_status=self._on_status,
        )

        relay_host = host or "127.0.0.1"
        try:
            self._client.connect(relay_host, port, display_name)
        except OSError as exc:
            self._emit_status(f"Falha ao conectar ao relay: {exc}.")
            self.stop()

    def stop(self) -> None:
        if self._client:
            self._client.stop()
            self._client = None

        if self._server:
            self._server.stop()
            self._server = None

        self._mode = "off"

    def send_chunk(self, display_name: str, text: str) -> None:
        if self._client:
            self._client.send_chunk(display_name, text)

    def _emit_status(self, message: str) -> None:
        if self._on_status:
            self._on_status(message)
