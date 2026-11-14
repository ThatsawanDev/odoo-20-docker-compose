/** @odoo-module **/

import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class HubDashboard extends Component {
    static template = "thai_sales_stock_hub.Dashboard";
    props = useProps();

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({ loading: true, data: {} });
        onWillStart(async () => {
            this.state.data = await this.orm.call("thai.sales.stock.hub.dashboard", "get_overview", []);
            this.state.loading = false;
        });
    }

    open(xmlid) { return this.action.doAction(xmlid); }
    openChannel(key) {
        return this.action.doAction({ type: "ir.actions.act_window", name: "ออเดอร์ตามช่องทาง",
            res_model: "sale.order", views: [[false, "list"], [false, "form"]],
            domain: [["hub_channel", "=", key], ["state", "!=", "cancel"]], target: "current" });
    }
    openProduction() {
        return this.action.doAction({ type: "ir.actions.act_window", name: "การผลิต",
            res_model: "mrp.production", views: [[false, "list"], [false, "form"]], target: "current" });
    }
    money(value) { return new Intl.NumberFormat("th-TH", { maximumFractionDigits: 0 }).format(value || 0); }
    pct(value) { return `${Math.max(0, Math.min(100, value || 0))}%`; }
    statusGradient() {
        const statuses = this.state.data.statuses || [];
        const total = statuses.reduce((sum, item) => sum + item.count, 0);
        if (!total) return "conic-gradient(#e4edf8 0 100%)";
        let cursor = 0;
        const stops = statuses.map((item) => {
            const start = cursor;
            cursor += item.count / total * 100;
            return `${item.color} ${start}% ${cursor}%`;
        });
        return `conic-gradient(${stops.join(", ")})`;
    }
}

registry.category("actions").add("thai_sales_stock_hub.Dashboard", HubDashboard);
