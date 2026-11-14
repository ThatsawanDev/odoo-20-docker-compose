/** @odoo-module **/

import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DAY_MS = 24 * 60 * 60 * 1000;
const DAY_WIDTH = 42;

function iso(date) {
    return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"),
        String(date.getDate()).padStart(2, "0")].join("-");
}

function utcDay(value) {
    return Date.parse(`${value}T00:00:00Z`);
}

export class ManufacturingGantt extends Component {
    static template = "thai_mrp_easy.ManufacturingGantt";
    props = useProps();

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({ loading: true, scale: "month", anchor: new Date(), days: [], orders: [], title: "" });
        onWillStart(() => this.load());
    }

    period() {
        const anchor = this.state.anchor;
        let first;
        let count;
        if (this.state.scale === "week") {
            first = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate());
            first.setDate(first.getDate() - (first.getDay() + 6) % 7);
            count = 14;
        } else {
            first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
            count = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0).getDate();
        }
        const days = Array.from({ length: count }, (_, index) => {
            const date = new Date(first.getFullYear(), first.getMonth(), first.getDate() + index);
            return {
                iso: iso(date),
                day: date.getDate(),
                weekday: new Intl.DateTimeFormat("th-TH", { weekday: "short" }).format(date),
                weekend: [0, 6].includes(date.getDay()),
                today: iso(date) === iso(new Date()),
            };
        });
        const last = days[days.length - 1];
        const title = this.state.scale === "week"
            ? `${days[0].day} ${new Intl.DateTimeFormat("th-TH", { month: "short" }).format(first)} – ${last.day} ${new Intl.DateTimeFormat("th-TH", { month: "short", year: "numeric" }).format(new Date(last.iso))}`
            : new Intl.DateTimeFormat("th-TH", { month: "long", year: "numeric" }).format(first);
        return { days, title };
    }

    async load() {
        this.state.loading = true;
        const { days, title } = this.period();
        this.state.days = days;
        this.state.title = title;
        this.state.orders = await this.orm.call("thai.mrp.easy.plan", "get_plan_data", [days[0].iso, days[days.length - 1].iso]);
        this.state.loading = false;
    }

    async navigate(direction) {
        const anchor = this.state.anchor;
        this.state.anchor = this.state.scale === "week"
            ? new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate() + direction * 14)
            : new Date(anchor.getFullYear(), anchor.getMonth() + direction, 1);
        await this.load();
    }

    async today() {
        this.state.anchor = new Date();
        await this.load();
    }

    async setScale(scale) {
        this.state.scale = scale;
        await this.load();
    }

    barStyle(order) {
        const first = utcDay(this.state.days[0].iso);
        const start = Math.max(0, Math.round((utcDay(order.start) - first) / DAY_MS));
        const end = Math.min(this.state.days.length - 1, Math.round((utcDay(order.end) - first) / DAY_MS));
        return `left:${start * DAY_WIDTH + 3}px;width:${Math.max(12, (end - start + 1) * DAY_WIDTH - 6)}px`;
    }

    openOrder(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "mrp.production",
            res_id: id, views: [[false, "form"]], target: "current" });
    }

    newOrder() {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "mrp.production",
            views: [[false, "form"]], target: "current" });
    }

    openCalendar() {
        return this.action.doAction("thai_mrp_easy.action_thai_manufacturing_plan");
    }
}

registry.category("actions").add("thai_mrp_easy.ManufacturingGantt", ManufacturingGantt);
