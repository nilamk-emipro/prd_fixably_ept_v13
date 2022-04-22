# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, _


class FixablyQueueProcessEpt(models.TransientModel):
    _name = 'fixably.queue.process.ept'
    _description = 'fixably Queue Process'

    def manual_queue_process(self):
        """
        This method is used to call child methods while manually queue(product, order and customer) process.
       """
        queue_process = self._context.get('queue_process')
        if queue_process == "process_product_queue_manually":
            self.sudo().process_product_queue_manually()
        if queue_process == "process_order_queue_manually":
            self.sudo().process_order_queue_manually()

    def process_product_queue_manually(self):
        """This method used to process the product queue manually.
        """
        model = self._context.get('active_model')
        fixably_product_queue_line_obj = self.env["fixably.product.queue.line.ept"]
        product_queue_ids = self._context.get('active_ids')
        if model == 'fixably.product.queue.line.ept':
            product_queue_ids = fixably_product_queue_line_obj.search(
                [('id', 'in', product_queue_ids)]).mapped("product_queue_id").ids
        for product_queue_id in product_queue_ids:
            product_queue_line_batch = fixably_product_queue_line_obj.search(
                [("product_queue_id", "=", product_queue_id),
                 ("state", "in", ('draft', 'failed'))])
            product_queue_line_batch.process_product_queue_line()
        return True

    def process_order_queue_manually(self):
        """This method used to process the order queue manually.
        """
        model = self._context.get('active_model')
        fixably_order_queue_line_obj = self.env["fixably.order.queue.line.ept"]
        order_queue_ids = self._context.get('active_ids')
        if model == "fixably.order.data.queue.line.ept":
            order_queue_ids = fixably_order_queue_line_obj.search([('id', 'in', order_queue_ids)]).mapped(
                "fixably_order_queue_id").ids
        self.env.cr.execute(
            """update fixably_order_queue_ept set is_process_queue = False where is_process_queue = True""")
        self._cr.commit()
        for order_queue_id in order_queue_ids:
            order_queue_line_batch = fixably_order_queue_line_obj.search(
                [("order_queue_id", "=", order_queue_id),
                 ("state", "in", ('draft', 'failed'))])
            order_queue_line_batch.process_order_queue_line()
        return True

    def set_to_completed_queue(self):
        """
        This method used to change the queue(order, product) state as completed.
        """
        queue_process = self._context.get('queue_process')
        if queue_process == "set_to_completed_order_queue":
            self.set_to_completed_order_queue_manually()
        if queue_process == "set_to_completed_customer_queue":
            self.set_to_completed_customer_queue_manually()

    def set_to_completed_order_queue_manually(self):
        """This method used to set order queue as completed.
        """
        order_queue_ids = self._context.get('active_ids')
        order_queue_ids = self.env['fixably.order.queue.ept'].browse(order_queue_ids)
        for order_queue_id in order_queue_ids:
            queue_lines = order_queue_id.order_queue_line_ids.filtered(
                lambda line: line.state in ['draft', 'failed'])
            queue_lines.write({'state': 'cancel'})
            # order_queue_id.message_post(
            #     body=_("Manually set to cancel queue lines %s - ") % (queue_lines.mapped('fixably_order_id')))
        return True

    def set_to_completed_product_queue_manually(self):
        """This method used to set product queue as completed.
        """
        product_queue_ids = self._context.get('active_ids')
        product_queue_ids = self.env['fixably.product.queue.ept'].browse(product_queue_ids)
        for product_queue_id in product_queue_ids:
            queue_lines = product_queue_id.product_queue_lines.filtered(
                lambda line: line.state in ['draft', 'failed'])
            queue_lines.write({'state': 'cancel'})
            # product_queue_id.message_post(
            #     body=_("Manually set to cancel queue lines %s - ") % (queue_lines.mapped('product_id')))
        return True

