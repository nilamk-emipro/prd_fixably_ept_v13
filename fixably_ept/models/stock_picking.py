# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class StockPicking(models.Model):
    """Inhetit the model to add the fields in this model related to connector"""
    _inherit = "stock.picking"

    fixably_instance_id = fields.Many2one("fixably.instance.ept", "Fixably Instance")
