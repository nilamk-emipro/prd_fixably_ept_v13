# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class FixablyOrderStatusEpt(models.Model):
    _name = "fixably.order.status.ept"
    _description = 'Fixably Order Status'

    name = fields.Char(string="Name", help='Order Status Name')
    status_id = fields.Char(string='Id')
    type = fields.Char(string='Type', help="Order Status Type")
    fixably_instance_id = fields.Many2one('fixably.instance.ept', string='Instance')
