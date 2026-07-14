/** @odoo-module **/

import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { ConnectionAbortedError } from "@web/core/network/rpc";
import { ORM } from "@web/core/orm_service";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { Component, useState } from "@odoo/owl";

const BYPASS_REASON_CONTEXT_KEY = "cm_sa_timesheet_lock_bypass_reason";
const BYPASS_EXCEPTION_NAME = "TimesheetBypassReasonRequired";
const BYPASS_MESSAGE_TOKEN =
    "This timesheet entry is locked, but you are allowed to bypass it";

let timesheetLockDialogService = null;

class TimesheetBypassCancelledError extends ConnectionAbortedError {}

export class TimesheetBypassReasonDialog extends Component {
    static template = "cm_sa_timesheet_lock.TimesheetBypassReasonDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        title: String,
        message: String,
        confirm: Function,
        cancel: Function,
    };

    setup() {
        this.state = useState({ reason: "", validationMessage: "" });
        this.env.dialogData.dismiss = () => this.onCancel();
    }

    async onConfirm() {
        const reason = this.state.reason.trim();
        if (!reason) {
            this.state.validationMessage = _t("Bypass Reason is required.");
            return;
        }
        this.state.validationMessage = "";
        await this.props.confirm(reason);
        this.props.close();
    }

    onCancel() {
        this.props.cancel();
        this.props.close();
    }
}

/**
 * Odoo normally exposes the Python class in error.exceptionName. Some server
 * builds/proxies only preserve it in error.data.name or in the debug
 * traceback, so inspect all stable RPC error locations.
 */
function isBypassReasonError(error) {
    const candidates = [
        error?.exceptionName,
        error?.data?.name,
        error?.data?.message,
        error?.data?.debug,
        error?.message,
        ...(Array.isArray(error?.data?.arguments) ? error.data.arguments : []),
    ];
    return candidates.some((value) => {
        const text = typeof value === "string" ? value : "";
        return (
            text.includes(BYPASS_EXCEPTION_NAME) ||
            text.includes(BYPASS_MESSAGE_TOKEN)
        );
    });
}

function getBypassMessage(error) {
    const argument = Array.isArray(error?.data?.arguments)
        ? error.data.arguments.find((item) => typeof item === "string")
        : null;
    return (
        argument ||
        error?.data?.message ||
        _t("Enter a mandatory reason to bypass this timesheet lock.")
    );
}

function requestBypassReason(dialogService, error) {
    const message = getBypassMessage(error);

    return new Promise((resolve, reject) => {
        let settled = false;
        const settleResolve = (reason) => {
            if (!settled) {
                settled = true;
                resolve(reason);
            }
        };
        const settleReject = () => {
            if (!settled) {
                settled = true;
                reject(
                    new TimesheetBypassCancelledError(
                        "Timesheet bypass cancelled"
                    )
                );
            }
        };

        dialogService.add(
            TimesheetBypassReasonDialog,
            {
                title: _t("Invalid Operation"),
                message,
                confirm: settleResolve,
                cancel: settleReject,
            },
            { onClose: settleReject }
        );
    });
}

// Store the dialog service through a normal Odoo service dependency. This is
// reliable regardless of the order in which the ORM service itself starts.
registry.category("services").add("cm_sa_timesheet_lock_bypass_dialog", {
    dependencies: ["dialog"],
    start(env, { dialog }) {
        timesheetLockDialogService = dialog;
        return {};
    },
});

// Catch the failed mutation, request the reason, then retry exactly the same
// ORM call with the mandatory reason in context. This covers form, list and
// grid saves because they all pass through ORM.call.
patch(ORM.prototype, {
    async call(model, method, args = [], kwargs = {}) {
        try {
            return await super.call(model, method, args, kwargs);
        } catch (error) {
            const context = kwargs.context || {};
            const isTimesheetMutation =
                model === "account.analytic.line" &&
                ["create", "write", "web_save", "web_save_multi"].includes(
                    method
                );

            if (
                !isTimesheetMutation ||
                !isBypassReasonError(error) ||
                context[BYPASS_REASON_CONTEXT_KEY] ||
                !timesheetLockDialogService
            ) {
                throw error;
            }

            const reason = await requestBypassReason(
                timesheetLockDialogService,
                error
            );
            const retryKwargs = {
                ...kwargs,
                context: {
                    ...context,
                    [BYPASS_REASON_CONTEXT_KEY]: reason,
                },
            };
            return await super.call(model, method, args, retryKwargs);
        }
    },
});

// Cancelling the popup means "do not save". Swallow only this dedicated
// cancellation so Odoo does not display a second generic client error.
registry.category("error_handlers").add(
    "cm_sa_timesheet_lock_cancelled",
    (env, uncaughtError, originalError) => {
        if (!(originalError instanceof TimesheetBypassCancelledError)) {
            return false;
        }
        uncaughtError.unhandledRejectionEvent?.preventDefault();
        return true;
    },
    { sequence: 96 }
);
