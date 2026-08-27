// Mirrors packages/contracts/python/veyra_contracts/browser.py and the
// response models in services/local-api's app/api/browser.py.
// docs/phase-8/*.

import type { DomainTrustStatus } from "./enums";

export interface BrowserTabInfo {
  tab_id: string;
  title: string;
  url: string;
  domain: string;
  status: string;
  active: boolean;
  favicon: string | null;
}

export interface BrowserSessionInfo {
  session_id: string;
  browser_type: string;
  connection_status: string;
  created_at: string;
  last_activity: string;
  tabs: BrowserTabInfo[];
  active_tab_id: string | null;
}

export interface PageObservationSummary {
  url: string;
  title: string;
  domain: string;
  login_state: string;
  captcha_detected: boolean;
  otp_detected: boolean;
  payment_page_detected: boolean;
  domain_trust: DomainTrustStatus;
}
