# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _

class PosOrder(models.Model):
    _inherit = "pos.order"

    fixably_order_id = fields.Char("Fixably Order Ref", copy=False)
    fixably_instance_id = fields.Many2one("fixably.instance.ept", "Fixably Instance", copy=False)
    fixably_customer_id = fields.Char("Fixably Customer Ref", copy=False)

class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    shopify_line_id = fields.Char("Shopify Line", copy=False)
