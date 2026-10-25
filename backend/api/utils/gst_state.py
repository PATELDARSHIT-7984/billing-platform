"""Account GST registration states; no dependency on Customer/Party contracts.

Source: https://docs.ewaybillgst.gov.in/apidocs/state-code.html
25 and 28 are retained for historical registrations (including approved C4).
99 is a place-of-supply foreign-country sentinel, not an Indian registration state.
"""
GST_STATES = {
    '01': 'Jammu and Kashmir', '02': 'Himachal Pradesh', '03': 'Punjab',
    '04': 'Chandigarh', '05': 'Uttarakhand', '06': 'Haryana', '07': 'Delhi',
    '08': 'Rajasthan', '09': 'Uttar Pradesh', '10': 'Bihar', '11': 'Sikkim',
    '12': 'Arunachal Pradesh', '13': 'Nagaland', '14': 'Manipur', '15': 'Mizoram',
    '16': 'Tripura', '17': 'Meghalaya', '18': 'Assam', '19': 'West Bengal',
    '20': 'Jharkhand', '21': 'Odisha', '22': 'Chhattisgarh', '23': 'Madhya Pradesh',
    '24': 'Gujarat', '25': 'Daman and Diu',
    '26': 'Dadra and Nagar Haveli and Daman and Diu', '27': 'Maharashtra',
    '28': 'Andhra Pradesh (Old)', '29': 'Karnataka', '30': 'Goa',
    '31': 'Lakshadweep', '32': 'Kerala', '33': 'Tamil Nadu', '34': 'Puducherry',
    '35': 'Andaman and Nicobar Islands', '36': 'Telangana', '37': 'Andhra Pradesh',
    '38': 'Ladakh', '97': 'Other Territory',
}
HISTORICAL_STATE_CODES = frozenset({'25', '28'})
CURRENT_STATE_CODES = frozenset(GST_STATES) - HISTORICAL_STATE_CODES


def validate_selectable_state(code):
    if code is not None and code not in CURRENT_STATE_CODES:
        raise ValueError('Select a current GST state code; historical codes are read-only.')
    return code


def normalize_state_code(value):
    if value is None or not value.strip():
        return None
    code = value.strip()
    if code not in GST_STATES:
        raise ValueError('Invalid GST state code.')
    return code


def state_code_from_name(value):
    if value is None or not value.strip():
        return None
    name = ' '.join(value.casefold().replace('&', 'and').split())
    aliases = {'orissa': '21', 'pondicherry': '34', 'uttaranchal': '05',
               'dadra and nagar haveli': '26', 'andaman and nicobar': '35'}
    names = {v.casefold(): k for k, v in GST_STATES.items()}
    code = names.get(name) or aliases.get(name)
    if code is None:
        raise ValueError('Unrecognized state name.')
    return code
