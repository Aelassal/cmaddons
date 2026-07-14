# SO Margin Guard - User Manual

Version: 19.0.1.1.0  
Odoo: 19.0 Community and Enterprise

## 1. Purpose

SO Margin Guard prevents confirmation of sales orders or other configured records when the calculated margin is below company policy. Authorized users may override a violation after entering a mandatory reason. Every override is written to a permanent, read-only audit log.

## 2. Security Roles

- **System Administrator**: can create and maintain rules.
- **Margin Guard Rule Administrator**: a dedicated technical group that can maintain rules without receiving general Sales Manager permissions.
- **Sales User / Sales Manager**: can read applicable rule information and audit logs, but cannot create, edit, or delete rules unless separately authorized.
- **Override Group Member**: can override a specific rule when the rule points to a group that contains the user.

To authorize a technical user, open Settings > Users & Companies > Groups and add the user to **Margin Guard Rule Administrator**.

## 3. Creating a Rule

Open **Margin Guard > Rules**. This menu is visible only to system administrators and Margin Guard Rule Administrators.

Complete these fields:

- **Name**: a clear policy name, such as `Sales Order Minimum 10 Percent`.
- **Model**: normally `Sales Order (sale.order)`.
- **Method to Guard**: normally `action_confirm`.
- **Domain**: optional Odoo domain. Use `[]` to apply the rule to all records.
- **Minimum Margin %**: the lowest accepted result.
- **Override Group**: users in this group may override the rule. Leave empty to block all overrides.
- **Require Reason on Override**: enables the reason wizard.
- **Minimum Reason Length**: minimum accepted number of characters.
- **Margin Formula**: a Python expression evaluated against `record` and returning a number.
- **Error Message**: the message shown when override is not permitted.

Allowed error-message placeholders are:

- `%(model)s`
- `%(actual).1f`
- `%(threshold).1f`
- `%%` for a literal percent sign

The system validates the domain, formula syntax, target method, threshold, minimum reason length, and error-message placeholders before saving.

## 4. Rule Activation

A new active rule is installed in the current Odoo worker immediately after saving. Existing wrappers read active rule values dynamically, so changes to thresholds, formulas, domains, groups, and messages are effective immediately. Other workers are signaled to refresh automatically. No manual service restart is required for normal rule creation or editing.

If the selected model or method does not exist, the rule cannot be saved as active.

## 5. Confirming One Sales Order

When the calculated margin meets the threshold, confirmation continues normally.

When the margin is below the threshold:

- A user outside the Override Group is blocked and receives the configured message.
- A member of the Override Group receives the Margin Override wizard when a reason is required.
- The order is confirmed only after a valid reason is entered.
- An audit log is created before confirmation completes.

If the audit log cannot be created, confirmation is cancelled.

## 6. Confirming Multiple Sales Orders

When several orders are selected and confirmed together, the module evaluates every order:

- Compliant orders are confirmed normally.
- Orders that need an authorized reason appear in one batch override wizard.
- Only affected orders are included in that wizard.
- Orders that the user cannot override remain unconfirmed and are listed clearly.
- The wizard also states which selected orders were already processed normally.

Cancelling the override wizard leaves the affected orders as quotations; compliant orders that were already processed remain confirmed.

## 7. Margin Override Audit Log

Open **Margin Guard > Override Log**.

Each entry records:

- date and time
- approving user
- rule
- source model and record
- configured threshold
- calculated margin
- margin gap
- approval reason

Audit entries are immutable. They cannot be created manually, edited, duplicated, or deleted through normal Odoo access. Rules that already have audit entries cannot be deleted; archive the rule instead.

## 8. Recommended Functional Test

1. Create an active `sale.order / action_confirm` rule with a threshold of 50.
2. Select an Override Group and require a reason of at least 10 characters.
3. Create one order with a formula result above 50 and another below 50.
4. Select both orders and click Confirm.
5. Verify that the compliant order is confirmed and only the low-margin order appears in the wizard.
6. Enter a reason and confirm the wizard.
7. Verify that the low-margin order is confirmed and an immutable log exists.
8. Attempt to edit and delete the log; both operations must be rejected.

## 9. Troubleshooting

- **Rule cannot be saved**: read the validation message and correct the model, method, formula syntax, domain, or error template.
- **User does not receive the wizard**: verify that the user belongs to the exact Override Group configured on every violated rule.
- **Order remains a quotation after batch confirm**: review the wizard or warning message; it lists records without override permission.
- **Confirmation cancelled because logging failed**: review server logs and database permissions. The module intentionally blocks confirmation when it cannot preserve the audit trail.
