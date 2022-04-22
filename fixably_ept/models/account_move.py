# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _


class AccountMove(models.Model):
    """
    Inherite the account move here to return refund action.
    """
    _inherit = "account.move"

    fixably_instance_id = fields.Many2one("fixably.instance.ept", "Instances")
    invoice_exported_to_fixably = fields.Boolean(string='Invoice Exported',
                                                 help='Is it true when invoice exported odoo to fixably')

    def prepare_val_for_invoice(self):
        """
        this method use for prepare dict of export invoice
        @return : vals and url for post request
        """
        invoice_line = self.invoice_line_ids
        sale_lines = invoice_line.sale_line_ids
        fixably_customer_id = sale_lines.order_id.fixably_customer_id
        fixably_line_ids = []
        for sale_line in sale_lines:
            fixably_line_ids.append({'id': sale_line.fixably_line_id})

        customer_add = sale_lines.order_id.partner_shipping_id.street if sale_lines.order_id.partner_shipping_id.street else ""
        city = sale_lines.order_id.partner_shipping_id.city if sale_lines.order_id.partner_shipping_id.city else ""
        state = sale_lines.order_id.partner_shipping_id.state_id[
            'name'] if sale_lines.order_id.partner_shipping_id.state_id else ""
        zip = sale_lines.order_id.partner_shipping_id.zip if sale_lines.order_id.partner_shipping_id.zip else ""
        country = sale_lines.order_id.partner_shipping_id.country_id[
            'name'] if sale_lines.order_id.partner_shipping_id.country_id else ""

        vals = {
            "user": {
                "id": fixably_customer_id
            },
            "reference": self.name,
            "contactName": sale_lines.order_id.partner_id['name'],
            "lines": fixably_line_ids,
            "address": {
                "name": sale_lines.order_id.partner_shipping_id['name'],
                "address1": customer_add,
                "city": city,
                "zip": zip,
                "state": state,
                "country": country
            }
        }
        url = self.fixably_instance_id.fixably_url + '/orders/' + sale_lines.order_id.fixably_order_id + '/invoice'
        return vals, url

    def export_invoice_to_fixably(self):
        """
        this method call from button click of export invoice as well use from cron to export invoice
        and set the invoice exported true
        @return : vals and url for post request
        """
        vals, url = self.prepare_val_for_invoice()
        self.invoice_exported_to_fixably = True
        return vals, url

    def search_ready_for_export_invoice(self, instance_id):
        """
        this method use to search invoices for export
        @param : instance_id
        @return: invoice_ids
        """
        return self.search([('invoice_payment_state', '=', 'paid'),
                            ('fixably_instance_id', '=', instance_id),
                            ('invoice_exported_to_fixably', '=', False)
                            ])
