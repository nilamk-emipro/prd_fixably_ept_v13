# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import requests
import logging

from calendar import monthrange
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger("Fixably Instance")
_secondsConverter = {
    'days': lambda interval: interval * 24 * 60 * 60,
    'hours': lambda interval: interval * 60 * 60,
    'weeks': lambda interval: interval * 7 * 24 * 60 * 60,
    'minutes': lambda interval: interval * 60,
}


class FixablyInstanceEpt(models.Model):
    _name = "fixably.instance.ept"
    _description = 'Fixably Instance'

    @api.model
    def _get_default_warehouse(self):
        """
        This method is used to set the default warehouse in an instance.
        """
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.fixably_company_id.id)], limit=1)
        return warehouse.id if warehouse else False

    name = fields.Char(size=120, required=True)
    fixably_warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', default=_get_default_warehouse,
                                           domain="[('company_id', '=',fixably_company_id)]",
                                           help="Selected Warehouse will be set in your orders", required=True)
    fixably_company_id = fields.Many2one('res.company', string='Company', required=True,
                                         default=lambda self: self.env.company)
    fixably_auto_create_product_if_not_found = fields.Boolean(string="Auto Create Product",
                                                              help='if checked than it auto create the product when'
                                                                   ' product is not found')
    fixably_is_use_default_sequence = fields.Boolean("Use Odoo Default Sequence?",
                                                     help="If checked,Then use default sequence of odoo while create pos "
                                                          "order.")
    fixably_order_prefix = fields.Char(size=10, string='Order Prefix',
                                       help="Enter your order prefix")
    apply_tax = fields.Selection(
        [("odoo_tax", "Odoo Default Tax Behaviour"), ("create_fixably_tax",
                                                      "Create new tax If Not Found")],
        copy=False, help=""" For Fixably Orders :- \n
                       1) Odoo Default Tax Behaviour - The Taxes will be set based on Odoo's
                                    default functional behaviour i.e. based on Odoo's Tax and Fiscal Position configurations. \n
                       2) Create New Tax If Not Found - System will search the tax data received 
                       from Fixably in Odoo, will create a new one if it fails in finding it.""")
    credit_tax_account_id = fields.Many2one('account.account', string='Credit Tax Account')
    debit_tax_account_id = fields.Many2one('account.account', string='Debit Tax Account')
    last_order_import_date = fields.Datetime(string="Last Date Of Order Import",
                                             help="Last date of sync orders from Fixably to Odoo")
    fixably_pricelist_id = fields.Many2one('product.pricelist', string='Pricelist',
                                           help="During order sync, prices will be Imported/Exported using this Pricelist.")
    fixably_api_key = fields.Char("API Key", required=True)
    fixably_url = fields.Char("URL", required=True)
    active = fields.Boolean(default=True)
    fixably_order_status_ids = fields.Many2many(comodel_name='fixably.order.status.ept', string="Order Status",
                                                help="Select order status in which "
                                                     "you want to import the orders from Fixably.")
    fixably_store_ids = fields.One2many(comodel_name='fixably.store.ept', inverse_name="fixably_instance_id",
                                        string="Store")
    fixably_status_ids = fields.One2many(comodel_name='fixably.order.status.ept', inverse_name="fixably_instance_id",
                                         string="Status")

    _sql_constraints = [('unique_url', 'unique(fixably_url)',
                         "Instance already exists for given url. URL must be Unique for the instance!"),
                        ('unique_api_key', 'unique(fixably_api_key)',
                         "Instance already exists for given Api Key. Api Key must be Unique for the instance!")]

    def prepare_fixably_api_url(self, url, ref, withURL):
        """ This method is used to prepare a store URL.
            return : api_url
        """
        if withURL:
            api_url = ref
        else:
            api_url = url + "/api/v3/" + ref
        return api_url

    def connect_with_fixably(self, ref=False, withURL=False):
        """
               This method used to connect with Odoo to Fixably.
        """
        api_url = self.prepare_fixably_api_url(self.fixably_url, ref, withURL)
        headers = {'Authorization': self.fixably_api_key,
                   'Content-Type': 'application/json'}
        response = requests.get(url=api_url, headers=headers)
        return response

    def get_fixably_cron_execution_time(self, cron_name):
        """
        This method is used to get the interval time of the cron.
        """
        process_queue_cron = self.env.ref(cron_name, False)
        if not process_queue_cron:
            raise UserError(_("Please upgrade the module. \n Maybe the job has been deleted, it will be recreated at "
                              "the time of module upgrade."))
        interval = process_queue_cron.interval_number
        interval_type = process_queue_cron.interval_type
        if interval_type == "months":
            days = 0
            current_year = fields.Date.today().year
            current_month = fields.Date.today().month
            for i in range(0, interval):
                month = current_month + i

                if month > 12:
                    if month == 13:
                        current_year += 1
                    month -= 12

                days_in_month = monthrange(current_year, month)[1]
                days += days_in_month

            interval_type = "days"
            interval = days
        interval_in_seconds = _secondsConverter[interval_type](interval)
        return interval_in_seconds

    def open_reset_credentials_wizard(self):
        """
        Open wizard for reset credentials.
        """
        view_id = self.env.ref('fixably_ept.view_reset_credentials_form').id
        action = self.env.ref('fixably_ept.res_config_action_fixably_instance').read()[0]
        action.update({"name": "Reset Credentials",
                       "context": {'fixably_instance_id': self.id,
                                   "default_name": self.name,
                                   "default_fixably_url": self.fixably_url},
                       "view_id": (view_id, "Reset Credentials"),
                       "views": [(view_id, "form")]})
        return action

    def cron_configuration_action(self):
        """
        Open wizard of "Configure Schedulers" on button click in the instance form view.
        """
        action = self.env.ref('fixably_ept.action_wizard_fixably_cron_configuration_ept').read()[0]
        action['context'] = {'fixably_instance_id': self.id}
        return action

    def write(self, vals):
        self.fixably_status_ids.unlink()
        self.fixably_store_ids.unlink()
        res = super(FixablyInstanceEpt, self).write(vals)
        self._cr.commit()
        vals = {
            "fixably_api_key": self.fixably_api_key,
            "fixably_url": self.fixably_url
        }
        self.env['res.config.fixably.instance'].fixably_test_connection(vals)
        return res
