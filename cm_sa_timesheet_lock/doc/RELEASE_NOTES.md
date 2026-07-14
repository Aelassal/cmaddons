# Release Notes

All notable changes to **Timesheet Back-Dating Limit (Rolling Window)** are tracked here.
Versions follow the format `<odoo_version>.<major>.<minor>.<patch>`.

---

## 19.0.1.2.0 — 2026-07-14

- Fixed the bypass RPC exception appearing as a generic Odoo Server Error.
- Replaced the ORM-start environment capture with a dedicated Odoo service
  dependency on the dialog service.
- Added resilient bypass-error detection using the RPC exception name, data
  name, message, arguments, and debug traceback.
- Retained automatic retry of the original create/write/web_save request after
  a mandatory reason is entered.

---

## 19.0.1.1.0 — 2026-07-14

- Fixed bypass users being able to save locked timesheets without a reason.
- Added an automatic **Invalid Operation** modal containing a mandatory
  **Bypass Reason** field.
- The original create/write request is retried only after a non-empty reason is
  submitted.
- Added the reason and related timesheet entry to the immutable Bypass Log.
- Improved validation messages to always show the earliest allowed date,
  including for rules created with the previous message template.
- Limited the rolling-window guard to actual timesheet analytic lines (project
  or task based), instead of every analytic line.
- Prevented duplicate bypass logs caused by nested Odoo timesheet
  post-processing writes.
- Fixed the post-install smoke test's undefined variable.

---

## 19.0.1.0.0 — 2026-04-24

Initial public release on the Odoo App Store.

**What's in it**

- Block timesheet entries more than N days old using a rolling window.
- Compatible with Odoo 17.0, 18.0, and 19.0 (Community + Enterprise).
- Bypass group and audit-log foundation.
