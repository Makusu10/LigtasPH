import re

PH_MOBILE = re.compile(r"^(\+63|0)9\d{9}$")
# Allow (02) 8xxx-xxxx, (02) 8646-1631, 02-8..., +63 2..., etc. - flexible for demo but must contain digits and not be empty
PH_LANDLINE_FLEX = re.compile(r"^[\d\(\)\-\s\+]{7,20}$")

def validate_phone(phone: str) -> bool:
    if not phone:
        return True  # optional field
    phone = phone.strip()
    if PH_MOBILE.match(phone):
        return True
    if PH_LANDLINE_FLEX.match(phone) and any(c.isdigit() for c in phone):
        # at least 7 digits
        digits = re.sub(r"\D", "", phone)
        return 7 <= len(digits) <= 13
    return False

def validate_lat_lng(lat, lng):
    try:
        lat_f = float(lat); lng_f = float(lng)
        return -90 <= lat_f <= 90 and -180 <= lng_f <= 180
    except:
        return False
