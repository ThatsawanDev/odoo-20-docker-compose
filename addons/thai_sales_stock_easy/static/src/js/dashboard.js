/** @odoo-module **/

import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ThaiSalesStockDashboard extends Component {
    static template = "thai_sales_stock_easy.Dashboard";
    props = useProps();

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.nextLineKey = 1;
        this.state = proxy({ loading: true, data: {}, quotationOpen: false, saving: false,
            formData: { customers: [], products: [], currency: "" },
            newCustomer: false,
            customerSearch: "",
            customerResultsOpen: false,
            productSearch: "",
            categoryId: 0,
            customer: { name: "", phone: "", street: "", city: "", zip: "" },
            totals: { untaxed: 0, tax: 0, total: 0, tax_label: "ไม่มี VAT" },
            quote: { partner_id: 0, note: "", validity_date: "", lines: [] } });
        onWillStart(async () => {
            this.state.data = await this.orm.call("thai.sales.stock.dashboard", "get_dashboard_data", []);
            this.state.loading = false;
            if (this.props?.action?.params?.open_sale_page) {
                await this.createQuotation();
            }
        });
    }

    open(xmlId) {
        return this.action.doAction(xmlId);
    }

    openSaleOrder(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "sale.order",
            res_id: id, views: [[false, "form"]], target: "current" });
    }

    openProduct(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "product.product",
            res_id: id, views: [[false, "form"]], target: "current" });
    }

    async createQuotation() {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "ใบเสนอราคาใหม่",
            res_model: "sale.order",
            views: [[false, "form"]],
            target: "current",
            context: { default_state: "draft" },
        });
    }

    dateInput(date) {
        const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
        return local.toISOString().slice(0, 10);
    }

    closeQuotation() { this.state.quotationOpen = false; }

    addQuoteLine() {
        this.state.quote.lines.push({ key: this.nextLineKey++, product_id: 0, quantity: 1, price: 0, uom: "" });
    }

    addProduct(product) {
        const line = this.state.quote.lines.find((item) => item.product_id === product.id && item.uom_id === product.uom_id);
        if (line) {
            line.quantity += 1;
        } else {
            this.state.quote.lines.push({ key: this.nextLineKey++, product_id: product.id, uom_id: product.uom_id,
                name: product.name, quantity: 1, price: product.price, uom: product.uom });
        }
        this.refreshTotals();
    }

    removeQuoteLine(index) {
        this.state.quote.lines.splice(index, 1);
        this.refreshTotals();
    }

    searchCustomer(value) {
        this.state.customerSearch = value;
        this.state.quote.partner_id = 0;
        this.state.customerResultsOpen = true;
    }
    openCustomerSearch() { this.state.customerResultsOpen = true; }
    customerMatches() {
        const query = this.state.customerSearch.trim().toLocaleLowerCase("th-TH");
        if (!query) return this.state.formData.customers.slice(0, 8);
        const phoneQuery = query.replace(/[^0-9]/g, "");
        return this.state.formData.customers.filter((customer) =>
            customer.name.toLocaleLowerCase("th-TH").includes(query) ||
            (phoneQuery && (customer.phone || "").replace(/[^0-9]/g, "").includes(phoneQuery))
        ).slice(0, 12);
    }
    selectCustomer(customer) {
        this.state.quote.partner_id = customer.id;
        this.state.customerSearch = customer.phone ? `${customer.name} — ${customer.phone}` : customer.name;
        this.state.customerResultsOpen = false;
        this.refreshTotals();
    }
    selectedCustomer() {
        return this.state.formData.customers.find((customer) => customer.id === this.state.quote.partner_id);
    }
    categories() {
        const counts = new Map();
        for (const product of this.state.formData.products) {
            if (!counts.has(product.category_id)) counts.set(product.category_id, { id: product.category_id, name: product.category, count: 0 });
            counts.get(product.category_id).count += 1;
        }
        return [...counts.values()];
    }
    filteredProducts() {
        const query = this.state.productSearch.trim().toLocaleLowerCase("th-TH");
        return this.state.formData.products.filter((product) =>
            (!this.state.categoryId || product.category_id === this.state.categoryId) &&
            (!query || product.name.toLocaleLowerCase("th-TH").includes(query))
        );
    }
    setCategory(id) { this.state.categoryId = id; }
    setProductSearch(value) { this.state.productSearch = value; }
    setValidityDate(value) { this.state.quote.validity_date = value; }
    toggleNewCustomer() {
        this.state.newCustomer = !this.state.newCustomer;
        if (this.state.newCustomer) {
            this.state.quote.partner_id = 0;
            this.state.customerSearch = "";
            this.state.customerResultsOpen = false;
        }
        this.refreshTotals();
    }
    setCustomerField(field, value) { this.state.customer[field] = value; }

    setProduct(line, value) {
        const product = this.state.formData.products.find((item) => item.id === Number(value));
        line.product_id = product?.id || 0;
        line.price = product?.price || 0;
        line.uom = product?.uom || "";
    }

    setQuantity(line, value) { line.quantity = Number(value) || 0; this.refreshTotals(); }
    adjustQuantity(line, change) {
        line.quantity = Math.max(1, (Number(line.quantity) || 1) + change);
        this.refreshTotals();
    }
    setPrice(line, value) { line.price = Number(value) || 0; }
    setNote(value) { this.state.quote.note = value; }

    quoteTotal() {
        return this.state.quote.lines.reduce((sum, line) => sum + (Number(line.quantity) || 0) * (Number(line.price) || 0), 0);
    }

    async refreshTotals() {
        this.state.totals = await this.orm.call("thai.sales.stock.dashboard", "get_quick_quotation_totals", [], {
            partner_id: this.state.quote.partner_id,
            lines: this.state.quote.lines,
        });
    }

    async saveQuotation() {
        this.state.saving = true;
        try {
            const result = await this.orm.call("thai.sales.stock.dashboard", "create_quick_quotation", [], {
                partner_id: this.state.quote.partner_id,
                lines: this.state.quote.lines,
                note: this.state.quote.note,
                customer_data: this.state.newCustomer ? this.state.customer : {},
                validity_date: this.state.quote.validity_date,
            });
            this.notification.add(`บันทึก ${result.name} เรียบร้อยแล้ว`, { type: "success" });
            this.state.quotationOpen = false;
            this.state.data = await this.orm.call("thai.sales.stock.dashboard", "get_dashboard_data", []);
            await this.action.doAction("thai_sales_stock_easy.action_quotation");
        } finally {
            this.state.saving = false;
        }
    }

    money(value) {
        return new Intl.NumberFormat("th-TH", { maximumFractionDigits: 2 }).format(value || 0);
    }
}

registry.category("actions").add("thai_sales_stock_easy.Dashboard", ThaiSalesStockDashboard);
