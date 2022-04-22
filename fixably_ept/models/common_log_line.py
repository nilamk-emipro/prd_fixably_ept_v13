# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from datetime import datetime
from odoo import models, fields


class CommonLogLineEpt(models.Model):
    _inherit = "common.log.lines.ept"

    fixably_product_queue_line_id = fields.Many2one("fixably.product.queue.line.ept",
                                                    "fixably Product Queue Line")
    fixably_order_queue_line_id = fields.Many2one("fixably.order.queue.line.ept",
                                                  "fixably Order Queue Line")
    fixably_customer_queue_line_id = fields.Many2one("fixably.customer.queue.line.ept",
                                                     "fixably Customer Queue Line")
    fixably_payout_report_line_id = fields.Many2one("fixably.payout.report.line.ept")


    def fixably_create_product_log_line(self, message, model_id, queue_line_id, log_book_id, sku=""):
        """
        This method used to create a log line for product mismatch logs.
        @return: log_line
        """
        vals = self.fixably_prepare_log_line_vals(message, model_id, queue_line_id, log_book_id)

        vals.update({
            'fixably_product_queue_line_id': queue_line_id.id if queue_line_id else False,
            "default_code": sku
        })
        log_line = self.create(vals)
        return log_line

    def fixably_prepare_log_line_vals(self, message, model_id, res_id, log_book_id):
        """
        this method use to prepare vals for the log line.
        @return: vals
        """
        vals = {'message': message,
                'model_id': model_id,
                'res_id': res_id.id if res_id else False,
                'log_line_id': log_book_id.id if log_book_id else False,
                }
        return vals

    def fixably_create_order_log_line(self, message, model_id, queue_line_id, log_book_id, order_ref=""):
        """
        This method used to create a log line for order mismatch logs.
        @return: log_line
        """
        if order_ref:
            domain = [("message", "=", message), ("model_id", "=", model_id), ("order_ref", "=", order_ref)]
            log_line = self.search(domain)
            if log_line:
                log_line.update({"write_date": datetime.now(), "log_line_id": log_book_id.id if log_book_id else False,
                                 "fixably_order_queue_line_id": queue_line_id and queue_line_id.id or False})
                return log_line

        vals = self.fixably_prepare_log_line_vals(message, model_id, queue_line_id, log_book_id)

        vals.update({'fixably_order_queue_line_id': queue_line_id and queue_line_id.id or False,
                     "order_ref": order_ref})
        log_line = self.create(vals)
        return log_line
