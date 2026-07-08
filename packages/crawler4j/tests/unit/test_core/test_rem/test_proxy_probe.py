from src.core.rem.ip_pool import IPEntry
from src.core.rem.proxy_probe import (
    ProxyProbeError,
    ProxyProbeHttpResponse,
    probe_ip_entry,
    probe_ip_entry_geo,
)


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


def test_probe_ip_entry_geo_returns_exit_location_and_asn(monkeypatch):
    entry = IPEntry(
        address="10.0.0.10",
        port=8080,
        protocol="http",
    )

    monkeypatch.setattr("src.core.rem.proxy_probe.time.perf_counter", lambda: 10.0)
    monkeypatch.setattr(
        "src.core.rem.proxy_probe._probe_via_proxy",
        lambda entry, timeout_s, target: ProxyProbeHttpResponse(  # noqa: ARG005
            status_code=200,
            reason="OK",
            body=(
                '{"status":"success","query":"124.225.43.95","country":"China",'
                '"countryCode":"CN","regionName":"Hainan","city":"Haikou",'
                '"lat":20.0442,"lon":110.1999,'
                '"timezone":"Asia/Shanghai","as":"AS4134 CHINANET-BACKBONE",'
                '"isp":"China Telecom"}'
            ),
        ),
    )

    result = probe_ip_entry_geo(entry)

    assert result.ok is True
    assert result.exit_ip == "124.225.43.95"
    assert result.country_code == "CN"
    assert result.country == "China"
    assert result.region == "Hainan"
    assert result.city == "Haikou"
    assert result.latitude == 20.0442
    assert result.longitude == 110.1999
    assert result.timezone == "Asia/Shanghai"
    assert result.asn == "AS4134 CHINANET-BACKBONE"
    assert result.isp == "China Telecom"
    assert "出口位置: CN / Hainan / Haikou / Asia/Shanghai" in result.summary_text


def test_probe_ip_entry_geo_returns_failure_when_probe_service_fails(monkeypatch):
    entry = IPEntry(
        address="10.0.0.11",
        port=8080,
        protocol="http",
    )

    monkeypatch.setattr("src.core.rem.proxy_probe.time.perf_counter", lambda: 10.0)
    monkeypatch.setattr(
        "src.core.rem.proxy_probe._probe_via_proxy",
        lambda entry, timeout_s, target: ProxyProbeHttpResponse(  # noqa: ARG005
            status_code=200,
            reason="OK",
            body='{"status":"fail","message":"reserved range"}',
        ),
    )

    result = probe_ip_entry_geo(entry)

    assert result.ok is False
    assert result.stage == "parse_geo"
    assert result.exit_ip is None
    assert result.detail == "reserved range"
