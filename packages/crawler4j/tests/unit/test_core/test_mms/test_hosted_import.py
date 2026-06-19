from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from src.core.mms.ui.hosted_import import (
    HostedImportLimits,
    parse_clipboard_import_text,
    parse_import_file,
    parse_manual_json_import,
    redact_import_payload,
)


def test_parse_csv_file_builds_standard_import_payload(tmp_path: Path):
    csv_file = tmp_path / "accounts.csv"
    csv_file.write_bytes("手机号,姓名,cookie\n13800000000,Alice,token-1\n\n13900000000,Bob,token-2\n".encode())

    payload = parse_import_file(
        csv_file,
        target_type="ctrip_account",
        limits=HostedImportLimits(max_file_size_bytes=1024, max_rows=10),
        business_key_field="phone",
        field_mapping={"手机号": "phone", "姓名": "name", "cookie": "cookie"},
    )

    assert payload == {
        "source_type": "file",
        "source_name": "accounts.csv",
        "target_type": "ctrip_account",
        "rows": [
            {
                "source_row_no": 2,
                "business_key": "13800000000",
                "payload": {"phone": "13800000000", "name": "Alice", "cookie": "token-1"},
                "raw_payload": {"手机号": "13800000000", "姓名": "Alice", "cookie": "token-1"},
            },
            {
                "source_row_no": 4,
                "business_key": "13900000000",
                "payload": {"phone": "13900000000", "name": "Bob", "cookie": "token-2"},
                "raw_payload": {"手机号": "13900000000", "姓名": "Bob", "cookie": "token-2"},
            },
        ],
    }


def test_parse_clipboard_tsv_uses_clipboard_source_name():
    payload = parse_clipboard_import_text(
        "phone\tname\n13800000000\tAlice\n",
        target_type="web_account",
        limits=HostedImportLimits(max_rows=5),
        business_key_field="phone",
    )

    assert payload["source_type"] == "clipboard"
    assert payload["source_name"] == "clipboard"
    assert payload["rows"][0]["source_row_no"] == 2
    assert payload["rows"][0]["business_key"] == "13800000000"
    assert payload["rows"][0]["payload"] == {"phone": "13800000000", "name": "Alice"}


def test_parse_import_file_rejects_unsupported_type_and_oversized_file(tmp_path: Path):
    txt_file = tmp_path / "accounts.txt"
    txt_file.write_text("phone\n13800000000\n", encoding="utf-8")

    with pytest.raises(ValueError, match="只支持 .xlsx/.csv"):
        parse_import_file(txt_file, target_type="web_account", limits=HostedImportLimits())

    csv_file = tmp_path / "accounts.csv"
    csv_file.write_text("phone\n13800000000\n", encoding="utf-8")
    with pytest.raises(ValueError, match="超过大小限制"):
        parse_import_file(
            csv_file,
            target_type="web_account",
            limits=HostedImportLimits(max_file_size_bytes=4),
        )


def test_parse_import_file_rejects_duplicate_headers_and_row_limit(tmp_path: Path):
    duplicate_header_file = tmp_path / "duplicate.csv"
    duplicate_header_file.write_text("phone,phone\n13800000000,13900000000\n", encoding="utf-8")
    with pytest.raises(ValueError, match="重复"):
        parse_import_file(duplicate_header_file, target_type="web_account", limits=HostedImportLimits())

    too_many_rows_file = tmp_path / "too_many.csv"
    too_many_rows_file.write_text("phone\n13800000000\n13900000000\n", encoding="utf-8")
    with pytest.raises(ValueError, match="超过最大行数"):
        parse_import_file(
            too_many_rows_file,
            target_type="web_account",
            limits=HostedImportLimits(max_rows=1),
        )


def test_parse_xlsx_file_reads_first_sheet_without_openpyxl(tmp_path: Path):
    xlsx_file = tmp_path / "accounts.xlsx"
    _write_minimal_xlsx(
        xlsx_file,
        [
            ["phone", "name"],
            ["13800000000", "Alice"],
            ["13900000000", "Bob"],
        ],
    )

    payload = parse_import_file(
        xlsx_file,
        target_type="labor_account",
        limits=HostedImportLimits(max_file_size_bytes=4096, max_rows=5),
        business_key_field="phone",
    )

    assert payload["source_type"] == "file"
    assert payload["source_name"] == "accounts.xlsx"
    assert [row["source_row_no"] for row in payload["rows"]] == [2, 3]
    assert [row["business_key"] for row in payload["rows"]] == ["13800000000", "13900000000"]
    assert payload["rows"][1]["payload"] == {"phone": "13900000000", "name": "Bob"}


def test_parse_manual_json_import_accepts_row_payloads():
    payload = parse_manual_json_import(
        '[{"phone": "13800000000", "password": "p1"}]',
        target_type="web_account",
        business_key_field="phone",
    )

    assert payload["source_type"] == "manual"
    assert payload["rows"][0]["source_row_no"] == 1
    assert payload["rows"][0]["business_key"] == "13800000000"
    assert payload["rows"][0]["raw_payload"] == {"phone": "13800000000", "password": "p1"}


def test_redact_import_payload_masks_sensitive_fields_without_mutating_original():
    payload = {
        "source_type": "file",
        "source_name": "accounts.csv",
        "target_type": "web_account",
        "rows": [
            {
                "source_row_no": 2,
                "business_key": "u1",
                "payload": {"token": "abc", "name": "Alice"},
                "raw_payload": {"Cookie": "session=1", "password": "secret"},
            }
        ],
    }

    redacted = redact_import_payload(payload)

    assert redacted["rows"][0]["payload"] == {"token": "***", "name": "Alice"}
    assert redacted["rows"][0]["raw_payload"] == {"Cookie": "***", "password": "***"}
    assert payload["rows"][0]["payload"]["token"] == "abc"


def _write_minimal_xlsx(path: Path, rows: list[list[str]]) -> None:
    shared_values: list[str] = []
    shared_index: dict[str, int] = {}

    def shared(value: str) -> int:
        if value not in shared_index:
            shared_index[value] = len(shared_values)
            shared_values.append(value)
        return shared_index[value]

    sheet_rows: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row):
            cell_ref = f"{chr(ord('A') + column_index)}{row_index}"
            cells.append(f'<c r="{cell_ref}" t="s"><v>{shared(str(value))}</v></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    shared_strings = "".join(f"<si><t>{value}</t></si>" for value in shared_values)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
</Types>
""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>
""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
""",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
     count="{len(shared_values)}" uniqueCount="{len(shared_values)}">{shared_strings}</sst>
""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{''.join(sheet_rows)}</sheetData>
</worksheet>
""",
        )
