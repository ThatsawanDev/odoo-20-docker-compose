/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { onWillStart, proxy } from "@odoo/owl";

class ThaiMrpOrderListController extends ListController {
    static template = "thai_mrp_easy.MrpOrderListView";

    setup() {
        super.setup();
        this.moSummary = proxy({
            draft: 0, confirmed: 0, progress: 0, material_waiting: 0, done_today: 0,
        });
        onWillStart(async () => {
            Object.assign(this.moSummary, await this.orm.call("mrp.production", "get_easy_list_summary", []));
        });
    }
}

registry.category("views").add("thai_mrp_order_list", {
    ...listView,
    Controller: ThaiMrpOrderListController,
});
