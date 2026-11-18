/** @odoo-module **/

import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TbfOverviewDashboard extends Component {
    static template = "tbf_navigation.OverviewDashboard";
    props = useProps();

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.searchTimer = null;

        this.state = proxy({
            loading: true,
            period: "month",
            search: "",
            activeTab: "all",
            activeStage: "",
            stages: [],
            tabCounts: { all: 0, in_progress: 0, shipped: 0, partial: 0 },
            orders: [],
            selectedIds: [],
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const result = await this.orm.call(
                "tbf.overview.dashboard",
                "get_overview_data",
                [],
                { period: this.state.period, search: this.state.search }
            );
            this.state.stages = result.stages || [];
            this.state.tabCounts = result.tab_counts || { all: 0, in_progress: 0, shipped: 0, partial: 0 };
            this.state.orders = result.orders || [];
        } finally {
            this.state.loading = false;
        }
    }

    get filteredOrders() {
        let list = this.state.orders;
        if (this.state.activeStage && this.state.activeStage !== "so") {
            list = list.filter((o) => o.stage_key === this.state.activeStage);
        }
        if (this.state.activeTab === "in_progress") {
            list = list.filter((o) => o.tab_key === "in_progress");
        } else if (this.state.activeTab === "shipped") {
            list = list.filter((o) => o.tab_key === "shipped");
        } else if (this.state.activeTab === "partial") {
            list = list.filter((o) => o.is_partial);
        }
        return list;
    }

    get allSelected() {
        const list = this.filteredOrders;
        return list.length > 0 && list.every((o) => this.state.selectedIds.includes(o.id));
    }

    toggleSelectAll(ev) {
        const checked = ev.target.checked;
        if (checked) {
            this.state.selectedIds = this.filteredOrders.map((o) => o.id);
        } else {
            this.state.selectedIds = [];
        }
    }

    toggleSelectRow(id) {
        if (this.state.selectedIds.includes(id)) {
            this.state.selectedIds = this.state.selectedIds.filter((x) => x !== id);
        } else {
            this.state.selectedIds = [...this.state.selectedIds, id];
        }
    }

    async onPeriodChange(ev) {
        this.state.period = ev.target.value;
        await this.loadData();
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        if (this.searchTimer) {
            clearTimeout(this.searchTimer);
        }
        this.searchTimer = setTimeout(() => {
            this.loadData();
        }, 250);
    }

    selectTab(tabKey) {
        this.state.activeTab = tabKey;
        if (tabKey === "all") {
            this.state.activeStage = "";
        }
    }

    selectStage(stageKey) {
        if (stageKey === "so") {
            this.state.activeStage = "";
            this.state.activeTab = "all";
            return;
        }
        this.state.activeStage = this.state.activeStage === stageKey ? "" : stageKey;
        this.state.activeTab = "all";
    }

    openSaleOrder(orderId) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sale.order",
            res_id: orderId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openEpoOrOrder(order) {
        if (order.active_epo_id) {
            return this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "tbf.epo",
                res_id: order.active_epo_id,
                views: [[false, "form"]],
                target: "current",
            });
        }
        return this.openSaleOrder(order.id);
    }

    canOpenStep(order, stepKey) {
        if (stepKey === "so") {
            return true;
        }
        if (stepKey === "awaiting") {
            return Boolean(order.internal_picking_id || order.active_epo_id);
        }
        if (stepKey === "shipped") {
            return Boolean(order.shipment_picking_id || order.active_epo_id);
        }
        return Boolean(order.active_epo_id);
    }

    openStepDocument(order, stepKey) {
        if (stepKey === "so") {
            return this.openSaleOrder(order.id);
        }
        if (stepKey === "awaiting" && order.internal_picking_id) {
            return this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "stock.picking",
                res_id: order.internal_picking_id,
                views: [[false, "form"]],
                target: "current",
            });
        }
        if (stepKey === "shipped" && order.shipment_picking_id) {
            return this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "stock.picking",
                res_id: order.shipment_picking_id,
                views: [[false, "form"]],
                target: "current",
            });
        }
        return this.openEpoOrOrder(order);
    }
}

registry.category("actions").add("tbf_navigation.overview_dashboard", TbfOverviewDashboard);
