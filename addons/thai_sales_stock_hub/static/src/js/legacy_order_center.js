/** @odoo-module **/

import { Component, onMounted, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class LegacyOrderCenter extends Component {
    static template = "thai_sales_stock_hub.LegacyOrderCenter";
    props = useProps();

    setup() {
        this.action = useService("action");
        onMounted(() => this.action.doAction("thai_sales_stock_hub.action_hub_orders", { clearBreadcrumbs: true }));
    }
}

registry.category("actions").add("thai_sales_stock_hub.OrderCenter", LegacyOrderCenter);
