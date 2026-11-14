{
    'name': 'Custom Project Fields',
    'version': '20.0.1.0.0',
    'summary': 'Add custom fields to the project module',
    'category': 'Project',
    'author': 'Your Name',
    'website': 'https://yourwebsite.com',
    'depends': ['base','project','hr_timesheet'],
    'data': [
        #security
        'security/ir.access.csv',

        # View
        'views/project_views.xml',
        'views/project_task.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'crd_custom_project_fields/static/src/components/project_task_state_selection/project_task_state_selection.js',
            'crd_custom_project_fields/static/src/scss/form_style.scss',
            'crd_custom_project_fields/static/src/components/progress_bar/project_task_progress_bar_field.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
