/** @odoo-module */

import { registry } from "@web/core/registry";
import { StatusBarField, statusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class DynamicConfigStatusbar extends StatusBarField {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.labelConfig = [];
        onWillStart(async () => {
            try {
                this.labelConfig = await this.orm.searchRead(
                    "statusbar.label.config",
                    [["model_name", "=", this.props.record.resModel]],
                    ["target_state", "trigger_states", "alternative_label"]
                );
            } catch {
                // Gracefully degrade: use original labels if config cannot be loaded
                this.labelConfig = [];
            }
        });
    }

    getAllItems() {
        const items = super.getAllItems();
        if (!this.labelConfig.length) {
            return items;
        }
        const currentState = this.props.record.data[this.props.name];
        return items.map(item => {
            const rule = this.labelConfig.find(r =>
                r.target_state === item.value &&
                r.trigger_states &&
                r.trigger_states.split(",").map(s => s.trim()).includes(currentState)
            );
            return rule ? { ...item, label: rule.alternative_label } : item;
        });
    }
}

registry.category("fields").add("dynamic_config_statusbar", {
    ...statusBarField,
    component: DynamicConfigStatusbar,
});
