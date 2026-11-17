"""
MediFind Healthcare Ingestion Pipeline - Data Normalization Module
Standardizes Indian administrative entities (States/UTs, Districts, Cities, Pincodes, Phones).
"""

import re
from typing import Any, Optional

# Official 28 States and 8 Union Territories of the Republic of India
CANONICAL_INDIAN_STATES = {
    # 28 States
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    # 8 Union Territories
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
}

# Alias mapping for legacy spellings, abbreviations, and common data feed variations
STATE_ALIASES = {
    # Delhi
    "dl": "Delhi",
    "nct of delhi": "Delhi",
    "delhi nct": "Delhi",
    "new delhi": "Delhi",
    "nct delhi": "Delhi",
    # Telangana & Andhra
    "tg": "Telangana",
    "ts": "Telangana",
    "telengana": "Telangana",
    "telangana state": "Telangana",
    "ap": "Andhra Pradesh",
    "andhra": "Andhra Pradesh",
    # Maharashtra
    "mh": "Maharashtra",
    "maharashtra state": "Maharashtra",
    # Karnataka
    "ka": "Karnataka",
    "karnataka state": "Karnataka",
    # Tamil Nadu
    "tn": "Tamil Nadu",
    "tamilnadu": "Tamil Nadu",
    # West Bengal
    "wb": "West Bengal",
    "west bengal state": "West Bengal",
    # Uttar Pradesh
    "up": "Uttar Pradesh",
    # Gujarat
    "gj": "Gujarat",
    # Rajasthan
    "rj": "Rajasthan",
    # Kerala
    "kl": "Kerala",
    # Madhya Pradesh
    "mp": "Madhya Pradesh",
    # Punjab & Haryana & Chandigarh
    "pb": "Punjab",
    "hr": "Haryana",
    "ch": "Chandigarh",
    "chandigarh ut": "Chandigarh",
    # Bihar & Jharkhand
    "br": "Bihar",
    "jh": "Jharkhand",
    # Odisha
    "od": "Odisha",
    "or": "Odisha",
    "orissa": "Odisha",
    # Uttarakhand
    "uk": "Uttarakhand",
    "ua": "Uttarakhand",
    "uttaranchal": "Uttarakhand",
    # Assam & North East
    "as": "Assam",
    "tr": "Tripura",
    "ml": "Meghalaya",
    "mn": "Manipur",
    "nl": "Nagaland",
    "mz": "Mizoram",
    "ar": "Arunachal Pradesh",
    "sk": "Sikkim",
    # Chhattisgarh & Goa
    "cg": "Chhattisgarh",
    "chattisgarh": "Chhattisgarh",
    "ga": "Goa",
    # Jammu & Kashmir & Ladakh
    "jk": "Jammu and Kashmir",
    "jammu & kashmir": "Jammu and Kashmir",
    "j&k": "Jammu and Kashmir",
    "la": "Ladakh",
    # UTs
    "py": "Puducherry",
    "pondicherry": "Puducherry",
    "an": "Andaman and Nicobar Islands",
    "andaman & nicobar": "Andaman and Nicobar Islands",
    "dd": "Dadra and Nagar Haveli and Daman and Diu",
    "dnh": "Dadra and Nagar Haveli and Daman and Diu",
    "daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
    "dadra and nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "ld": "Lakshadweep",
}


def normalize_indian_state(raw_state: Any) -> str:
    """
    Standardizes state input to its canonical Census/official Republic of India name.
    Returns canonical state string, or cleaned original if not recognized.
    """
    if not raw_state:
        return ""
    cleaned = str(raw_state).strip()
    lookup = cleaned.lower()

    # Check direct canonical match (case-insensitive)
    for canonical in CANONICAL_INDIAN_STATES:
        if lookup == canonical.lower():
            return canonical

    # Check alias map
    if lookup in STATE_ALIASES:
        return STATE_ALIASES[lookup]

    # Partial substring cleanup
    for alias_key, canonical in STATE_ALIASES.items():
        if len(alias_key) > 3 and alias_key in lookup:
            return canonical

    return cleaned.title()


def clean_indian_pincode(raw_pincode: Any) -> str:
    """
    Normalizes Indian postal pincodes to exactly 6 digits.
    Rules: Must be exactly 6 numeric digits; first digit cannot be '0'.
    """
    if not raw_pincode:
        return ""
    digits = re.sub(r'\D', '', str(raw_pincode))
    if len(digits) == 6 and digits[0] != '0':
        return digits
    return ""


def normalize_phone_number(raw_phone: Any) -> str:
    """
    Cleans and standardizes Indian phone numbers (mobile or landline with STD).
    Strips international prefixes (+91, 0091) and formats consistently.
    """
    if not raw_phone:
        return ""
    val = str(raw_phone).strip()
    digits = re.sub(r'[^\d]', '', val)

    if not digits:
        return ""

    # Strip country code 91 if present
    if digits.startswith("91") and len(digits) > 10:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    # Mobile: 10 digits starting with 6, 7, 8, or 9
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91 {digits[:5]} {digits[5:]}"

    # Landline: 10 or 11 digits (STD + number)
    if 8 <= len(digits) <= 11:
        return val  # Retain formatted original if plausible landline

    return val[:50]


def sanitize_text(text: Any, max_length: Optional[int] = None) -> str:
    """
    Cleans text by stripping whitespace, collapsing multiple spaces, and truncating.
    """
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', str(text)).strip()
    if max_length and len(cleaned) > max_length:
        return cleaned[:max_length].rstrip()
    return cleaned
