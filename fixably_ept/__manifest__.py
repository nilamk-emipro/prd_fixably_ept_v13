{
    # App information
    'name': 'Fixably Odoo Connector',
    'version': '13.0.4.0.1',
    'category': 'Sales',
    'summary': 'Fixably Odoo Connector helps you in integrating and managing your data with odoo',
    'license': 'OPL-1',

    # Author
    'author': 'Emipro Technologies Pvt. Ltd.',
    'website': 'http://www.emiprotechnologies.com/',
    'maintainer': 'Emipro Technologies Pvt. Ltd.',

    # Dependencies
    'depends': ['common_connector_library', 'point_of_sale'],

    # Views
    'init_xml': [],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'view/instance_view.xml',
        'wizard/cron_configuration_ept.xml',
        'wizard/instance_config_wizard_view.xml',
        'view/store_view.xml',
        'view/order_status_view.xml',
        'view/product_view.xml',
        'wizard/queue_process_wizard_view.xml',
        'wizard/fixably_res_config_view.xml',
        'wizard/process_import_export_view.xml',
        'view/common_log_book_view.xml',
        'view/product_queue_view.xml',
        'view/product_queue_line_view.xml',
        'view/order_queue_view.xml',
        'view/order_queue_line_view.xml',
        'view/sale_order_view.xml',
        'view/pos_order_view.xml',
        'view/account_move_view.xml',
    ],
    'demo_xml': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
