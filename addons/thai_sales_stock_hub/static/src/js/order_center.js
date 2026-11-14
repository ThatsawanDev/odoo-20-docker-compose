/** @odoo-module **/

import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

export class OrderCenter extends Component {
    static template = "thai_sales_stock_hub.OrderCenter";
    props = useProps();

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({ loading: true, data: {}, search: "", channel: "", status: "",
            dateFrom: "", dateTo: "", page: 1, selectedId: 0, companyOpen: false });
        onWillStart(() => this.refresh());
    }

    async refresh() {
        this.state.loading = true;
        const data = await this.orm.call("thai.sales.stock.order.center", "get_data", [], {
            search: this.state.search, channel: this.state.channel, status: this.state.status,
            date_from: this.state.dateFrom, date_to: this.state.dateTo,
            page: this.state.page, selected_id: this.state.selectedId,
        });
        this.state.data = data;
        this.state.page = data.page;
        this.state.selectedId = data.detail?.id || 0;
        this.state.loading = false;
    }

    setSearch(ev) { this.state.search = ev.target.value; this.state.page = 1; this.refresh(); }
    setChannel(key) { this.state.channel = key; this.state.page = 1; this.refresh(); }
    setStatus(key) { this.state.status = key; this.state.page = 1; this.refresh(); }
    setDateFrom(ev) { this.state.dateFrom = ev.target.value; this.state.page = 1; this.refresh(); }
    setDateTo(ev) { this.state.dateTo = ev.target.value; this.state.page = 1; this.refresh(); }
    setPage(page) { this.state.page = page; this.refresh(); }
    selectOrder(id) { this.state.selectedId = id; this.refresh(); }
    resetFilters() {
        Object.assign(this.state, { search: "", channel: "", status: "", dateFrom: "", dateTo: "", page: 1 });
        this.refresh();
    }
    open(xmlid) { return this.action.doAction(xmlid); }
    get companyOptions() { return user.allowedCompanies; }
    isCompanyActive(id) { return user.activeCompanies.some((company) => company.id === id); }
    toggleCompanies() { this.state.companyOpen = !this.state.companyOpen; }
    async toggleCompany(id) {
        const active = user.activeCompanies.map((company) => company.id);
        const next = active.includes(id) ? active.filter((companyId) => companyId !== id) : [...active, id];
        if (next.length === 0) return;
        await user.activateCompanies(next, { includeChildCompanies: false, reload: true });
    }
    openOrder(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "sale.order",
            res_id: id, views: [[false, "form"]], target: "current" });
    }
    openDelivery(detail) {
        if (detail.picking_ids?.length === 1) {
            return this.action.doAction({ type: "ir.actions.act_window", res_model: "stock.picking",
                res_id: detail.picking_ids[0], views: [[false, "form"]], target: "current" });
        }
        return this.openOrder(detail.id);
    }
    money(value) { return new Intl.NumberFormat("th-TH", { maximumFractionDigits: 2 }).format(value || 0); }
    pageStart() { return this.state.data.total ? (this.state.data.page - 1) * this.state.data.page_size + 1 : 0; }
    pageEnd() { return Math.min(this.state.data.total || 0, (this.state.data.page || 1) * (this.state.data.page_size || 25)); }
}

registry.category("actions").add("thai_sales_stock_hub.OrderCenter", OrderCenter);
