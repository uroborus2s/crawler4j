from __future__ import annotations

import base64
import ipaddress
import json
import socket
import ssl
import time
from dataclasses import dataclass
from typing import Final

from src.core.foundation.logging import logger
from src.core.rem.ip_pool import IPEntry


DEFAULT_PROXY_PROBE_TIMEOUT_S: Final[float] = 8.0


@dataclass(frozen=True, slots=True)
class ProxyProbeTarget:
    host: str
    port: int
    path: str


DEFAULT_PROXY_PROBE_TARGET: Final[ProxyProbeTarget] = ProxyProbeTarget(
    host="api64.ipify.org",
    port=80,
    path="/",
)
DEFAULT_PROXY_GEO_PROBE_TARGET: Final[ProxyProbeTarget] = ProxyProbeTarget(
    host="ip-api.com",
    port=80,
    path="/json/?fields=status,message,query,country,countryCode,regionName,city,timezone,as,asname,isp",
)


@dataclass(frozen=True, slots=True)
class ProxyProbeHttpResponse:
    status_code: int
    reason: str
    body: str


@dataclass(frozen=True, slots=True)
class ProxyProbeResult:
    ok: bool
    stage: str
    protocol: str
    masked_proxy_url: str
    latency_ms: int
    exit_ip: str | None
    http_status: int | None
    detail: str
    error_type: str | None
    country_code: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    timezone: str | None = None
    asn: str | None = None
    isp: str | None = None

    @property
    def title(self) -> str:
        return "代理测试成功" if self.ok else "代理测试失败"

    @property
    def summary_text(self) -> str:
        lines = [
            f"代理地址: {self.masked_proxy_url}",
            f"耗时: {self.latency_ms} ms",
        ]
        if self.ok:
            lines.insert(0, f"出口 IP: {self.exit_ip or '-'}")
            if self.country_code or self.city or self.timezone:
                lines.append(
                    "出口位置: "
                    + " / ".join(
                        item
                        for item in (
                            self.country_code,
                            self.region,
                            self.city,
                            self.timezone,
                        )
                        if item
                    )
                )
        else:
            lines.insert(0, f"失败阶段: {self.stage}")
            lines.append(f"原因: {self.detail}")
        if self.http_status is not None:
            lines.append(f"HTTP 状态: {self.http_status}")
        return "\n".join(lines)

    @property
    def detail_text(self) -> str:
        lines = [
            f"ok: {self.ok}",
            f"stage: {self.stage}",
            f"protocol: {self.protocol}",
            f"masked_proxy_url: {self.masked_proxy_url}",
            f"latency_ms: {self.latency_ms}",
            f"exit_ip: {self.exit_ip or '-'}",
            f"country_code: {self.country_code or '-'}",
            f"country: {self.country or '-'}",
            f"region: {self.region or '-'}",
            f"city: {self.city or '-'}",
            f"timezone: {self.timezone or '-'}",
            f"asn: {self.asn or '-'}",
            f"isp: {self.isp or '-'}",
            f"http_status: {self.http_status if self.http_status is not None else '-'}",
            f"error_type: {self.error_type or '-'}",
            f"detail: {self.detail}",
        ]
        return "\n".join(lines)


class ProxyProbeError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


def probe_ip_entry(
    entry: IPEntry,
    *,
    timeout_s: float = DEFAULT_PROXY_PROBE_TIMEOUT_S,
    target: ProxyProbeTarget = DEFAULT_PROXY_PROBE_TARGET,
) -> ProxyProbeResult:
    return _probe_ip_entry(
        entry,
        timeout_s=timeout_s,
        target=target,
        parse_body=_extract_exit_ip_fields,
        success_detail="探针服务返回公网出口 IP",
    )


def probe_ip_entry_geo(
    entry: IPEntry,
    *,
    timeout_s: float = DEFAULT_PROXY_PROBE_TIMEOUT_S,
    target: ProxyProbeTarget = DEFAULT_PROXY_GEO_PROBE_TARGET,
) -> ProxyProbeResult:
    return _probe_ip_entry(
        entry,
        timeout_s=timeout_s,
        target=target,
        parse_body=_extract_geo_probe_fields,
        success_detail="探针服务返回公网出口 IP 与地理信息",
    )


def _probe_ip_entry(
    entry: IPEntry,
    *,
    timeout_s: float,
    target: ProxyProbeTarget,
    parse_body,
    success_detail: str,
) -> ProxyProbeResult:
    start = time.perf_counter()
    protocol = _normalize_protocol(entry.protocol)
    masked_proxy_url = _mask_proxy_url(entry, protocol)
    http_status: int | None = None

    try:
        _validate_entry(entry, protocol)
        response = _probe_via_proxy(entry, timeout_s=timeout_s, target=target)
        http_status = response.status_code
        if response.status_code != 200:
            preview = _preview_text(response.body)
            raise ProxyProbeError(
                "probe",
                f"探针服务返回 HTTP {response.status_code} {response.reason}: {preview}",
            )
        parsed = parse_body(response.body)
        latency_ms = _elapsed_ms(start)
        return ProxyProbeResult(
            ok=True,
            stage="probe",
            protocol=protocol,
            masked_proxy_url=masked_proxy_url,
            latency_ms=latency_ms,
            exit_ip=parsed.get("exit_ip"),
            http_status=http_status,
            detail=success_detail,
            error_type=None,
            country_code=parsed.get("country_code"),
            country=parsed.get("country"),
            region=parsed.get("region"),
            city=parsed.get("city"),
            timezone=parsed.get("timezone"),
            asn=parsed.get("asn"),
            isp=parsed.get("isp"),
        )
    except ProxyProbeError as exc:
        latency_ms = _elapsed_ms(start)
        logger.warning(f"[ProxyProbe] {masked_proxy_url} failed at {exc.stage}: {exc}")
        return ProxyProbeResult(
            ok=False,
            stage=exc.stage,
            protocol=protocol,
            masked_proxy_url=masked_proxy_url,
            latency_ms=latency_ms,
            exit_ip=None,
            http_status=http_status,
            detail=str(exc),
            error_type=type(exc).__name__,
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        latency_ms = _elapsed_ms(start)
        logger.exception(f"[ProxyProbe] unexpected failure for {masked_proxy_url}")
        detail = str(exc).strip() or "未提供异常消息"
        return ProxyProbeResult(
            ok=False,
            stage="unexpected",
            protocol=protocol,
            masked_proxy_url=masked_proxy_url,
            latency_ms=latency_ms,
            exit_ip=None,
            http_status=http_status,
            detail=detail,
            error_type=type(exc).__name__,
        )


def _probe_via_proxy(
    entry: IPEntry,
    *,
    timeout_s: float,
    target: ProxyProbeTarget,
) -> ProxyProbeHttpResponse:
    protocol = _normalize_protocol(entry.protocol)
    if protocol in {"http", "https"}:
        return _probe_via_http_proxy(entry, timeout_s=timeout_s, target=target)
    if protocol == "socks5":
        return _probe_via_socks5_proxy(entry, timeout_s=timeout_s, target=target)
    if protocol == "socks4":
        return _probe_via_socks4_proxy(entry, timeout_s=timeout_s, target=target)
    raise ProxyProbeError("validate", f"不支持的代理协议: {protocol}")


def _probe_via_http_proxy(
    entry: IPEntry,
    *,
    timeout_s: float,
    target: ProxyProbeTarget,
) -> ProxyProbeHttpResponse:
    sock = _open_proxy_socket(entry, timeout_s=timeout_s)
    try:
        request = _build_http_proxy_request(entry, target)
        _sendall(sock, request, stage="send_request", action="发送 HTTP 代理探针请求")
        return _read_http_response(sock, stage="probe")
    finally:
        sock.close()


def _probe_via_socks5_proxy(
    entry: IPEntry,
    *,
    timeout_s: float,
    target: ProxyProbeTarget,
) -> ProxyProbeHttpResponse:
    sock = _open_proxy_socket(entry, timeout_s=timeout_s)
    try:
        _perform_socks5_handshake(sock, entry, stage="proxy_handshake")
        _perform_socks5_connect(sock, entry, target, stage="proxy_handshake")
        request = _build_origin_http_request(target)
        _sendall(sock, request, stage="send_request", action="发送 SOCKS5 探针请求")
        return _read_http_response(sock, stage="probe")
    finally:
        sock.close()


def _probe_via_socks4_proxy(
    entry: IPEntry,
    *,
    timeout_s: float,
    target: ProxyProbeTarget,
) -> ProxyProbeHttpResponse:
    sock = _open_proxy_socket(entry, timeout_s=timeout_s)
    try:
        _perform_socks4_connect(sock, entry, target, stage="proxy_handshake")
        request = _build_origin_http_request(target)
        _sendall(sock, request, stage="send_request", action="发送 SOCKS4 探针请求")
        return _read_http_response(sock, stage="probe")
    finally:
        sock.close()


def _open_proxy_socket(entry: IPEntry, *, timeout_s: float) -> socket.socket:
    address = str(entry.address or "").strip()
    port = int(entry.port or 0)
    protocol = _normalize_protocol(entry.protocol)
    try:
        sock = socket.create_connection((address, port), timeout=timeout_s)
    except OSError as exc:
        raise ProxyProbeError("connect_proxy", f"连接代理失败: {exc}") from exc
    sock.settimeout(timeout_s)
    if protocol != "https":
        return sock

    tls_context = ssl.create_default_context()
    tls_context.check_hostname = False
    tls_context.verify_mode = ssl.CERT_NONE
    try:
        wrapped = tls_context.wrap_socket(sock, server_hostname=address or None)
    except Exception as exc:
        sock.close()
        raise ProxyProbeError("proxy_tls", f"连接 HTTPS 代理失败: {exc}") from exc
    wrapped.settimeout(timeout_s)
    return wrapped


def _build_http_proxy_request(entry: IPEntry, target: ProxyProbeTarget) -> bytes:
    headers = [
        f"GET http://{target.host}:{target.port}{target.path} HTTP/1.0",
        f"Host: {target.host}",
        "User-Agent: crawler4j-proxy-probe/1.0",
        "Accept: text/plain, application/json",
        "Connection: close",
    ]
    proxy_auth = _build_http_proxy_auth(entry)
    if proxy_auth:
        headers.append(f"Proxy-Authorization: {proxy_auth}")
    return ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8")


def _build_origin_http_request(target: ProxyProbeTarget) -> bytes:
    headers = [
        f"GET {target.path} HTTP/1.0",
        f"Host: {target.host}",
        "User-Agent: crawler4j-proxy-probe/1.0",
        "Accept: text/plain, application/json",
        "Connection: close",
    ]
    return ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8")


def _build_http_proxy_auth(entry: IPEntry) -> str | None:
    username = str(entry.username or "")
    password = str(entry.password or "")
    if not username and not password:
        return None
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _perform_socks5_handshake(sock: socket.socket, entry: IPEntry, *, stage: str) -> None:
    methods = [0x00]
    if entry.username or entry.password:
        methods.append(0x02)
    greeting = bytes([0x05, len(methods), *methods])
    _sendall(sock, greeting, stage=stage, action="发送 SOCKS5 握手请求")
    response = _recv_exact(sock, 2, stage=stage, action="读取 SOCKS5 握手响应")
    if response[0] != 0x05:
        raise ProxyProbeError(stage, "SOCKS5 握手失败: 非法版本")
    method = response[1]
    if method == 0xFF:
        raise ProxyProbeError(stage, "SOCKS5 握手失败: 代理不接受当前认证方式")
    if method == 0x02:
        username = str(entry.username or "")
        password = str(entry.password or "")
        if len(username.encode("utf-8")) > 255 or len(password.encode("utf-8")) > 255:
            raise ProxyProbeError("validate", "SOCKS5 用户名或密码过长")
        payload = bytearray([0x01, len(username.encode("utf-8"))])
        payload.extend(username.encode("utf-8"))
        payload.append(len(password.encode("utf-8")))
        payload.extend(password.encode("utf-8"))
        _sendall(sock, bytes(payload), stage=stage, action="发送 SOCKS5 认证请求")
        auth_response = _recv_exact(sock, 2, stage=stage, action="读取 SOCKS5 认证响应")
        if auth_response[1] != 0x00:
            raise ProxyProbeError(stage, "SOCKS5 认证失败")


def _perform_socks5_connect(
    sock: socket.socket,
    entry: IPEntry,
    target: ProxyProbeTarget,
    *,
    stage: str,
) -> None:
    host_bytes = target.host.encode("idna")
    request = bytearray([0x05, 0x01, 0x00, 0x03, len(host_bytes)])
    request.extend(host_bytes)
    request.extend(target.port.to_bytes(2, "big"))
    _sendall(sock, bytes(request), stage=stage, action="发送 SOCKS5 CONNECT 请求")
    header = _recv_exact(sock, 4, stage=stage, action="读取 SOCKS5 CONNECT 响应头")
    if header[0] != 0x05:
        raise ProxyProbeError(stage, "SOCKS5 CONNECT 失败: 非法版本")
    reply = header[1]
    if reply != 0x00:
        raise ProxyProbeError(stage, f"SOCKS5 CONNECT 失败: {_describe_socks5_reply(reply)}")
    atyp = header[3]
    if atyp == 0x01:
        _recv_exact(sock, 4, stage=stage, action="读取 SOCKS5 绑定地址")
    elif atyp == 0x03:
        domain_len = _recv_exact(sock, 1, stage=stage, action="读取 SOCKS5 域名长度")[0]
        _recv_exact(sock, domain_len, stage=stage, action="读取 SOCKS5 绑定域名")
    elif atyp == 0x04:
        _recv_exact(sock, 16, stage=stage, action="读取 SOCKS5 绑定地址")
    else:
        raise ProxyProbeError(stage, f"SOCKS5 CONNECT 失败: 未知地址类型 {atyp}")
    _recv_exact(sock, 2, stage=stage, action="读取 SOCKS5 绑定端口")


def _perform_socks4_connect(
    sock: socket.socket,
    entry: IPEntry,
    target: ProxyProbeTarget,
    *,
    stage: str,
) -> None:
    user_id = str(entry.username or "").encode("utf-8")
    host_bytes = target.host.encode("idna")
    payload = bytearray([0x04, 0x01])
    payload.extend(target.port.to_bytes(2, "big"))
    payload.extend(b"\x00\x00\x00\x01")
    payload.extend(user_id)
    payload.append(0x00)
    payload.extend(host_bytes)
    payload.append(0x00)
    _sendall(sock, bytes(payload), stage=stage, action="发送 SOCKS4 CONNECT 请求")
    response = _recv_exact(sock, 8, stage=stage, action="读取 SOCKS4 CONNECT 响应")
    if response[1] != 0x5A:
        raise ProxyProbeError(stage, f"SOCKS4 CONNECT 失败: {_describe_socks4_reply(response[1])}")


def _read_http_response(sock: socket.socket, *, stage: str) -> ProxyProbeHttpResponse:
    raw = _recv_until_close(sock, stage=stage, action="读取探针响应")
    separator = b"\r\n\r\n"
    if separator not in raw:
        raise ProxyProbeError(stage, "探针服务返回了无效 HTTP 响应")
    head, body = raw.split(separator, 1)
    try:
        lines = head.decode("iso-8859-1").split("\r\n")
    except UnicodeDecodeError as exc:
        raise ProxyProbeError(stage, f"探针响应头解码失败: {exc}") from exc
    if not lines or not lines[0]:
        raise ProxyProbeError(stage, "探针响应缺少状态行")
    parts = lines[0].split(" ", 2)
    if len(parts) < 2 or not parts[1].isdigit():
        raise ProxyProbeError(stage, f"探针响应状态行非法: {lines[0]}")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    if headers.get("transfer-encoding", "").lower() == "chunked":
        body = _decode_chunked_body(body, stage=stage)
    text = body.decode("utf-8", errors="replace").strip()
    return ProxyProbeHttpResponse(
        status_code=int(parts[1]),
        reason=parts[2].strip() if len(parts) > 2 else "",
        body=text,
    )


def _decode_chunked_body(body: bytes, *, stage: str) -> bytes:
    cursor = 0
    chunks = bytearray()
    while True:
        line_end = body.find(b"\r\n", cursor)
        if line_end < 0:
            raise ProxyProbeError(stage, "探针响应的 chunked body 非法")
        size_text = body[cursor:line_end].split(b";", 1)[0]
        try:
            chunk_size = int(size_text.decode("ascii"), 16)
        except ValueError as exc:
            raise ProxyProbeError(stage, "探针响应的 chunk size 非法") from exc
        cursor = line_end + 2
        if len(body) < cursor + chunk_size + 2:
            raise ProxyProbeError(stage, "探针响应的 chunked body 不完整")
        chunks.extend(body[cursor:cursor + chunk_size])
        cursor += chunk_size
        if body[cursor:cursor + 2] != b"\r\n":
            raise ProxyProbeError(stage, "探针响应缺少 chunk 分隔符")
        cursor += 2
        if chunk_size == 0:
            return bytes(chunks)


def _recv_until_close(sock: socket.socket, *, stage: str, action: str) -> bytes:
    chunks = bytearray()
    while True:
        try:
            chunk = sock.recv(4096)
        except socket.timeout as exc:
            raise ProxyProbeError(stage, f"{action}超时") from exc
        except OSError as exc:
            raise ProxyProbeError(stage, f"{action}失败: {exc}") from exc
        if not chunk:
            return bytes(chunks)
        chunks.extend(chunk)
        if len(chunks) > 512 * 1024:
            raise ProxyProbeError(stage, "探针响应过大，已停止读取")


def _recv_exact(sock: socket.socket, size: int, *, stage: str, action: str) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        try:
            chunk = sock.recv(size - len(chunks))
        except socket.timeout as exc:
            raise ProxyProbeError(stage, f"{action}超时") from exc
        except OSError as exc:
            raise ProxyProbeError(stage, f"{action}失败: {exc}") from exc
        if not chunk:
            raise ProxyProbeError(stage, f"{action}时连接已关闭")
        chunks.extend(chunk)
    return bytes(chunks)


def _sendall(sock: socket.socket, data: bytes, *, stage: str, action: str) -> None:
    try:
        sock.sendall(data)
    except socket.timeout as exc:
        raise ProxyProbeError(stage, f"{action}超时") from exc
    except OSError as exc:
        raise ProxyProbeError(stage, f"{action}失败: {exc}") from exc


def _extract_exit_ip(body: str) -> str:
    text = body.strip()
    if not text:
        raise ProxyProbeError("parse_exit_ip", "探针服务没有返回出口 IP")
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProxyProbeError("parse_exit_ip", f"探针 JSON 解析失败: {exc}") from exc
        text = str(payload.get("ip") or "").strip()
    try:
        ipaddress.ip_address(text)
    except ValueError as exc:
        raise ProxyProbeError(
            "parse_exit_ip",
            f"探针服务返回了非 IP 内容: {_preview_text(body)}",
        ) from exc
    return text


def _extract_exit_ip_fields(body: str) -> dict[str, str | None]:
    return {"exit_ip": _extract_exit_ip(body)}


def _extract_geo_probe_fields(body: str) -> dict[str, str | None]:
    text = body.strip()
    if not text:
        raise ProxyProbeError("parse_geo", "探针服务没有返回出口地理信息")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProxyProbeError("parse_geo", f"探针 JSON 解析失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProxyProbeError("parse_geo", "探针 JSON 不是对象")
    status = _clean_probe_text(payload.get("status")).lower()
    if status == "fail":
        message = _clean_probe_text(payload.get("message")) or "探针服务返回失败"
        raise ProxyProbeError("parse_geo", message)
    exit_ip = _clean_probe_text(payload.get("query")) or _clean_probe_text(payload.get("ip"))
    try:
        ipaddress.ip_address(exit_ip)
    except ValueError as exc:
        raise ProxyProbeError(
            "parse_geo",
            f"探针服务返回了非 IP 内容: {_preview_text(body)}",
        ) from exc
    country_code = _clean_probe_text(payload.get("countryCode")).upper() or None
    return {
        "exit_ip": exit_ip,
        "country_code": country_code,
        "country": _clean_probe_text(payload.get("country")) or None,
        "region": _clean_probe_text(payload.get("regionName")) or None,
        "city": _clean_probe_text(payload.get("city")) or None,
        "timezone": _clean_probe_text(payload.get("timezone")) or None,
        "asn": _clean_probe_text(payload.get("as")) or _clean_probe_text(payload.get("asname")) or None,
        "isp": _clean_probe_text(payload.get("isp")) or None,
    }


def _clean_probe_text(value: object) -> str:
    return str(value or "").strip()


def _mask_proxy_url(entry: IPEntry, protocol: str) -> str:
    auth = ""
    username = str(entry.username or "").strip()
    password = str(entry.password or "")
    if username and password:
        auth = f"{username}:***@"
    elif username:
        auth = f"{username}@"
    elif password:
        auth = "***@"
    return f"{protocol}://{auth}{str(entry.address or '').strip()}:{int(entry.port or 0)}"


def _validate_entry(entry: IPEntry, protocol: str) -> None:
    if protocol not in {"http", "https", "socks4", "socks5"}:
        raise ProxyProbeError("validate", f"不支持的代理协议: {protocol}")
    address = str(entry.address or "").strip()
    if not address:
        raise ProxyProbeError("validate", "代理地址不能为空")
    if not isinstance(entry.port, int) or entry.port <= 0 or entry.port > 65535:
        raise ProxyProbeError("validate", "代理端口必须在 1-65535 之间")


def _normalize_protocol(raw_protocol: str | None) -> str:
    return str(raw_protocol or "http").strip().lower() or "http"


def _elapsed_ms(start: float) -> int:
    return int(round((time.perf_counter() - start) * 1000))


def _preview_text(text: str, *, limit: int = 160) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _describe_socks5_reply(reply: int) -> str:
    mapping = {
        0x01: "一般性 SOCKS 服务故障",
        0x02: "规则集禁止访问",
        0x03: "网络不可达",
        0x04: "主机不可达",
        0x05: "目标拒绝连接",
        0x06: "TTL 已过期",
        0x07: "命令不受支持",
        0x08: "地址类型不受支持",
    }
    return mapping.get(reply, f"未知错误码 {reply}")


def _describe_socks4_reply(reply: int) -> str:
    mapping = {
        0x5B: "请求被拒绝或失败",
        0x5C: "SOCKS4 客户端未运行 identd",
        0x5D: "identd 返回的用户标识不匹配",
    }
    return mapping.get(reply, f"未知错误码 {reply}")
