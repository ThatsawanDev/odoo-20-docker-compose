/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, signal, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PackingStation extends Component {
    static template = "thai_sales_stock_hub.PackingStation";
    props = useProps();

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.initialPickingId = this.props?.action?.params?.picking_id || false;
        this.camera = signal.ref();
        this.state = proxy({ loading: true, queue: [], stations: [], stationId: false, order: null, canManageStations: false,
            barcode: "", cameraOn: false, recording: false, paused: false, saving: false, error: "", user: "" });
        this.stream = null;
        this.recorder = null;
        this.chunks = [];
        onWillStart(() => this.load(this.initialPickingId));
        onWillUnmount(() => this.stopCamera());
    }

    async load(preferredId = false) {
        this.state.loading = true;
        try {
            let result = await this.orm.call("thai.sales.stock.hub.packing.dashboard", "get_station_queue", [this.state.stationId]);
            if (!this.state.stationId && result.stations.length === 1) {
                this.state.stationId = result.stations[0].id;
                result = await this.orm.call("thai.sales.stock.hub.packing.dashboard", "get_station_queue", [this.state.stationId]);
            }
            this.state.stations = result.stations;
            this.state.canManageStations = result.can_manage_stations;
            this.state.queue = result.queue;
            this.state.user = result.user;
            if (preferredId && !result.queue.some(row => row.id === preferredId)) {
                const selected = await this.orm.call("thai.sales.stock.hub.packing.dashboard", "get_station_order", [preferredId]);
                result.queue.unshift({ id: selected.id, name: selected.name, customer: selected.customer,
                    state: selected.state, station_id: selected.station_id });
                this.state.queue = result.queue;
            }
            const id = preferredId || this.state.order?.id || result.queue[0]?.id;
            this.state.order = id && result.queue.some(row => row.id === id)
                ? await this.orm.call("thai.sales.stock.hub.packing.dashboard", "get_station_order", [id]) : null;
        } catch (error) { this.showError(error); }
        this.state.loading = false;
    }

    async selectStation(ev) {
        this.state.stationId = ev.target.value ? Number(ev.target.value) : false;
        this.state.order = null;
        await this.load();
    }

    async selectOrder(ev) {
        const id = Number(ev.target.value);
        if (id) this.state.order = await this.orm.call("thai.sales.stock.hub.packing.dashboard", "get_station_order", [id]);
    }

    async moveQueue(delta) {
        const index = this.state.queue.findIndex(row => row.id === this.state.order?.id);
        const next = this.state.queue[index + delta];
        if (next) this.state.order = await this.orm.call("thai.sales.stock.hub.packing.dashboard", "get_station_order", [next.id]);
    }

    showError(error) {
        const message = error?.data?.message || error?.message || "เกิดข้อผิดพลาด";
        this.state.error = message;
        this.notification.add(message, { type: "danger" });
    }

    async startOrder() {
        if (!this.state.stationId) { this.notification.add("กรุณาเลือกจุดแพ็ก", { type: "warning" }); return; }
        try {
            this.state.order = await this.orm.call("thai.sales.stock.hub.packing.dashboard", "start_station_order", [this.state.order.id, this.state.stationId]);
            await this.load(this.state.order.id);
        } catch (error) { this.showError(error); }
    }

    async scan(ev) {
        ev.preventDefault();
        const code = this.state.barcode.trim();
        if (!code || !this.state.order) return;
        try {
            this.state.order = await this.orm.call("thai.sales.stock.hub.packing.dashboard", "scan_station_product", [this.state.order.id, code]);
            this.state.barcode = "";
            this.state.error = "";
        } catch (error) { this.showError(error); }
    }

    async startCamera() {
        try {
            if (!navigator.mediaDevices?.getUserMedia) throw new Error("เบราว์เซอร์ไม่รองรับกล้อง หรือไม่ได้เปิดผ่าน HTTPS/localhost");
            this.stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
            this.state.cameraOn = true;
            if (this.camera()) { this.camera().srcObject = this.stream; await this.camera().play(); }
        } catch (error) { this.showError(error); }
    }

    stopCamera() {
        if (this.recorder?.state === "recording") this.recorder.stop();
        if (this.stream) this.stream.getTracks().forEach(track => track.stop());
        this.stream = null;
        this.state.cameraOn = false;
    }

    async startRecording() {
        if (!this.state.order || this.state.order.state !== "packing") return;
        if (!this.stream) await this.startCamera();
        if (!this.stream) return;
        try {
            const mime = MediaRecorder.isTypeSupported("video/webm") ? "video/webm" : "video/mp4";
            const orderId = this.state.order.id;
            const orderName = this.state.order.name;
            this.recorder = new MediaRecorder(this.stream, { mimeType: mime });
            this.chunks = [];
            this.recorder.ondataavailable = event => { if (event.data.size) this.chunks.push(event.data); };
            this.recorder.onstop = async () => {
                this.state.recording = false;
                this.state.paused = false;
                await this.uploadBlob(new Blob(this.chunks, { type: mime }), `packing-${orderName}.${mime === 'video/mp4' ? 'mp4' : 'webm'}`, orderId);
            };
            this.recorder.start(1000);
            this.state.recording = true;
        } catch (error) { this.showError(error); }
    }

    pauseRecording() {
        if (!this.recorder) return;
        if (this.recorder.state === "recording") { this.recorder.pause(); this.state.paused = true; }
        else if (this.recorder.state === "paused") { this.recorder.resume(); this.state.paused = false; }
    }

    stopRecording() {
        if (this.recorder?.state === "recording" || this.recorder?.state === "paused") this.recorder.stop();
    }

    async uploadFile(ev) {
        const file = ev.target.files?.[0];
        if (file) await this.uploadBlob(file, file.name);
        ev.target.value = "";
    }

    async uploadBlob(blob, name, orderId = this.state.order?.id) {
        if (!blob.size || blob.size > 50 * 1024 * 1024) {
            this.notification.add("วิดีโอต้องมีขนาดไม่เกิน 50 MB", { type: "warning" }); return;
        }
        this.state.saving = true;
        try {
            const data = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(String(reader.result).split(",")[1]);
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
            const result = await this.orm.call("thai.sales.stock.hub.packing.dashboard", "save_station_video",
                [orderId, name, data, blob.type]);
            if (this.state.order?.id === orderId) this.state.order = result;
            this.notification.add("บันทึกวิดีโอเรียบร้อย", { type: "success" });
        } catch (error) { this.showError(error); }
        this.state.saving = false;
    }

    async nextBox() {
        try { this.state.order = await this.orm.call("thai.sales.stock.hub.packing.dashboard", "next_station_box", [this.state.order.id]); }
        catch (error) { this.showError(error); }
    }

    async finish() {
        try {
            await this.orm.call("thai.sales.stock.hub.packing.dashboard", "finish_station_order", [this.state.order.id]);
            this.notification.add("ยืนยันแพ็กเรียบร้อย", { type: "success" });
            this.stopCamera();
            this.state.order = null;
            await this.load();
        } catch (error) { this.showError(error); }
    }

    openPicking() {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "stock.picking", res_id: this.state.order.id,
            views: [[false, "form"]], target: "current" });
    }

    openVideoHistory() {
        return this.action.doAction({ type: "ir.actions.act_window", name: "Packing Video History",
            res_model: "thai.sales.stock.packing.video", views: [[false, "list"], [false, "form"]],
            domain: [["picking_id", "=", this.state.order.id]], target: "current" });
    }

    get scannedTotal() { return this.state.order?.lines.reduce((sum, row) => sum + row.scanned, 0) || 0; }
    get requiredTotal() { return this.state.order?.lines.reduce((sum, row) => sum + row.required, 0) || 0; }
    get complete() { return !!this.state.order?.lines.length && this.state.order.lines.every(row => row.scanned >= row.required); }
    get position() { return this.state.queue.findIndex(row => row.id === this.state.order?.id) + 1; }
}

registry.category("actions").add("thai_sales_stock_hub.PackingStation", PackingStation);
