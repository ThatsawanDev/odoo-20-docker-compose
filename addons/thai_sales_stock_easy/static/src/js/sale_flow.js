/** @odoo-module **/

import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ThaiSaleFlow extends Component {
    static template = "thai_sales_stock_easy.SaleFlow";
    props = useProps();
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = proxy({ loading: true, busy: false, order: {}, modal: "", journals: [],
            payment: { journal_id: 0, amount: 0, date: this.today(), memo: "" },
            invoice: { date: this.today(), due_date: "" } });
        onWillStart(async () => {
            const id = this.props?.action?.params?.order_id || this.props?.action?.context?.active_id;
            if (!id) return this.action.doAction("thai_sales_stock_easy.action_sales_order");
            await this.load(id);
        });
    }
    today() { return new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10); }
    async load(id) { this.state.order = await this.orm.call("thai.sales.stock.flow", "get_order_flow", [id]); this.state.loading = false; }
    money(value) { return new Intl.NumberFormat("th-TH", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value || 0); }
    async run(method, kwargs = {}) {
        this.state.busy = true;
        try {
            this.state.order = await this.orm.call("thai.sales.stock.flow", method, [this.state.order.id], kwargs);
            this.state.modal = "";
            this.notification.add("ดำเนินการเรียบร้อยแล้ว", { type: "success" });
        } finally { this.state.busy = false; }
    }
    confirmSale() { return this.run("confirm_and_deliver"); }
    async openCash() {
        if (!this.state.order.invoiced) await this.run("create_invoice");
        this.state.journals = await this.orm.call("thai.sales.stock.flow", "get_payment_options", []);
        this.state.payment = { journal_id: this.state.journals[0]?.id || 0, amount: this.state.order.residual,
            date: this.today(), memo: "" };
        this.state.modal = "payment";
    }
    openCredit() { this.state.invoice = { date: this.today(), due_date: "" }; this.state.modal = "invoice"; }
    createInvoice() { return this.run("create_invoice", { invoice_date: this.state.invoice.date, due_date: this.state.invoice.due_date || false }); }
    pay() { return this.run("register_payment", { journal_id: this.state.payment.journal_id,
        amount: this.state.payment.amount, payment_date: this.state.payment.date, memo: this.state.payment.memo }); }
    cancel() { return this.run("cancel_order"); }
    back() { return this.action.doAction("thai_sales_stock_easy.action_sales_order"); }
    printInvoice() { if (this.state.order.invoice_id) return this.action.doAction({ type: "ir.actions.act_window",
        res_model: "account.move", res_id: this.state.order.invoice_id, views: [[false, "form"]], target: "current" }); }
}

registry.category("actions").add("thai_sales_stock_easy.SaleFlow", ThaiSaleFlow);
