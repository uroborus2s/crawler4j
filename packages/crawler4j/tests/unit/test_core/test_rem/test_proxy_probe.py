from src.core.rem.ip_pool import IPEntry
from src.core.rem.proxy_probe import ProxyProbeError, ProxyProbeHttpResponse, probe_ip_entry


def test_probe_ip_entry_returns_success_result_with_exit_ip_and_latency(monkeypatch):
    entry = IPEntry(
        address="10.0.0.8",
        port=8080,
        protocol="http",
        username="alice",
        password="secret",
    )

    perf_values = iter([10.0, 10.428])
    monkeypatch.setattr("src.core.rem.proxy_probe.time.perf_counter", lambda: next(perf_values))
    monkeypatch.setattr(
        "src.core.rem.proxy_probe._probe_via_proxy",
        lambda entry, timeout_s, target: ProxyProbeHttpResponse(  # noqa: ARG005
            status_code=200,
            reason="OK",
            body="8.8.8.8\n",
        ),
    )

    result = probe_ip_entry(entry)

    assert result.ok is True
    assert result.stage == "probe"
    assert result.exit_ip == "8.8.8.8"
    assert result.http_status == 200
    assert result.latency_ms == 428
    assert result.masked_proxy_url == "http://alice:***@10.0.0.8:8080"
    assert "出口 IP: 8.8.8.8" in result.summary_text
    assert "latency_ms: 428" in result.detail_text


def test_probe_ip_entry_returns_failure_result_when_proxy_probe_errors(monkeypatch):
    entry = IPEntry(
        address="10.0.0.9",
        port=1080,
        protocol="socks5",
    )

    perf_values = iter([20.0, 21.003])
    monkeypatch.setattr("src.core.rem.proxy_probe.time.perf_counter", lambda: next(perf_values))

    def _raise_probe_error(entry, timeout_s, target):  # noqa: ARG001
        raise ProxyProbeError("proxy_handshake", "SOCKS5 认证失败")

    monkeypatch.setattr("src.core.rem.proxy_probe._probe_via_proxy", _raise_probe_error)

    result = probe_ip_entry(entry)

    assert result.ok is False
    assert result.stage == "proxy_handshake"
    assert result.exit_ip is None
    assert result.latency_ms == 1003
    assert result.error_type == "ProxyProbeError"
    assert "SOCKS5 认证失败" in result.summary_text
    assert "stage: proxy_handshake" in result.detail_text
