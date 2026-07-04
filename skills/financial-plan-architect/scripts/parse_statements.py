#!/usr/bin/env python3
"""
parse_statements.py -- CSV / OFX (QFX) / XLSX statement intake for financial-plan-architect.

Python 3.10, stdlib only (csv, re, json, argparse, zipfile, xml.etree.ElementTree).

Usage:
    python parse_statements.py <file1> [file2 ...] --out plan_inputs.json

Produces a JSON document with `accounts`, `transactions`, `holdings` arrays shaped to
match references/plan-model.md. This script NEVER logs or stores a full account number --
every account identifier is masked to last-4 before it leaves this process.

Hard rule: no credentials are ever read, requested, or stored by this script. It only
parses files the user has already exported/handed over.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #

def mask_account(raw: Optional[str]) -> Optional[str]:
    """Mask any account-number-looking string to last 4 characters. Never returns
    or logs the full value."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) >= 4:
        return digits[-4:]
    # Not numeric / too short -- still truncate defensively, never echo raw.
    s = str(raw).strip()
    return s[-4:] if len(s) >= 4 else s


def parse_amount(raw: str) -> Optional[float]:
    """Parse amounts like '$1,234.56', '(45.00)', '-12.30', '1234.56 CR', '1,234.56-'."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "" or s.upper() in ("N/A", "NA", "-"):
        return None

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]

    # Trailing sign (some exports: "123.45-") or trailing CR/DR markers.
    s_upper = s.upper()
    if s_upper.endswith("DR"):
        negative = True
        s = s[:-2]
    elif s_upper.endswith("CR"):
        s = s[:-2]

    s = s.strip()
    if s.endswith("-"):
        negative = True
        s = s[:-1]
    if s.startswith("-"):
        negative = True
        s = s[1:]
    if s.startswith("+"):
        s = s[1:]

    s = s.replace("$", "").replace(",", "").strip()
    if s == "":
        return None
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if negative else val


DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%m-%d-%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d-%b-%Y",
    "%Y%m%d",
]


def parse_date(raw: str) -> Optional[str]:
    """Parse a date string into ISO YYYY-MM-DD. Returns None if unparseable."""
    if not raw:
        return None
    s = str(raw).strip()
    # OFX-style timestamps: 20260615120000[-5:EST] or 20260615
    m = re.match(r"^(\d{8})", s)
    if m and (len(s) == 8 or s[8:9] in ("", "T") or not s[8:9].isalpha() or True):
        candidate = m.group(1)
        try:
            dt = datetime.strptime(candidate, "%Y%m%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            # 2-digit year heuristic: assume 2000s
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------- #
# Categorization
# --------------------------------------------------------------------------- #

# Ordered rule table: (category, [regex keywords]). First match wins. Easy to extend --
# add a tuple anywhere in the list. Keep transfer-looking patterns distinct so callers
# can also set is_transfer independently.
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("income", [
        r"\bpayroll\b", r"\bdirect ?dep\b", r"\bdirect deposit\b", r"\bsalary\b",
        r"\bpaycheck\b", r"\bemployer\b", r"\bACH CREDIT\b", r"\breimbursement\b",
        r"\bdividend\b", r"\binterest paid\b", r"\btax refund\b", r"\birs treas\b",
    ]),
    ("transfer", [
        r"\btransfer\b", r"\bxfer\b", r"\bzelle\b", r"\bvenmo\b", r"\bcash ?app\b",
        r"\bpaypal transfer\b", r"\bach transfer\b", r"\bonline transfer\b",
        r"\bto savings\b", r"\bfrom savings\b", r"\bto checking\b", r"\bfrom checking\b",
        r"\bmove(d)? money\b", r"\bwire transfer\b", r"\bautopay.*(payment)\b",
    ]),
    ("credit_card_payment", [
        r"\bcredit card payment\b", r"\bcard ?payment\b", r"\bpayment ?thank ?you\b",
        r"\bcapital ?one (?:crcardpmt|payment)\b", r"\bamex.*payment\b",
        r"\bdiscover.*payment\b", r"\bchase.*payment\b",
    ]),
    ("groceries", [
        r"\bharris teeter\b", r"\bkroger\b", r"\bpublix\b", r"\btrader joe'?s\b",
        r"\bwhole foods\b", r"\baldi\b", r"\bfood lion\b", r"\bwalmart grocery\b",
        r"\bsafeway\b", r"\bgrocery\b", r"\bsupermarket\b", r"\bwinn-dixie\b",
    ]),
    ("dining", [
        r"\brestaurant\b", r"\bstarbucks\b", r"\bmcdonald'?s\b", r"\bchipotle\b",
        r"\bdoordash\b", r"\bgrubhub\b", r"\buber ?eats\b", r"\bpizza\b",
        r"\bcafe\b", r"\bcoffee\b", r"\bdiner\b", r"\bbar ?& ?grill\b", r"\bbrewery\b",
        r"\btaco\b", r"\bwaffle house\b",
    ]),
    ("gas", [
        r"\bshell\b", r"\bexxon\b", r"\bchevron\b", r"\bbp#\b", r"\bcircle k\b",
        r"\bspeedway\b", r"\bgas station\b", r"\bfuel\b", r"\bmurphy usa\b",
        r"\bwawa\b", r"\bquiktrip\b", r"\bqt\b",
    ]),
    ("utilities", [
        r"\belectric\b", r"\bpower ?co\b", r"\bwater ?(bill|utility)\b", r"\bduke energy\b",
        r"\bnatural gas\b", r"\bpiedmont natural\b", r"\bsewer\b", r"\btrash\b",
        r"\bwaste management\b", r"\binternet\b", r"\bspectrum\b", r"\bxfinity\b",
        r"\bcomcast\b", r"\bat&t\b", r"\bverizon\b", r"\bcellular\b", r"\butility\b",
    ]),
    ("insurance", [
        r"\binsurance\b", r"\bgeico\b", r"\bstate farm\b", r"\bprogressive\b",
        r"\ballstate\b", r"\bliberty mutual\b", r"\bhealth ?plan premium\b",
    ]),
    ("subscriptions", [
        r"\bnetflix\b", r"\bspotify\b", r"\bhulu\b", r"\bdisney\+\b", r"\bapple\.com/bill\b",
        r"\bamazon prime\b", r"\bicloud\b", r"\byoutube premium\b", r"\bpatreon\b",
        r"\bsubscription\b", r"\bgym membership\b", r"\bplanet fitness\b",
    ]),
    ("housing", [
        r"\brent\b", r"\bmortgage\b", r"\blandlord\b", r"\bhoa\b", r"\bapartment\b",
    ]),
    ("healthcare", [
        r"\bpharmacy\b", r"\bcvs\b", r"\bwalgreens\b", r"\bcopay\b", r"\bdoctor\b",
        r"\bdental\b", r"\bmedical\b", r"\bclinic\b", r"\burgent care\b",
    ]),
    ("shopping", [
        r"\bamazon\b", r"\btarget\b", r"\bwalmart\b", r"\bbest buy\b", r"\bebay\b",
        r"\betsy\b",
    ]),
    ("entertainment", [
        r"\bmovie\b", r"\bcinema\b", r"\bamc\b", r"\bconcert\b", r"\bticketmaster\b",
        r"\bsteam\b", r"\bplaystation\b", r"\bxbox\b",
    ]),
    ("travel", [
        r"\bairline\b", r"\bdelta air\b", r"\buber\b", r"\blyft\b", r"\bhotel\b",
        r"\bairbnb\b", r"\bmarriott\b", r"\bexpedia\b", r"\brental car\b",
    ]),
    ("fees", [
        r"\boverdraft\b", r"\bmaintenance fee\b", r"\bservice charge\b", r"\batm fee\b",
        r"\blate fee\b", r"\bnsf fee\b",
    ]),
]

TRANSFER_KEYWORDS = CATEGORY_RULES[1][1]  # reuse the "transfer" rule list


def categorize(description: str, amount: Optional[float]) -> tuple[str, bool]:
    """Return (category, is_transfer) for a transaction description."""
    desc = (description or "").lower()

    is_transfer = any(re.search(pat, desc, re.IGNORECASE) for pat in TRANSFER_KEYWORDS)

    for category, patterns in CATEGORY_RULES:
        for pat in patterns:
            if re.search(pat, desc, re.IGNORECASE):
                if category == "transfer":
                    is_transfer = True
                return category, is_transfer

    # Fallback: sign-based guess.
    if amount is not None and amount > 0:
        return "income", is_transfer
    return "uncategorized", is_transfer


# --------------------------------------------------------------------------- #
# Data holders
# --------------------------------------------------------------------------- #

@dataclass
class ParseResult:
    accounts: list[dict] = field(default_factory=list)
    transactions: list[dict] = field(default_factory=list)
    holdings: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_account_counter = [0]
_txn_counter = [0]


def next_account_id() -> str:
    _account_counter[0] += 1
    return f"a{_account_counter[0]}"


# --------------------------------------------------------------------------- #
# CSV parsing
# --------------------------------------------------------------------------- #

HEADER_ALIASES = {
    "date": {"date", "transaction date", "posted date", "post date", "trans date", "posting date"},
    "description": {"description", "memo", "payee", "name", "merchant", "details", "transaction"},
    "amount": {"amount", "transaction amount", "amt"},
    "debit": {"debit", "withdrawal", "withdrawals", "debit amount", "money out"},
    "credit": {"credit", "deposit", "deposits", "credit amount", "money in"},
    "category": {"category", "type"},
    "account": {"account", "account name", "account number", "account #"},
    "balance": {"balance", "running balance"},
}


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def _map_headers(fieldnames: list[str]) -> dict[str, str]:
    """Map canonical field -> actual CSV column name, via header heuristics."""
    norm_map = {_norm_header(f): f for f in fieldnames}
    result: dict[str, str] = {}
    for canonical, aliases in HEADER_ALIASES.items():
        for norm_name, actual in norm_map.items():
            if norm_name in aliases:
                result[canonical] = actual
                break
    return result


def sniff_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel  # fallback: comma


def parse_csv(path: str, result: ParseResult) -> None:
    with open(path, "r", encoding="utf-8-sig", newline="", errors="replace") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = sniff_dialect(sample)
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            result.warnings.append(f"{path}: no header row detected, skipped")
            return

        colmap = _map_headers(reader.fieldnames)
        if "date" not in colmap or ("amount" not in colmap and "debit" not in colmap and "credit" not in colmap):
            result.warnings.append(
                f"{path}: could not identify date/amount columns from header "
                f"{reader.fieldnames}; skipped"
            )
            return

        account_name = f"Imported ({path.split('/')[-1].split(chr(92))[-1]})"
        account_id = next_account_id()
        mask = None
        if "account" in colmap:
            pass  # account column usually holds a name, not a number; leave mask None

        result.accounts.append({
            "id": account_id,
            "name": account_name,
            "institution": None,
            "mask": mask,
            "type": "checking",
            "balance": None,
            "as_of": None,
            "apr_or_apy": None,
            "is_liability": False,
            "source": "export",
        })

        running_balance_seen = None
        for row in reader:
            date_raw = row.get(colmap.get("date", ""), "")
            date_iso = parse_date(date_raw)
            desc = row.get(colmap.get("description", ""), "") or ""

            amount = None
            if "amount" in colmap:
                amount = parse_amount(row.get(colmap["amount"], ""))
            else:
                debit = parse_amount(row.get(colmap.get("debit", ""), "")) if "debit" in colmap else None
                credit = parse_amount(row.get(colmap.get("credit", ""), "")) if "credit" in colmap else None
                if debit:
                    amount = -abs(debit)
                elif credit:
                    amount = abs(credit)

            if date_iso is None or amount is None:
                continue

            if "balance" in colmap:
                bal = parse_amount(row.get(colmap["balance"], ""))
                if bal is not None:
                    running_balance_seen = (date_iso, bal)

            category, is_transfer = categorize(desc, amount)
            is_income = amount > 0 and category == "income"

            result.transactions.append({
                "date": date_iso,
                "account_id": account_id,
                "amount": round(amount, 2),
                "description": desc.strip(),
                "category": category,
                "is_income": is_income,
                "is_transfer": is_transfer,
            })

        if running_balance_seen:
            as_of, bal = running_balance_seen
            result.accounts[-1]["balance"] = bal
            result.accounts[-1]["as_of"] = as_of


# --------------------------------------------------------------------------- #
# OFX / QFX parsing (SGML-ish, not necessarily well-formed XML)
# --------------------------------------------------------------------------- #

STMTTRN_FIELD_RE = re.compile(
    r"<(TRNTYPE|DTPOSTED|TRNAMT|FITID|NAME|MEMO|PAYEE)>\s*([^\r\n<]*)", re.IGNORECASE
)


def parse_ofx(path: str, result: ParseResult) -> None:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    # Account info: <ACCTID>, <BANKID>, <ACCTTYPE>, or credit-card <CCACCTID>
    acct_id_match = re.search(r"<ACCTID>\s*([^\r\n<]*)", text, re.IGNORECASE)
    acct_type_match = re.search(r"<ACCTTYPE>\s*([^\r\n<]*)", text, re.IGNORECASE)
    org_match = re.search(r"<ORG>\s*([^\r\n<]*)", text, re.IGNORECASE)
    balance_match = re.search(r"<BALAMT>\s*([^\r\n<]*)", text, re.IGNORECASE)
    baldate_match = re.search(r"<DTASOF>\s*([^\r\n<]*)", text, re.IGNORECASE)

    account_id = next_account_id()
    raw_acct = acct_id_match.group(1).strip() if acct_id_match else None
    acct_type_raw = (acct_type_match.group(1).strip().upper() if acct_type_match else "")
    type_map = {
        "CHECKING": "checking", "SAVINGS": "savings", "CREDITLINE": "credit_card",
        "MONEYMRKT": "savings", "CD": "savings",
    }
    account_type = type_map.get(acct_type_raw, "checking")
    if "<CCACCTID>" in text.upper():
        account_type = "credit_card"

    result.accounts.append({
        "id": account_id,
        "name": (org_match.group(1).strip() if org_match else "Imported OFX account"),
        "institution": org_match.group(1).strip() if org_match else None,
        "mask": mask_account(raw_acct),
        "type": account_type,
        "balance": parse_amount(balance_match.group(1)) if balance_match else None,
        "as_of": parse_date(baldate_match.group(1)) if baldate_match else None,
        "apr_or_apy": None,
        "is_liability": account_type == "credit_card",
        "source": "export",
    })

    # Split into STMTTRN blocks (case-insensitive, tolerant of unclosed/odd tags).
    blocks = re.split(r"<STMTTRN>", text, flags=re.IGNORECASE)[1:]
    for block in blocks:
        # Truncate at closing tag if present, else use whole remainder up to next STMTTRN.
        end = re.search(r"</STMTTRN>", block, re.IGNORECASE)
        segment = block[: end.start()] if end else block

        fields: dict[str, str] = {}
        for m in STMTTRN_FIELD_RE.finditer(segment):
            key = m.group(1).upper()
            val = m.group(2).strip()
            if key not in fields:  # first occurrence wins
                fields[key] = val

        date_iso = parse_date(fields.get("DTPOSTED", ""))
        amount = parse_amount(fields.get("TRNAMT", ""))
        desc = fields.get("NAME") or fields.get("PAYEE") or fields.get("MEMO") or ""
        memo = fields.get("MEMO", "")
        if memo and memo not in desc:
            desc = f"{desc} {memo}".strip()

        if date_iso is None or amount is None:
            result.warnings.append(f"{path}: skipped unparsable STMTTRN block")
            continue

        category, is_transfer = categorize(desc, amount)
        is_income = amount > 0 and category == "income"

        result.transactions.append({
            "date": date_iso,
            "account_id": account_id,
            "amount": round(amount, 2),
            "description": desc.strip(),
            "category": category,
            "is_income": is_income,
            "is_transfer": is_transfer,
        })


# --------------------------------------------------------------------------- #
# XLSX parsing (zipfile + shared strings, no openpyxl)
# --------------------------------------------------------------------------- #

XLSX_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col_to_index(col: str) -> int:
    idx = 0
    for ch in col:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return idx - 1


def _cell_ref_col(ref: str) -> str:
    m = re.match(r"([A-Z]+)(\d+)", ref)
    return m.group(1) if m else "A"


def read_xlsx_sheet1_rows(path: str) -> list[list[str]]:
    with zipfile.ZipFile(path) as z:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in ss_root.findall("m:si", XLSX_NS):
                texts = si.findall(".//m:t", XLSX_NS)
                shared_strings.append("".join((t.text or "") for t in texts))

        # Find first worksheet (sheet1.xml, or lowest-numbered sheetN.xml).
        sheet_names = sorted(
            [n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)],
            key=lambda n: int(re.search(r"(\d+)", n).group(1)),
        )
        if not sheet_names:
            return []
        sheet_xml = z.read(sheet_names[0])
        root = ET.fromstring(sheet_xml)

        rows_out: list[list[str]] = []
        sheet_data = root.find("m:sheetData", XLSX_NS)
        if sheet_data is None:
            return []

        for row_el in sheet_data.findall("m:row", XLSX_NS):
            cells: dict[int, str] = {}
            max_idx = -1
            for c_el in row_el.findall("m:c", XLSX_NS):
                ref = c_el.get("r", "")
                col_letters = _cell_ref_col(ref)
                idx = _col_to_index(col_letters) if col_letters else len(cells)
                cell_type = c_el.get("t")
                v_el = c_el.find("m:v", XLSX_NS)
                if v_el is None or v_el.text is None:
                    value = ""
                elif cell_type == "s":
                    try:
                        value = shared_strings[int(v_el.text)]
                    except (ValueError, IndexError):
                        value = ""
                elif cell_type == "inlineStr":
                    is_el = c_el.find("m:is", XLSX_NS)
                    value = "".join(t.text or "" for t in (is_el.findall(".//m:t", XLSX_NS) if is_el is not None else []))
                else:
                    value = v_el.text
                cells[idx] = value
                max_idx = max(max_idx, idx)
            row_list = [cells.get(i, "") for i in range(max_idx + 1)]
            rows_out.append(row_list)
        return rows_out


def parse_xlsx(path: str, result: ParseResult) -> None:
    try:
        rows = read_xlsx_sheet1_rows(path)
    except (zipfile.BadZipFile, ET.ParseError) as e:
        result.warnings.append(f"{path}: failed to read XLSX ({e})")
        return

    if not rows:
        result.warnings.append(f"{path}: no rows found in sheet1")
        return

    header = [str(h) for h in rows[0]]
    colmap_positional = _map_headers(header)
    if "date" not in colmap_positional or (
        "amount" not in colmap_positional and "debit" not in colmap_positional and "credit" not in colmap_positional
    ):
        result.warnings.append(f"{path}: could not identify date/amount columns from header {header}; skipped")
        return

    # Convert alias -> column index
    norm_to_idx = {_norm_header(h): i for i, h in enumerate(header)}
    idxmap: dict[str, int] = {}
    for canonical, aliases in HEADER_ALIASES.items():
        for norm_name, i in norm_to_idx.items():
            if norm_name in aliases:
                idxmap[canonical] = i
                break

    account_id = next_account_id()
    result.accounts.append({
        "id": account_id,
        "name": f"Imported ({path.split('/')[-1].split(chr(92))[-1]})",
        "institution": None,
        "mask": None,
        "type": "checking",
        "balance": None,
        "as_of": None,
        "apr_or_apy": None,
        "is_liability": False,
        "source": "export",
    })

    running_balance_seen = None
    for row in rows[1:]:
        def get(idx_key):
            i = idxmap.get(idx_key)
            if i is None or i >= len(row):
                return ""
            return row[i]

        date_iso = parse_date(get("date"))
        desc = get("description") or ""

        amount = None
        if "amount" in idxmap:
            amount = parse_amount(get("amount"))
        else:
            debit = parse_amount(get("debit")) if "debit" in idxmap else None
            credit = parse_amount(get("credit")) if "credit" in idxmap else None
            if debit:
                amount = -abs(debit)
            elif credit:
                amount = abs(credit)

        if date_iso is None or amount is None:
            continue

        if "balance" in idxmap:
            bal = parse_amount(get("balance"))
            if bal is not None:
                running_balance_seen = (date_iso, bal)

        category, is_transfer = categorize(desc, amount)
        is_income = amount > 0 and category == "income"

        result.transactions.append({
            "date": date_iso,
            "account_id": account_id,
            "amount": round(amount, 2),
            "description": str(desc).strip(),
            "category": category,
            "is_income": is_income,
            "is_transfer": is_transfer,
        })

    if running_balance_seen:
        as_of, bal = running_balance_seen
        result.accounts[-1]["balance"] = bal
        result.accounts[-1]["as_of"] = as_of


# --------------------------------------------------------------------------- #
# Format detection & driver
# --------------------------------------------------------------------------- #

def detect_format(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".xlsx"):
        return "xlsx"
    if lower.endswith((".ofx", ".qfx", ".qbo")):
        return "ofx"
    if lower.endswith(".csv"):
        return "csv"
    # Content sniff fallback
    try:
        with open(path, "rb") as f:
            head = f.read(2048)
        if head[:2] == b"PK":
            return "xlsx"
        text_head = head.decode("utf-8", errors="ignore")
        if "<OFX>" in text_head.upper() or "<STMTTRN>" in text_head.upper():
            return "ofx"
    except OSError:
        pass
    return "csv"


def apply_mask_to_all_accounts(result: ParseResult) -> None:
    """Defense in depth: ensure every account mask field is truncated to last-4."""
    for acct in result.accounts:
        if acct.get("mask"):
            acct["mask"] = mask_account(acct["mask"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse bank/brokerage statement exports (CSV/OFX/QFX/XLSX) into "
                    "plan_model.json-shaped accounts/transactions/holdings JSON."
    )
    parser.add_argument("files", nargs="+", help="Statement export file(s)")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()

    result = ParseResult()

    for path in args.files:
        fmt = detect_format(path)
        try:
            if fmt == "csv":
                parse_csv(path, result)
            elif fmt == "ofx":
                parse_ofx(path, result)
            elif fmt == "xlsx":
                parse_xlsx(path, result)
            else:
                result.warnings.append(f"{path}: unknown format, skipped")
        except (OSError, UnicodeDecodeError) as e:
            result.warnings.append(f"{path}: error reading file ({e})")

    apply_mask_to_all_accounts(result)

    output = {
        "accounts": result.accounts,
        "transactions": result.transactions,
        "holdings": result.holdings,
        "warnings": result.warnings,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Never print account numbers or transaction descriptions in bulk -- just counts.
    print(f"Parsed {len(result.accounts)} account(s), {len(result.transactions)} "
          f"transaction(s), {len(result.holdings)} holding(s) -> {args.out}")
    if result.warnings:
        print(f"{len(result.warnings)} warning(s):")
        for w in result.warnings:
            print(f"  - {w}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
