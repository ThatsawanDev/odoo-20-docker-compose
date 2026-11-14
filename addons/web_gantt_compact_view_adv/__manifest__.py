# -*- coding: utf-8 -*-
#################################################################################
# Author      : CFIS (<https://www.cfis.store/>)
# Copyright(c): 2017-Present CFIS.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://www.cfis.store/>
#################################################################################

{
    "name": "Gantt View for Project Tasks, Sales and Time Off",
    "summary": """
        The Planning view gives you a clear overview of what is already planned and 
        what remains to be planned using Start Date and End Date. It has  
        Project Task, Time Off and Sale Order Gantt views
    """,
    "version": "20.0.1.0.0",
    "description": """
        Project Gantt View
        ==================
        The Planning view gives you a clear overview of what is already planned and 
        what remains to be planned using Start Date and End Date. It has  
        Project Task, Time Off and Sale Order Gantt views
        - Gantt View
        - create new Task
        - customize an existing Tasks
        - TreeView for Gantt Items
        - Task Deadline Indicator
        - Task Priority Indicator
        - Task Progress Indicator
        - Multiple Scales
        - Navigate to Todat, Previous and Next Day
        - Grouping Task/Project
        - Filter
        - Progress bar on Task
        - Popup Task Informations
        - Overdue Indicator
        - Milestone Task in Different Shape
        - Predecessor Links
        - Todyas Marker
        - Sorting
        - Gantt View
        - Project Gantt
        - Project Gantt View
        - Gantt view Project
    """,    
    "author": "CFIS",
    "maintainer": "CFIS",
    "license" :  "Other proprietary",
    "website": "https://www.cfis.store",
    "images": ["images/web_gantt_compact_view_adv.png"],
    "category": "Project",
    "depends": [
        "base",
        "web",
        "project",
        "sale_management",
        "hr",
        "hr_holidays",
        "crd_custom_project_fields",
    ],
    "data": [
        "security/ir.access.csv",
        "views/project_gantt_views.xml",      
        "views/sale_gantt_views.xml",      
        "views/hr_leave_allocation_gantt_view.xml",
        "views/hr_leave_gantt_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "/web_gantt_compact_view_adv/static/lib/dhtmlxGantt/sources/dhtmlxgantt.js",
            "/web_gantt_compact_view_adv/static/lib/dhtmlxGantt/sources/api.js",
            "/web_gantt_compact_view_adv/static/lib/dhtmlxGantt/sources/dhtmlxgantt.css",
            
            "/web_gantt_compact_view_adv/static/src/css/*.*",
            "/web_gantt_compact_view_adv/static/src/js/*.*",
        ],
    },
    "installable": True,
    "application": True,
    "price"                :  100,
    "currency"             :  "EUR",
    "uninstall_hook"       :  "uninstall_hook",
}
