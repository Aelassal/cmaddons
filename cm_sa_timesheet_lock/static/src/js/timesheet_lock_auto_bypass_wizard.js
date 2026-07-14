/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const BYPASS_REASON_MESSAGE_PART = "mandatory bypass reason";
const TIMESHEET_MODEL = "account.analytic.line";
const WIZARD_MODEL = "cm_sa.timesheet.lock.bypass.wizard";

function errorMessage(error) {
    return (
        error?.data?.message ||
        error?.message ||
        error?.data?.arguments?.[0] ||
        ""
    ).toString();
}

function isTimesheetBypassReasonError(error) {
    return errorMessage(error).toLowerCase().includes(BYPASS_REASON_MESSAGE_PART);
}

patch(FormController.prototype, {
    async saveButtonClicked(params = {}) {
        try {
            return await super.saveButtonClicked(params);
        } catch (error) {
            const record = this.model?.root;
            const resModel = record?.resModel;
            const resId = record?.resId;

            if (
                resModel === TIMESHEET_MODEL &&
                resId &&
                isTimesheetBypassReasonError(error)
            ) {
                await this.actionService.doAction(
                    {
                        type: "ir.actions.act_window",
                        name: "Enter Bypass Reason",
                        res_model: WIZARD_MODEL,
                        views: [[false, "form"]],
                        view_mode: "form",
                        target: "new",
                        context: {
                            active_model: TIMESHEET_MODEL,
                            active_ids: [resId],
                            active_id: resId,
                        },
                    },
                    {
                        onClose: async () => {
                            try {
                                await super.saveButtonClicked(params);
                            } catch (secondError) {
                                throw secondError;
                            }
                        },
                    }
                );
                return false;
            }
            throw error;
        }
    },
});
