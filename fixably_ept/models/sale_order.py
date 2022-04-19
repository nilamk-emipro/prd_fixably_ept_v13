# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    fixably_order_id = fields.Char("Fixably Order Ref", copy=False)
    fixably_instance_id = fields.Many2one("fixably.instance.ept", "Fixably Instance", copy=False)
    fixably_customer_id = fields.Char("Fixably Customer Ref", copy=False)

    def _prepare_invoice(self):
        """This method used set a fixably instance in invoice.
        """
        inv_val = super(SaleOrder, self)._prepare_invoice()
        if self.fixably_instance_id:
            inv_val.update({'fixably_instance_id': self.fixably_instance_id.id})
        return inv_val

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    fixably_line_id = fields.Char("Fixably Line", copy=False)