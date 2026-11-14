/** @odoo-module **/

// The portal header belongs to the website layout, outside the sale template.
// Read the actual order company from the rendered sale template.
function showOrderCompany() {
    const page = document.querySelector(".o_thai_sale_portal[data-company-name]");
    const brand = document.querySelector("header .navbar-brand");
    if (!page || !brand || !page.dataset.companyName) return;
    brand.replaceChildren(document.createTextNode(page.dataset.companyName));
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showOrderCompany, { once: true });
} else {
    showOrderCompany();
}
