/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { onWillStart, proxy } from "@odoo/owl";

class OutgoingListController extends ListController {
    static template = "thai_sales_stock_hub.OutgoingListView";

    setup() {
        super.setup();
        this.outgoingSummary = proxy({ all: 0, waiting: 0, packing: 0, packed: 0, issues: 0 });
        onWillStart(async () => {
            Object.assign(this.outgoingSummary, await this.orm.call("stock.picking", "get_hub_outgoing_summary", []));
        });
    }
}

registry.category("views").add("hub_outgoing_list", {
    ...listView,
    Controller: OutgoingListController,
});
