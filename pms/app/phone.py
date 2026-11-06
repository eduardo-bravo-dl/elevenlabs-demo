import re


def normalize_mx_phone(raw: str) -> str:
    """Return a Mexican number as E.164.

    "55 5010 0001", "+52 55 5010 0001" and the legacy mobile format
    "+521 55 5010 0001" all become "+525550100001".
    """
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        national = digits
    elif len(digits) == 12 and digits.startswith("52"):
        national = digits[2:]
    elif len(digits) == 13 and digits.startswith("521"):
        national = digits[3:]
    else:
        raise ValueError("Phone must be a 10-digit Mexican number, optionally with +52 or +521.")
    return "+52" + national


def mask_phone(e164: str) -> str:
    return "***" + e164[-4:] if e164 else ""
