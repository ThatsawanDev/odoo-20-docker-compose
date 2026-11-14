/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProjectTaskStateSelection } from "@project/components/project_task_state_selection/project_task_state_selection";
import { patch } from "@web/core/utils/patch";

patch(ProjectTaskStateSelection.prototype, {
    setup() {
        super.setup();
        this.icons = {
            ...this.icons,
            "00_new": "add_circle",
            "04_waiting_normal": "hourglass_empty",
        };
        this.colorIcons = {
            ...this.colorIcons,
            "00_new": "text-primary", // สีน้ำเงิน
            "04_waiting_normal": "text-hold",
        };

        this.colorButton = {
            ...this.colorButton,
            "00_new": "btn-outline-primary",
            "04_waiting_normal": "btn-outline-secondary", // สีเทา #6C757D
        };
    },

    get options() {
        const allLabels = new Map(this.props.record.fields[this.props.name].selection);
        const states = ["1_done","1_canceled","04_waiting_normal"];
        const currentState = this.props.record.data[this.props.name];

//        if (currentState != "04_waiting_normal") {
        states.unshift("00_new","01_in_progress");
//        }
        return states.map((state) => [state, allLabels.get(state)]);
    },

    // Nested child_ids rows have canSaveOnUpdate=false, so update() alone doesn't persist;
    // save explicitly then reload the parent so subtask_completion_percentage refreshes.
    async updateRecord(value) {
        const result = await super.updateRecord(value);
        const record = this.props.record;
        const parentRecord = record._parentRecord;
        if (parentRecord) {
            if (record.dirty) {
                await record.save();
            }
            await parentRecord.load();
        }
        return result;
    },
});
