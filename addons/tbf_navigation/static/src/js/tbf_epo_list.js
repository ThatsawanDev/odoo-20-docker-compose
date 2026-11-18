/** @odoo-module **/

import { onWillStart, proxy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";

export class TbfEpoListController extends ListController {
    static template = "tbf_navigation.EpoListView";

    setup() {
        super.setup();
        this.epoSummary = proxy({
            activeState: "",
            all: 0,
            new: 0,
            confirmed: 0,
            verified: 0,
            ready: 0,
            shipped: 0,
        });
        onWillStart(async () => {
            const counts = await this.orm.call(
                "tbf.epo",
                "get_epo_dashboard_counts",
                [],
                { base_domain: this.props.domain || [] }
            );
            Object.assign(this.epoSummary, counts);
        });
    }

    filterState(stateKey) {
        const next = stateKey && this.epoSummary.activeState === stateKey ? "" : stateKey;
        this.epoSummary.activeState = next;
        const stateItems = this.env.searchModel.getSearchItems(
            (item) => item.type === "filter" && item.name && item.name.startsWith("state_")
        );
        for (const item of stateItems) {
            if (item.isActive) {
                this.env.searchModel.toggleSearchItem(item.id);
            }
        }
        if (next) {
            const target = stateItems.find((item) => item.name === `state_${next}`);
            if (target) {
                this.env.searchModel.toggleSearchItem(target.id);
            }
        }
    }
}

registry.category("views").add("tbf_epo_list", {
    ...listView,
    Controller: TbfEpoListController,
});
