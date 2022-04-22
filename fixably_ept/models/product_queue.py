# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import json

_logger = logging.getLogger("Fixably Product Queue")


class FixablyProductQueue(models.Model):
    _name = "fixably.product.queue.ept"
    _description = "Fixably Product Queue"

    name = fields.Char(size=120)
    fixably_instance_id = fields.Many2one("fixably.instance.ept", string="Instance")
    state = fields.Selection([("draft", "Draft"), ("partially_completed", "Partially Completed"),
                              ("completed", "Completed"), ("failed", "Failed")], default="draft",
                             compute="_compute_queue_state", store=True, tracking=True)
    product_queue_line_ids = fields.One2many("fixably.product.queue.line.ept",
                                             "product_queue_id",
                                             string="Product Queue Lines")
    common_log_book_id = fields.Many2one("common.log.book.ept",
                                         help="""Related Log book which has all logs for current queue.""")
    common_log_lines_ids = fields.One2many(related="common_log_book_id.log_lines")
    queue_line_total_records = fields.Integer(string="Total Records",
                                              compute="_compute_queue_line_record")
    queue_line_draft_records = fields.Integer(string="Draft Records",
                                              compute="_compute_queue_line_record")
    queue_line_fail_records = fields.Integer(string="Fail Records",
                                             compute="_compute_queue_line_record")
    queue_line_done_records = fields.Integer(string="Done Records",
                                             compute="_compute_queue_line_record")
    queue_line_cancel_records = fields.Integer(string="Cancelled Records",
                                               compute="_compute_queue_line_record")
    is_process_queue = fields.Boolean("Is Processing Queue", default=False)
    running_status = fields.Char(default="Running...")
    is_action_require = fields.Boolean(default=False)
    queue_process_count = fields.Integer(string="Queue Process Times",
                                         help="it is used know queue how many time processed")
    skip_existing_product = fields.Boolean(string="Do Not Update Existing Products")

    @api.depends("product_queue_line_ids.state")
    def _compute_queue_line_record(self):
        """This is used for count of total record of product queue line base on it's state and
            it display in the form view of product queue.
        """
        for product_queue in self:
            queue_lines = product_queue.product_queue_line_ids
            product_queue.queue_line_total_records = len(queue_lines)
            product_queue.queue_line_draft_records = len(queue_lines.filtered(lambda x: x.state == "draft"))
            product_queue.queue_line_fail_records = len(queue_lines.filtered(lambda x: x.state == "failed"))
            product_queue.queue_line_done_records = len(queue_lines.filtered(lambda x: x.state == "done"))
            product_queue.queue_line_cancel_records = len(queue_lines.filtered(lambda x: x.state == "cancel"))

    @api.depends("product_queue_line_ids.state")
    def _compute_queue_state(self):
        """
        Computes queue state from different states of queue lines.
        """
        for record in self:
            if record.queue_line_total_records == record.queue_line_done_records + record.queue_line_cancel_records:
                record.state = "completed"
            elif record.queue_line_draft_records == record.queue_line_total_records:
                record.state = "draft"
            elif record.queue_line_total_records == record.queue_line_fail_records:
                record.state = "failed"
            else:
                record.state = "partially_completed"

    @api.model
    def create(self, vals):
        """This method used to create a sequence for product queue.
        @return: product_id
        """
        sequence_id = self.env.ref("fixably_ept.seq_product_queue_data").ids
        if sequence_id:
            record_name = self.env["ir.sequence"].browse(sequence_id).next_by_id()
        else:
            record_name = "/"
        vals.update({"name": record_name or ""})
        product_id = super(FixablyProductQueue, self).create(vals)
        return product_id

    def prepare_val_product_creation(self, instance, skip_existing_product, products):
        """
        this method use to prepare vals for product creation.
        @return: product_val
        """
        product_queue_line_obj = self.env['fixably.product.queue.line.ept']
        product_val = []
        product_line_val = []
        for val in products['items']:
            line_details = product_queue_line_obj.fixably_prepare_products_line(val, instance)
            product_line_val.append((0, 0, line_details))
        product_val.append({
            "fixably_instance_id": instance.id,
            "skip_existing_product": skip_existing_product,
            "product_queue_line_ids": product_line_val
        })
        return product_val

    def fixably_create_product_queue(self, instance, skip_existing_product=False):
        """
        This method use for create product queue.
        @return: product_queue_ids
        """
        offset = 0
        product_queue_ids = []
        products = instance.connect_with_fixably(ref="products")
        if products.status_code != 200:
            raise UserError(_("Some Error in Connection"))
        else:
            products = json.loads(products.content.decode())
            total_queue = products['totalItems'] / products['limit']
            _logger.info(total_queue)
            for index in range(int(total_queue) + 1):
                _logger.info(index)
                product = instance.connect_with_fixably(ref="products?offset=" + str(offset))
                if offset <= products['totalItems']:
                    product = json.loads(product.content.decode())
                    offset += len(product['items'])
                    product_val = self.prepare_val_product_creation(instance, skip_existing_product, product)
                    new_created_product = self.create(product_val)
                    product_queue_ids.append(new_created_product.id)
                    self._cr.commit()
                    message = "Product Queue Created", new_created_product.name
                    self.env['fixably.product.queue.line.ept'].generate_simple_notification(message)
        return product_queue_ids
