# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import json
import logging
import time
from odoo import models, fields,_

_logger = logging.getLogger("Fixably Product Queue Line")


class FixablyProductQueueLineEpt(models.Model):
    _name = "fixably.product.queue.line.ept"
    _description = "Fixably Product Queue Line"

    name = fields.Char(string="Product", help="It contain the name of product")
    fixably_instance_id = fields.Many2one("fixably.instance.ept", string="Instance")
    last_process_date = fields.Datetime()
    synced_product_data = fields.Text()
    product_id = fields.Char()
    state = fields.Selection([("draft", "Draft"), ("failed", "Failed"), ("done", "Done"),
                              ("cancel", "Cancelled")],
                             default="draft")
    product_queue_id = fields.Many2one("fixably.product.queue.ept", required=True,
                                       ondelete="cascade", copy=False)
    common_log_lines_ids = fields.One2many("common.log.lines.ept",
                                           "fixably_product_queue_line_id",
                                           help="Log lines created against which line.")

    def fixably_prepare_products_line(self, product_url, fixably_instance):
        """
        This method use for prepare product queue line
        @return: product_line
        """
        product_url = product_url['href']  # + '?expand=lines(items(product)),customer,store'
        _logger.info(product_url)
        details = fixably_instance.connect_with_fixably(product_url, withURL=True)

        details = json.loads(details.content.decode())
        data = json.dumps(details)
        product_line = {
            "fixably_instance_id": fixably_instance.id,
            "synced_product_data": data,
            "name": details['name'],
            "product_id": details['id']
        }
        return product_line

    def auto_import_product_queue_line(self):
        """
        This method is used to find product queue which queue lines have state in draft and is_action_require is False.
        It will be called from auto queue process cron.
        """
        product_queue_ids = []
        product_queue_obj = self.env["fixably.product.queue.ept"]

        query = """select queue.id
                   from fixably_product_queue_line_ept as queue_line
                   inner join fixably_product_queue_ept as queue on queue_line.product_queue_id = queue.id
                   where queue_line.state = 'draft' and queue.is_action_require = 'False'
                   ORDER BY queue_line.create_date ASC"""
        self._cr.execute(query)
        product_queue_list = self._cr.fetchall()
        if product_queue_list:
            for result in product_queue_list:
                if result[0] not in product_queue_ids:
                    product_queue_ids.append(result[0])

            queues = product_queue_obj.browse(product_queue_ids)
            self.process_product_queue_and_post_message(queues)
        return

    def process_product_queue_and_post_message(self, queues):
        """
        This method is used to post a message if the queue is process more than 3 times otherwise
        it calls the child method to process the product queue line.
        """
        ir_model_obj = self.env["ir.model"]
        common_log_book_obj = self.env["common.log.book.ept"]
        start = time.time()
        product_queue_process_cron_time = queues.fixably_instance_id.get_fixably_cron_execution_time(
            "fixably_ept.process_fixably_product_queue")

        for queue in queues:
            product_queue_line_ids = queue.product_queue_line_ids
            # queue.queue_process_count += 1
            # if queue.queue_process_count > 3:
            #     queue.is_action_require = True
            #     note = "<p>Need to process this product queue manually.There are 3 attempts been made by " \
            #            "automated action to process this queue,<br/>- Ignore, if this queue is already processed.</p>"
            #     queue.message_post(body=note)
            #     if queue.fixably_instance_id.is_fixably_create_schedule:
            #         model_id = ir_model_obj.search([("model", "=", "fixably.product.queue.ept")]).id
            #         common_log_book_obj.create_crash_queue_schedule_activity(queue, model_id, note)
            #     return True

            self._cr.commit()
            product_queue_line_ids.process_product_queue_line()
            if time.time() - start > product_queue_process_cron_time - 60:
                return True
        return True

    def process_product_queue_line(self):
        """
        This method is used to processes product queue lines.
        """
        fixably_product_obj = self.env["fixably.product.ept"]
        common_log_book_obj = self.env["common.log.book.ept"]
        model_id = common_log_book_obj.log_lines.get_model_id("fixably.product.ept")

        queue_id = self.product_queue_id if len(self.product_queue_id) == 1 else False

        if queue_id:
            fixably_instance = queue_id.fixably_instance_id
            if fixably_instance.active:
                if queue_id.common_log_book_id:
                    log_book_id = queue_id.common_log_book_id
                else:
                    log_book_id = common_log_book_obj.fixably_create_common_log_book("import", fixably_instance,
                                                                                     model_id)

                self.env.cr.execute(
                    """update fixably_product_queue_ept set is_process_queue = False where is_process_queue = True""")
                self._cr.commit()
                for product_queue_line in self:
                    fixably_product_obj.fixably_sync_products(product_queue_line, fixably_instance, log_book_id)
                    queue_id.is_process_queue = True
                    self._cr.commit()
                queue_id.common_log_book_id = log_book_id
                if queue_id.common_log_book_id and not queue_id.common_log_book_id.log_lines:
                    queue_id.common_log_book_id.unlink()
        return True

    def generate_simple_notification(self, message):
        """ This method is used to display simple notification while the opration wizard
            opration running in the backend.
        """
        bus_bus_obj = self.env["bus.bus"]
        bus_bus_obj.sendone(
            (self._cr.dbname, 'res.partner', self.env.user.partner_id.id),
            {'type': 'simple_notification', 'title': _('Fixably Connector'),
             'message': message, 'sticky': False,
             'warning': True})
