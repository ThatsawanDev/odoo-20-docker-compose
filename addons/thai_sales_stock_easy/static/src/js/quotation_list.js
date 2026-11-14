/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { onWillStart, proxy } from "@odoo/owl";

export class ThaiQuotationListController extends ListController {
    static template = "thai_sales_stock_easy.QuotationListView";

    setup() {
        super.setup();
        this.saleSummary = proxy({ draft: 0, sent: 0, confirmed: 0, month_total: 0, currency: "" });
        onWillStart(async () => {
            Object.assign(this.saleSummary, await this.orm.call("sale.order", "get_thai_list_summary", []));
        });
    }

    get monthTotalText() {
        return new Intl.NumberFormat("th-TH", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(this.saleSummary.month_total);
    }

    async createRecord() {
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "ใบเสนอราคาใหม่",
            res_model: "sale.order",
            views: [[false, "form"]],
            target: "current",
            context: { default_state: "draft" },
        });
    }

}

registry.category("views").add("thai_quotation_list", {
    ...listView,
    Controller: ThaiQuotationListController,
});
