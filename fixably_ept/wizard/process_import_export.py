# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import logging
import requests
import json
from odoo import models, fields, api, _

_logger = logging.getLogger("Fixably Operations")


class FixablyProcessImportExport(models.TransientModel):
    _name = 'fixably.process.import.export'
    _description = 'Fixably Process Import Export'

    fixably_instance_id = fields.Many2one("fixably.instance.ept", string="Instance")
    fixably_operation = fields.Selection(
        [("sync_product", "Import Products"),
         ("sync_orders", "Import Orders")], default="sync_product", string="Operation")
    orders_from_date = fields.Datetime(string="From Date")
    orders_to_date = fields.Datetime(string="To Date")
    skip_existing_product = fields.Boolean(string="Do Not Update Existing Products",
                                           help="Check if you want to skip existing products.")

    def fixably_execute(self):
        """This method used to execute the operation as per given in wizard.
        @return: action
        """
        product_queue_obj = self.env["fixably.product.queue.ept"]
        order_queue_obj = self.env["fixably.order.queue.ept"]
        queue_ids = False
        order_queues = False

        instance = self.fixably_instance_id
        if self.fixably_operation == "sync_product":
            product_queue_ids = product_queue_obj.fixably_create_product_queue(instance, self.skip_existing_product)
            if product_queue_ids:
                queue_ids = product_queue_ids
                action_name = "fixably_ept.action_fixably_product_queue"
                form_view_name = "fixably_ept.fixably_product_synced_data_form_view_ept"

        elif self.fixably_operation == "sync_orders":
            order_queues = order_queue_obj.fixably_create_order_queue(instance,
                                                                      self.orders_from_date,
                                                                      self.orders_to_date)
        if order_queues:
            queue_ids = order_queues
            action_name = "fixably_ept.action_fixably_order_queue"
            form_view_name = "fixably_ept.fixably_order_synced_data_form_view_ept"

        if queue_ids and action_name and form_view_name:
            action = self.env.ref(action_name).sudo().read()[0]
            form_view = self.sudo().env.ref(form_view_name)

            if len(queue_ids) == 1:
                action.update({"view_id": (form_view.id, form_view.name), "res_id": queue_ids[0],
                               "views": [(form_view.id, "form")]})
            else:
                action["domain"] = [("id", "in", queue_ids)]
            return action

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def auto_export_invoice_to_fixably(self, ctx=False):
        """
        this method use to export invoice odoo to fixably using the request post
        """
        invoice_obj = self.env['account.move']
        instance_id = self.env['fixably.instance.ept'].browse(ctx.get('fixably_instance_id'))
        headers = {'Authorization': instance_id.fixably_api_key,
                   'Content-Type': 'application/json'}

        invoice_ids = invoice_obj.search_ready_for_export_invoice(instance_id.id)

        for invoice_id in invoice_ids:
            vals, url = invoice_id.export_invoice_to_fixably()
            _logger.info("call api for export invoice with %s", url)
            response = requests.post(url, data=json.dumps(vals), headers=headers)
            _logger.info("Api Response : %s", response)
