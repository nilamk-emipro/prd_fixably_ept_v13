# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _


class AccountMove(models.Model):
    """
    Inherite the account move here to return refund action.
    """
    _inherit = "account.move"

    fixably_instance_id = fields.Many2one("fixably.instance.ept", "Instances")
