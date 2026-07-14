/** @odoo-module **/

import { Component, useRef, useState, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const TIMESHEET_MODEL = "account.analytic.line";
const REASON_FIELD = "cm_sa_timesheet_bypass_reason";
const BYPASS_REASON_ERROR_MARKER = "mandatory bypass reason";

function extractErrorMessage(error) {
    const data = error?.data || {};
    const message =
        data.message ||
        data.arguments?.[0] ||
        error?.message ||
        _t("This timesheet entry is locked, but you are allowed to bypass it. Please enter a mandatory bypass reason.");
    return String(message);
}

function isBypassReasonError(error) {
    return extractErrorMessage(error).toLowerCase().includes(BYPASS_REASON_ERROR_MARKER);
}

class TimesheetBypassReasonDialog extends Component {
    static template = "cm_sa_timesheet_lock.TimesheetBypassReasonDialog";
    static components = { Dialog };
    static props = {
        message: String,
        onConfirm: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            reason: "",
            error: "",
            saving: false,
        });
        this.reasonRef = useRef("reason");
        onMounted(() => {
            this.reasonRef.el?.focus();
        });
    }

    async confirm() {
        const reason = (this.state.reason || "").trim();
        if (!reason) {
            this.state.error = _t("Please enter a bypass reason.");
            return;
        }
        this.state.error = "";
        this.state.saving = true;
        try {
            await this.props.onConfirm(reason);
            this.props.close();
        } catch (error) {
            this.state.error = extractErrorMessage(error);
        } finally {
            this.state.saving = false;
        }
    }
}

patch(FormController.prototype, {
    async saveButtonClicked(params = {}) {
        const originalSave = async () => super.saveButtonClicked(params);
        try {
            return await originalSave();
        } catch (error) {
            const record = this.model?.root;
            const dialogService = this.dialogService || this.env.services.dialog;

            if (
                record?.resModel === TIMESHEET_MODEL &&
                isBypassReasonError(error) &&
                dialogService
            ) {
                return await new Promise((resolve, reject) => {
                    dialogService.add(TimesheetBypassReasonDialog, {
                        message: extractErrorMessage(error),
                        onConfirm: async (reason) => {
                            try {
                                // Keep the temporary reason in the same pending save.
                                // The Python guard copies it to the bypass log and clears it
                                // after the real write succeeds.
                                await record.update({ [REASON_FIELD]: reason });
                                const result = await originalSave();
                                resolve(result);
                            } catch (saveError) {
                                reject(saveError);
                                throw saveError;
                            }
                        },
                        onClose: () => resolve(false),
                    });
                });
            }
            throw error;
        }
    },
});
