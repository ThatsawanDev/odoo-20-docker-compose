/** @odoo-module **/

import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class BomTreeNode extends Component {
    static template = "thai_mrp_easy.BomTreeNode";
    props = useProps();
}
BomTreeNode.components = { BomTreeNode };

export class VisualBomBuilder extends Component {
    static template = "thai_mrp_easy.VisualBomBuilder";
    static components = { BomTreeNode };
    props = useProps();

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        
        this.bomId = this.props?.action?.context?.default_bom_id || false;
        
        this.state = proxy({
            bom: {
                id: false,
                product_id: false,
                product_tmpl_id: false,
                product_name: "",
                product_qty: 1,
                product_uom_id: false,
                product_uom_name: "",
                image_url: "",
                code: "",
                lines: []
            },
            materialSearch: "",
            materialResults: [],
            componentMode: "material",
            mainProductSearch: "",
            mainProductResults: [],
            editingLine: false,
            nextNodeId: -1,
            examples: [],
            zoom: 1,
            bomStack: [],
        });

        onWillStart(async () => {
            if (this.bomId) {
                this.state.bom = await this.orm.call("mrp.bom", "get_visual_bom_data", [this.bomId]);
            }
            // Load initial materials
            this.state.materialResults = await this.orm.call("mrp.bom", "search_materials", [""]);
            this.state.examples = await this.orm.call("mrp.bom", "get_visual_bom_examples", []);
        });
    }

    async openExample(example) {
        this.bomId = example.id;
        this.state.bom = await this.orm.call("mrp.bom", "get_visual_bom_data", [example.id]);
    }

    changeZoom(delta) {
        this.state.zoom = Math.max(0.4, Math.min(1.5, Math.round((this.state.zoom + delta) * 10) / 10));
    }

    async cancel() {
        if (this.state.bomStack.length) {
            this.state.bom = this.state.bomStack.pop().bom;
            return;
        }
        await this.action.doAction({ type: "ir.actions.act_window", name: "สูตรการผลิต", res_model: "mrp.bom", views: [[false, "list"], [false, "form"]] });
    }

    async openSubBom(line) {
        const bomId = line.selected_bom_id || line.sub_bom?.id;
        if (!bomId) {
            return this.createSubBom(line);
        }
        this.state.bomStack.push({ bom: this.state.bom, lineKey: line.key || line.id });
        this.state.bom = await this.orm.call("mrp.bom", "get_visual_bom_data", [bomId]);
        this.state.editingLine = false;
    }

    async createSubBom(line) {
        if (line.product_id === this.state.bom.product_id) {
            this.notification.add("สินค้าเดียวกับสูตรหลักไม่สามารถเป็น BOM ย่อยได้", { type: "warning" });
            return;
        }
        const products = await this.orm.read("product.product", [line.product_id], ["product_tmpl_id", "uom_id", "default_code"]);
        const product = products[0];
        if (!product) {
            this.notification.add("ไม่พบสินค้าสำหรับสร้าง BOM ย่อย", { type: "warning" });
            return;
        }
        this.state.bomStack.push({ bom: this.state.bom, lineKey: line.key || line.id });
        this.state.bom = {
            id: false,
            product_id: line.product_id,
            product_tmpl_id: product.product_tmpl_id[0],
            product_name: line.product_name,
            product_qty: 1,
            product_uom_id: product.uom_id[0],
            product_uom_name: product.uom_id[1],
            image_url: line.image_url,
            code: product.default_code || "",
            lines: [],
        };
        this.state.editingLine = false;
    }

    printBom() {
        window.print();
    }

    async searchMainProduct(ev) {
        this.state.mainProductSearch = ev.target.value;
        if (this.state.mainProductSearch.length > 1) {
            this.state.mainProductResults = await this.orm.call("mrp.bom", "search_materials", [this.state.mainProductSearch]);
        } else {
            this.state.mainProductResults = [];
        }
    }

    selectMainProduct(product) {
        this.state.bom.product_id = product.id;
        // In a real app we'd fetch product_tmpl_id, but here we can just use the search results
        this.state.bom.product_tmpl_id = product.product_tmpl_id;
        this.state.bom.product_name = product.name;
        this.state.bom.image_url = product.image_url;
        this.state.bom.product_qty = 1;
        this.state.bom.product_uom_id = product.uom_id;
        this.state.bom.product_uom_name = product.uom_name;
        this.state.mainProductResults = [];
        this.state.mainProductSearch = "";
    }

    clearMainProduct() {
        this.bomId = false;
        this.state.bom = {
            id: false,
            product_id: false,
            product_tmpl_id: false,
            product_name: "",
            product_qty: 1,
            lines: []
        };
    }

    newBom() {
        this.clearMainProduct();
        this.state.bomStack = [];
        this.state.editingLine = false;
        this.state.materialSearch = "";
    }

    async deleteBom() {
        if (!this.state.bom.id || !window.confirm("ลบสูตรการผลิตนี้ใช่หรือไม่?")) {
            return;
        }
        try {
            await this.orm.unlink("mrp.bom", [this.state.bom.id]);
            this.notification.add("ลบสูตรการผลิตแล้ว", { type: "success" });
            this.newBom();
            this.state.examples = await this.orm.call("mrp.bom", "get_visual_bom_examples", []);
        } catch (error) {
            this.notification.add("ลบสูตรการผลิตไม่ได้: กรุณาตรวจสอบสิทธิ์หรือรายการผลิตที่อ้างอิงสูตรนี้", { type: "danger" });
            console.error(error);
        }
    }

    async searchMaterial(ev) {
        this.state.materialSearch = ev.target.value;
        await this.loadComponentResults();
    }

    async setComponentMode(mode) {
        this.state.componentMode = mode;
        this.state.materialSearch = "";
        await this.loadComponentResults();
    }

    async loadComponentResults() {
        this.state.materialResults = this.state.componentMode === "bom"
            ? await this.orm.call("mrp.bom", "search_existing_boms", [
                this.state.materialSearch, this.state.bom.id || false, this.state.bom.product_tmpl_id || false,
            ])
            : await this.orm.call("mrp.bom", "search_materials", [this.state.materialSearch]);
    }

    focusMaterialSearch() {
        this.state.componentMode = "material";
        this.loadComponentResults();
        document.querySelector(".visual-bom-container .vb-material-search")?.focus();
    }

    addMaterial(material) {
        // Open edit popup directly instead of adding instantly
        this.state.editingLine = {
            key: this.state.nextNodeId--,
            product_id: material.id,
            product_name: material.name,
            product_qty: 1,
            product_uom_id: material.uom_id,
            product_uom_name: material.uom_name,
            image_url: material.image_url,
            has_bom: material.has_bom,
            selected_bom_id: material.bom_id || false,
            sub_bom: null, // We'll fetch this upon save or backend save
            isNew: true
        };
    }

    editLine(line) {
        this.state.editingLine = Object.assign({}, line, {isNew: false});
    }

    setBomQty(ev) {
        this.state.bom.product_qty = Math.max(1, Number(ev.target.value) || 1);
    }

    setLineQty(ev) {
        this.state.editingLine.product_qty = Math.max(0, Number(ev.target.value) || 0);
    }

    removeLine(line) {
        if (!window.confirm(`ลบ ${line.product_name} ออกจากสูตรนี้ใช่หรือไม่?`)) {
            return;
        }
        const index = this.state.bom.lines.findIndex(l => l.key === line.key || l.id === line.id);
        if (index > -1) {
            this.state.bom.lines.splice(index, 1);
        }
    }

    closeEditPopup() {
        this.state.editingLine = false;
    }

    async saveLineEdit() {
        const line = this.state.editingLine;
        
        // If it has a BOM and it's new, we need to fetch the sub_bom structure to display it
        if (line.selected_bom_id && !line.sub_bom) {
            line.sub_bom = await this.orm.call("mrp.bom", "get_visual_bom_data", [line.selected_bom_id]);
        } else if (line.has_bom && !line.sub_bom) {
             const subBoms = await this.orm.searchRead("mrp.bom", [["product_id", "=", line.product_id]], ["id"], {limit: 1});
             if (subBoms.length > 0) {
                 line.sub_bom = await this.orm.call("mrp.bom", "get_visual_bom_data", [subBoms[0].id]);
             } else {
                 // Try by product_tmpl_id
                 const prods = await this.orm.searchRead("product.product", [["id", "=", line.product_id]], ["product_tmpl_id"]);
                 if (prods.length > 0) {
                     const subBomsTmpl = await this.orm.searchRead("mrp.bom", [["product_tmpl_id", "=", prods[0].product_tmpl_id[0]]], ["id"], {limit: 1});
                     if (subBomsTmpl.length > 0) {
                         line.sub_bom = await this.orm.call("mrp.bom", "get_visual_bom_data", [subBomsTmpl[0].id]);
                     }
                 }
             }
        }

        if (line.isNew) {
            delete line.isNew;
            this.state.bom.lines.push(line);
        } else {
            delete line.isNew;
            const index = this.state.bom.lines.findIndex(l => l.key === line.key || l.id === line.id);
            if (index > -1) {
                this.state.bom.lines[index] = line;
            }
        }
        this.state.editingLine = false;
    }

    async saveBom() {
        if (!this.state.bom.product_id) {
            this.notification.add("กรุณาเลือกสินค้าที่จะผลิต", { type: "warning" });
            return;
        }
        
        // We need product_tmpl_id. If we don't have it (new creation), fetch it.
        if (!this.state.bom.product_tmpl_id) {
            const prods = await this.orm.searchRead("product.product", [["id", "=", this.state.bom.product_id]], ["product_tmpl_id"]);
            if (prods.length > 0) {
                this.state.bom.product_tmpl_id = prods[0].product_tmpl_id[0];
            }
        }

        try {
            const newBomId = await this.orm.call("mrp.bom", "save_visual_bom", [this.state.bom]);
            this.state.bom.id = newBomId;
            this.notification.add("บันทึกสูตรการผลิต (BOM) เรียบร้อยแล้ว", { type: "success" });
            
            // Reload the view
            const savedBom = await this.orm.call("mrp.bom", "get_visual_bom_data", [newBomId]);
            if (this.state.bomStack.length) {
                const parent = this.state.bomStack.pop();
                const line = parent.bom.lines.find((item) => (item.key || item.id) === parent.lineKey);
                if (line) {
                    line.selected_bom_id = newBomId;
                    line.has_bom = true;
                    line.sub_bom = savedBom;
                }
                this.state.bom = parent.bom;
            } else {
                this.state.bom = savedBom;
            }
            this.state.examples = await this.orm.call("mrp.bom", "get_visual_bom_examples", []);
        } catch (error) {
            this.notification.add("เกิดข้อผิดพลาดในการบันทึก", { type: "danger" });
            console.error(error);
        }
    }
}

registry.category("actions").add("thai_mrp_easy.VisualBomBuilder", VisualBomBuilder);
