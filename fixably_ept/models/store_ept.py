# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class FixablyStoreEpt(models.Model):
    _name = "fixably.store.ept"
    _description = 'Fixably Store'

    name = fields.Char(string="Store Name")
    fixably_instance_id = fields.Many2one('fixably.instance.ept', string='Instance')
    fixably_store_id = fields.Char(string='Store', help="Enter store id")
    fixably_team_id = fields.Many2one('crm.team', string='Team')
    fixably_pos_store_id = fields.Many2one('pos.config', string='POS Store')
