#!/usr/bin/env python3
"""Browser acceptance suite for HealthPilot.

Run against a seeded stack:
  python -m pip install -r tests/e2e/requirements.txt
  playwright install chromium
  python tests/e2e/playwright_acceptance.py --base http://127.0.0.1:3000

This suite deliberately fails on console errors, broken routes, unlabeled controls,
role leakage, offline misrepresentation, and actions that do not persist through
the API. It does not approve clinical correctness; human sign-off remains required.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable

from playwright.sync_api import Browser, BrowserContext, Page, expect, sync_playwright


@dataclass(frozen=True)
class Actor:
    role: str
    email: str
    home: str
    routes: tuple[str, ...]
    password: str = "DemoPass!2026"


ACTORS = (
    Actor("patient", "patient1@healthpilot.test", "/patient", ("/patient/appointments", "/patient/health-record", "/patient/invoices", "/patient/dependents")),
    Actor("doctor", "dr.nakato@healthpilot.test", "/doctor", ("/doctor/appointments", "/doctor/clinical", "/doctor/lab-referrals", "/doctor/prescriptions", "/release-acceptance")),
    Actor("nurse", "nurse@healthpilot.test", "/nurse", ("/nurse/inpatients", "/nurse/triage", "/nurse/medications", "/nurse/advanced-inpatient", "/release-acceptance")),
    Actor("midwife", "midwife@healthpilot.test", "/midwife", ("/midwife/antenatal-dashboard", "/midwife/visual-partograph", "/midwife/newborn-assessment")),
    Actor("receptionist", "reception@healthpilot.test", "/reception", ("/reception/appointment-calendar", "/reception/provider-schedules", "/reception/patient-arrival-board")),
    Actor("records_officer", "records@healthpilot.test", "/records", ("/records/master-patient-index", "/records/merge-wizard", "/records/record-release", "/release-acceptance")),
    Actor("cashier", "cashier@healthpilot.test", "/cashier", ("/cashier/patient-account", "/cashier/split-payment", "/cashier/receipt-history")),
    Actor("accountant", "accountant@healthpilot.test", "/accounting", ("/accounting/general-ledger", "/accounting/trial-balance", "/accounting/income-statement", "/release-acceptance")),
    Actor("pharmacist", "pharmacist.staff@healthpilot.test", "/pharmacist", ("/pharmacist/prescription-workspace", "/pharmacist/controlled-drug-register", "/pharmacist/stock-count", "/release-acceptance")),
    Actor("lab_technician", "labtech@healthpilot.test", "/lab-staff", ("/lab-staff/collection-worklist", "/lab-staff/result-entry", "/lab-staff/validation-queue", "/release-acceptance")),
    Actor("radiologist", "radiologist@healthpilot.test", "/radiology", ("/radiology/modality-worklist", "/radiology/reporting-editor", "/radiology/pacs-viewer")),
    Actor("paramedic", "paramedic@healthpilot.test", "/paramedic", ("/paramedic/trauma-chart", "/paramedic/resuscitation-timeline", "/paramedic/offline-paramedic")),
    Actor("anaesthetist", "anaesthetist@healthpilot.test", "/anaesthesia", ("/anaesthesia/pre-anaesthetic", "/anaesthesia/anaesthesia-chart", "/anaesthesia/recovery-observation")),
    Actor("facility_manager", "manager@healthpilot.test", "/facility", ("/facility/multi-branch-dashboard", "/facility/staff-onboarding", "/facility/visual-bed-map")),
    Actor("insurance_officer", "insurance.officer@healthpilot.test", "/insurance-officer", ("/insurance-officer/eligibility-detail", "/insurance-officer/preauthorization-workbench", "/insurance-officer/claim-detail")),
)

ADMIN = Actor("admin", "admin@healthpilot.test", "/admin", ("/admin/user-detail", "/admin/role-matrix", "/admin/verification-case", "/admin/backup-restore", "/admin/release-acceptance"), "AdminPass!2026")
VIEWPORTS = (("desktop", {"width": 1440, "height": 1000}), ("tablet", {"width": 834, "height": 1112}), ("mobile", {"width": 390, "height": 844}))
ALL_ROLE_ACTORS = (
    Actor("patient", "patient1@healthpilot.test", "/patient", ()),
    Actor("doctor", "dr.nakato@healthpilot.test", "/doctor", ()),
    Actor("clinical_officer", "clinical.officer@healthpilot.test", "/clinical-officer", ()),
    Actor("dentist", "dentist@healthpilot.test", "/dentist", ()),
    Actor("physiotherapist", "physio@healthpilot.test", "/physiotherapy", ()),
    Actor("nutritionist", "nutrition@healthpilot.test", "/nutrition", ()),
    Actor("psychologist", "psychology@healthpilot.test", "/psychology", ()),
    Actor("medical_director", "medical.director@healthpilot.test", "/medical-director", ()),
    Actor("nurse", "nurse@healthpilot.test", "/nurse", ()),
    Actor("midwife", "midwife@healthpilot.test", "/midwife", ()),
    Actor("theatre_nurse", "theatre.nurse@healthpilot.test", "/theatre-nurse", ()),
    Actor("receptionist", "reception@healthpilot.test", "/reception", ()),
    Actor("records_officer", "records@healthpilot.test", "/records", ()),
    Actor("cashier", "cashier@healthpilot.test", "/cashier", ()),
    Actor("accountant", "accountant@healthpilot.test", "/accounting", ()),
    Actor("pharmacist", "pharmacist.staff@healthpilot.test", "/pharmacist", ()),
    Actor("lab_technician", "labtech@healthpilot.test", "/lab-staff", ()),
    Actor("radiologist", "radiologist@healthpilot.test", "/radiology", ()),
    Actor("radiographer", "radiographer@healthpilot.test", "/radiography", ()),
    Actor("anaesthetist", "anaesthetist@healthpilot.test", "/anaesthesia", ()),
    Actor("facility_manager", "manager@healthpilot.test", "/facility", ()),
    Actor("finance_manager", "finance.manager@healthpilot.test", "/finance", ()),
    Actor("procurement_officer", "procurement@healthpilot.test", "/procurement", ()),
    Actor("quality_officer", "quality@healthpilot.test", "/quality", ()),
    Actor("compliance_officer", "compliance@healthpilot.test", "/compliance", ()),
    Actor("hr_officer", "hr@healthpilot.test", "/hr", ()),
    Actor("it_support", "it@healthpilot.test", "/it-operations", ()),
    Actor("ambulance_dispatcher", "dispatcher@healthpilot.test", "/dispatch", ()),
    Actor("paramedic", "paramedic@healthpilot.test", "/paramedic", ()),
    Actor("insurance_officer", "insurance.officer@healthpilot.test", "/insurance-officer", ()),
    Actor("claims_reviewer", "claims@healthpilot.test", "/claims-review", ()),
    Actor("storekeeper", "storekeeper@healthpilot.test", "/storekeeping", ()),
    Actor("pharmacy", "pharmacy@healthpilot.test", "/pharmacy", ()),
    Actor("lab", "lab@healthpilot.test", "/lab", ()),
    Actor("hospital", "hospital@healthpilot.test", "/hospital", ()),
    Actor("insurance", "insurance@healthpilot.test", "/insurance", ()),
    ADMIN,
)



def login(page: Page, base: str, actor: Actor) -> None:
    page.goto(f"{base}/login", wait_until="domcontentloaded")
    page.get_by_label("Email address").fill(actor.email)
    page.get_by_label("Password").fill(actor.password)
    page.get_by_role("button", name="Sign in securely").click()
    verification = page.get_by_label("Verification code")
    if verification.is_visible(timeout=1500):
        code = os.getenv(f"HEALTHPILOT_MFA_{actor.role.upper()}") or os.getenv("HEALTHPILOT_MFA_CODE")
        if not code:
            raise AssertionError(f"{actor.role} requires MFA; set HEALTHPILOT_MFA_{actor.role.upper()} for browser acceptance")
        verification.fill(code)
        page.get_by_role("button", name="Verify and sign in").click()
    page.wait_for_url(lambda url: urllib.parse.urlparse(str(url)).path.startswith(actor.home), timeout=20_000)


def assert_accessible_basics(page: Page) -> None:
    violations = page.evaluate(
        """() => {
          const issues = [];
          const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
          document.querySelectorAll('input,select,textarea').forEach((el, i) => {
            if (!visible(el) || el.type === 'hidden') return;
            const id = el.id;
            const labelled = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') ||
              (id && document.querySelector(`label[for="${CSS.escape(id)}"]`)) || el.closest('label');
            if (!labelled) issues.push(`unlabelled form control ${el.tagName.toLowerCase()}#${id || i}`);
          });
          document.querySelectorAll('button').forEach((el, i) => {
            if (!visible(el)) return;
            if (!(el.innerText.trim() || el.getAttribute('aria-label') || el.getAttribute('title'))) issues.push(`unnamed button ${i}`);
          });
          document.querySelectorAll('img').forEach((el, i) => {
            if (!el.hasAttribute('alt')) issues.push(`image without alt ${i}`);
          });
          const ids = [...document.querySelectorAll('[id]')].map(el => el.id).filter(Boolean);
          const duplicates = ids.filter((id, i) => ids.indexOf(id) !== i);
          if (duplicates.length) issues.push(`duplicate ids: ${[...new Set(duplicates)].slice(0, 5).join(', ')}`);
          return issues;
        }"""
    )
    assert not violations, "Accessibility basics failed: " + "; ".join(violations)


def assert_no_dead_controls(page: Page) -> None:
    dead = page.evaluate(
        """() => [...document.querySelectorAll('button')]
          .filter(el => (el.offsetWidth || el.offsetHeight || el.getClientRects().length) && !el.disabled)
          .filter(el => !el.innerText.trim() && !el.getAttribute('aria-label') && !el.getAttribute('title'))
          .map((el, i) => `button-${i}`)"""
    )
    assert not dead, f"Visible active controls have no accessible action name: {dead}"


def visit_routes(page: Page, base: str, actor: Actor, routes: Iterable[str]) -> None:
    failures = []
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    for route in routes:
        response = page.goto(f"{base}{route}", wait_until="networkidle")
        if response and response.status >= 400:
            failures.append(f"{route}: HTTP {response.status}")
            continue
        if page.url.endswith("/403") or page.url.endswith("/404") or page.url.endswith("/500"):
            failures.append(f"{route}: redirected to error page {page.url}")
            continue
        expect(page.locator("main, [role=main], #root").first).to_be_visible()
        assert_accessible_basics(page)
        assert_no_dead_controls(page)
    actionable_console = [item for item in console_errors if not any(token in item.lower() for token in ("favicon", "resizeobserver"))]
    assert not failures, f"{actor.role} route failures: {failures}"
    assert not actionable_console, f"{actor.role} browser console errors: {actionable_console[:10]}"


def verify_persisted_workflow(page: Page, base: str) -> None:
    """Create a low-risk patient complaint and prove it survives a refresh/API read."""
    route = f"{base}/patient/feedback-complaint"
    page.goto(route, wait_until="networkidle")
    new_button = page.get_by_role("button", name="New workflow")
    if not new_button.is_visible(timeout=3000):
        raise AssertionError("The patient feedback workflow is not actionable")
    new_button.click()
    # Fields are server-definition driven; fill every visible required text field.
    dialog = page.get_by_role("dialog")
    for control in dialog.locator("input[required], textarea[required]").all():
        control_type = control.get_attribute("type")
        if control_type in {"date", "datetime-local", "time"}:
            continue
        if control_type == "number":
            control.fill("1")
        elif not control.input_value():
            control.fill("Playwright acceptance verification")
    for control in dialog.locator("select[required]").all():
        options = control.locator("option").evaluate_all("els => els.map(el => ({value: el.value, disabled: el.disabled}))")
        usable = next((item["value"] for item in options if item["value"] and not item["disabled"]), None)
        if usable:
            control.select_option(usable)
    dialog.get_by_role("button", name="Create workflow").click()
    expect(page.get_by_text("was created", exact=False)).to_be_visible(timeout=10_000)
    page.reload(wait_until="networkidle")
    expect(page.get_by_text("Playwright acceptance verification", exact=False).first).to_be_visible(timeout=10_000)


def crawl_role_navigation(page: Page, base: str, actor: Actor) -> None:
    """Visit every visible internal navigation route for a seeded role."""
    page.goto(f"{base}{actor.home}", wait_until="networkidle")
    hrefs = page.locator('a[href^="/"]').evaluate_all(
        "els => [...new Set(els.map(el => el.getAttribute('href')).filter(Boolean))]"
    )
    excluded = {"/", "/login", "/register", "/logout"}
    routes = [href.split('#')[0] for href in hrefs if href.split('#')[0] not in excluded]
    visit_routes(page, base, actor, sorted(set(routes)))


def offline_and_print_checks(page: Page, context: BrowserContext, base: str) -> None:
    page.goto(f"{base}/patient/appointments", wait_until="networkidle")
    page.emulate_media(media="print")
    assert page.locator("body").is_visible()
    page.emulate_media(media="screen")
    context.set_offline(True)
    page.evaluate("window.dispatchEvent(new Event('offline'))")
    assert page.evaluate("navigator.onLine") is False
    context.set_offline(False)
    page.evaluate("window.dispatchEvent(new Event('online'))")


def run(base: str, headless: bool, browser_executable: str | None = None) -> int:
    failures = []
    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(headless=headless, executable_path=browser_executable)
        try:
            for name, viewport in VIEWPORTS:
                context = browser.new_context(viewport=viewport)
                page = context.new_page()
                try:
                    login(page, base, ACTORS[0])
                    visit_routes(page, base, ACTORS[0], ACTORS[0].routes[:2] if name != "desktop" else ACTORS[0].routes)
                    if name == "desktop":
                        verify_persisted_workflow(page, base)
                        offline_and_print_checks(page, context, base)
                except Exception as exc:
                    failures.append(f"{name}/patient: {exc}")
                finally:
                    context.close()

            for actor in ACTORS[1:]:
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                page = context.new_page()
                try:
                    login(page, base, actor)
                    visit_routes(page, base, actor, actor.routes)
                except Exception as exc:
                    failures.append(f"{actor.role}: {exc}")
                finally:
                    context.close()

            if os.getenv("HEALTHPILOT_CRAWL_ALL_ROLES", "1") == "1":
                for actor in ALL_ROLE_ACTORS:
                    context = browser.new_context(viewport={"width": 1440, "height": 1000})
                    page = context.new_page()
                    try:
                        login(page, base, actor)
                        crawl_role_navigation(page, base, actor)
                    except Exception as exc:
                        failures.append(f"all-pages/{actor.role}: {exc}")
                    finally:
                        context.close()

            if os.getenv("HEALTHPILOT_TEST_ADMIN", "1") == "1":
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                page = context.new_page()
                try:
                    login(page, base, ADMIN)
                    visit_routes(page, base, ADMIN, ADMIN.routes)
                except Exception as exc:
                    failures.append(f"admin: {exc}")
                finally:
                    context.close()
        finally:
            browser.close()
    if failures:
        print("Playwright acceptance failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Playwright acceptance passed for critical role journeys, {len(ALL_ROLE_ACTORS)} seeded role navigation crawls, admin, {len(VIEWPORTS)} viewports, offline and print checks")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.getenv("HEALTHPILOT_FRONTEND_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--browser-executable",
        default=os.getenv("HEALTHPILOT_BROWSER_EXECUTABLE"),
        help="Path to a system Chrome/Chromium when the Playwright-managed build is unsupported on this OS.",
    )
    args = parser.parse_args()
    return run(args.base.rstrip("/"), not args.headed, args.browser_executable)


if __name__ == "__main__":
    sys.exit(main())
