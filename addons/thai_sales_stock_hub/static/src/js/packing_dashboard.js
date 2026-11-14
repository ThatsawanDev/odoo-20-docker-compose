/** @odoo-module **/

import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PackingDashboard extends Component {
    static template = "thai_sales_stock_hub.PackingDashboard";
    props = useProps();

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({ loading: true, data: {}, warehouseId: false, stage: "waiting" });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("thai.sales.stock.hub.packing.dashboard", "get_overview", [this.state.warehouseId]);
        this.state.loading = false;
    }

    async selectWarehouse(ev) {
        this.state.warehouseId = ev.target.value ? Number(ev.target.value) : false;
        await this.load();
    }

    openQueue(stage = false) {
        const domain = [["picking_type_code", "=", "outgoing"]];
        if (this.state.warehouseId) domain.push(["picking_type_id.warehouse_id", "=", this.state.warehouseId]);
        if (stage === "done") {
            domain.push(["state", "=", "done"]);
            domain.push(["date_done", ">=", this.state.data.date_start], ["date_done", "<", this.state.data.date_end]);
        }
        else if (stage === "ready") {
            domain.push(["state", "=", "assigned"], ["hub_packing_state", "=", "packed"]);
        }
        else {
            domain.push(["state", "not in", ["done", "cancel"]]);
            if (stage) domain.push(["hub_packing_state", "=", stage]);
        }
        return this.action.doAction({ type: "ir.actions.act_window", name: "ใบส่งสินค้า / งานแพ็ก", res_model: "stock.picking",
            views: [[false, "list"], [false, "form"]], domain, target: "current" });
    }

    openPicking(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "stock.picking", res_id: id,
            views: [[false, "form"]], target: "current" });
    }

    openStations() { return this.action.doAction("thai_sales_stock_hub.action_hub_packing_stations"); }
    count(value) { return new Intl.NumberFormat("th-TH").format(value || 0); }
    percent(value) { return `${Math.min(100, Math.max(0, value || 0))}%`; }
    stageName(stage) { return { waiting: "รอแพ็ก", packing: "กำลังแพ็ก", packed: "แพ็กเสร็จ" }[stage] || stage; }
}

registry.category("actions").add("thai_sales_stock_hub.PackingDashboard", PackingDashboard);
