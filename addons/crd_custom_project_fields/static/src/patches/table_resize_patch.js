import { patch } from "@web/core/utils/patch";
import { TableResizePlugin } from "@html_editor/main/table/table_resize_plugin";
import { getColumnIndex } from "@html_editor/utils/table";
import { closestElement } from "@html_editor/utils/dom_traversal";

patch(TableResizePlugin.prototype, {
    resizeTable(ev, direction, target1, target2) {
        const item = target1 || target2;
        if (!item) return;

        if (direction === "col") {
            const table = closestElement(item, "table");
            if (!table) return;
            const firstRow = table.querySelector("tr");
            if (!firstRow) return;
            const nthColumn = getColumnIndex(item);
            if (nthColumn >= firstRow.children.length) return;
        }

        return super.resizeTable(ev, direction, target1, target2);
    },
});
