import api from './api';
const COMPANY_PROFILE_ENDPOINT = '/company-profile/';
export const DEFAULT_COMPANY_PROFILE = {
  company_name: 'Your Company Name',
  address_line1: 'Your Address Line 1, Near Landmark,',
  address_line2: 'City, STATE',
  mobile: '',
  email: '',
  gstin: '',
  pan_card: '',
  udyam_no: '',
  bank_account_name: '',
  bank_account_no: '',
  bank_ifsc: '',
  bank_name: '',
  terms_and_conditions: [
    'As per section 15 of MSMED Act, 2006, business are required to pay MSMEs within 45 days.',
    'Goods once sold will not be taken back or exchanged.',
  ],
  jurisdiction_note: 'Subject to Ahmedabad jurisdiction.',
};
export function fetchCompanyProfile() {
  return api.get(COMPANY_PROFILE_ENDPOINT).then((res) => res.data);
}
export function updateCompanyProfile(payload) {
  return api.put(COMPANY_PROFILE_ENDPOINT, payload).then((res) => res.data);
}
