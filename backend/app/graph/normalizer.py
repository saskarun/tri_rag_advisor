"""Entity normalization: collapse aliases/synonyms into canonical nodes."""
import re

# canonical name -> aliases (spec example: CBDT / Income Tax Dept / Tax Authority)
ALIASES = {
    "CBDT (Income Tax Dept)": ["cbdt", "central board of direct taxes", "income tax dept", "income tax department", "it department", "tax authority", "tax authorities"],
    "CBIC": ["cbic", "central board of indirect taxes and customs", "indirect tax authority"],
    "RBI": ["rbi", "reserve bank of india", "the regulator", "reserve bank"],
    "FIU-IND": ["fiu-ind", "fiu", "financial intelligence unit", "financial intelligence unit - india"],
    "GST Council": ["gst council", "57th gst council", "57th gst council meeting"],
    "CGST Act, 2017": ["cgst act", "cgst act 2017", "central goods and services tax act"],
    "PMLA": ["pmla", "prevention of money laundering act", "prevention of money laundering act 2002"],
    "Input Service Distributor (ISD)": ["isd", "input service distributor", "isd registration", "isd mechanism"],
    "E-Invoicing": ["e-invoicing", "e invoicing", "e-invoice", "einvoicing"],
    "Income Tax Act": ["income tax act", "income-tax act", "it act"],
    "Companies Act 2013": ["companies act 2013", "companies act"],
    "FEMA": ["fema", "foreign exchange management act"],
}
_LOOKUP = {a: c for c, al in ALIASES.items() for a in al}
_SUFFIX = re.compile(r"\b(ltd|limited|pvt|private|inc|llp|corp|co)\b\.?", re.I)


def _key(name: str) -> str:
    k = re.sub(r"[^a-z0-9\- ]", " ", name.lower())
    return re.sub(r"\s+", " ", k).strip()


def org_key(name: str) -> str:
    return re.sub(r"\s+", " ", _SUFFIX.sub("", _key(name))).strip()


def canonical(name: str, known: dict[str, str] | None = None) -> str:
    """Return canonical node name. `known` maps org_key -> canonical for fuzzy company-name merging."""
    k = _key(name)
    if k in _LOOKUP: return _LOOKUP[k]
    ok = org_key(name)
    if known is not None:
        if ok in known: return known[ok]
        known[ok] = name.strip()
    return name.strip()
