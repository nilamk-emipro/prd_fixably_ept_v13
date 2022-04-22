# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import json
import logging
import time
from odoo import models, fields, _

_logger = logging.getLogger("Fixably Order Queue Line")


class FixablyorderQueueLineEpt(models.Model):
    _name = "fixably.order.queue.line.ept"
    _description = "Fixably Order Queue Line"

    name = fields.Char(string="order", help="It contain the name of order")
    fixably_instance_id = fields.Many2one("fixably.instance.ept", string="Instance")
    last_process_date = fields.Datetime()
    synced_order_data = fields.Text()
    fixably_order_id = fields.Char()
    state = fields.Selection([("draft", "Draft"), ("failed", "Failed"), ("done", "Done"),
                              ("cancel", "Cancelled")],
                             default="draft")
    order_queue_id = fields.Many2one("fixably.order.queue.ept", required=True,
                                     ondelete="cascade", copy=False)
    common_log_lines_ids = fields.One2many("common.log.lines.ept",
                                           "fixably_order_queue_line_id",
                                           help="Log lines created against which line.")
    customer_name = fields.Char(string="Customer Name", help="It contain the name of Customer")
    customer_email = fields.Char(string="Email", help="It contain the Email of Customer")

    def prepare_val_for_order_queue_line(self, order_url, fixably_instance):
        """
        This method is used to prepare order queue lines.
        """
        order_url = order_url + '?expand=lines(items(product)),customer,store'
        _logger.info(order_url)
        details = fixably_instance.connect_with_fixably(order_url, withURL=True)
        details = json.loads(details.content.decode())
        data = json.dumps(details)
        order_line = {
            "fixably_instance_id": fixably_instance.id,
            "synced_order_data": data,
            "fixably_order_id": details['id']
        }
        return order_line

    def auto_import_order_queue(self):
        """
        This method is used to find order queue which queue lines have state in draft and is_action_require is False.
        If cronjob has tried more than 3 times to process any queue then it marks that queue has need process to
        manually. It will be called from auto queue process cron.
        """
        order_queue_ids = []
        order_queue_obj = self.env["fixably.order.queue.ept"]

        query = """select queue.id
                   from fixably_order_queue_line_ept as queue_line
                   inner join fixably_order_queue_ept as queue on queue_line.order_queue_id = queue.id
                   where queue_line.state = 'draft' and queue.is_action_require = 'False'
                   ORDER BY queue_line.create_date ASC"""
        self._cr.execute(query)
        order_queue_list = self._cr.fetchall()
        if order_queue_list:
            for result in order_queue_list:
                if result[0] not in order_queue_ids:
                    order_queue_ids.append(result[0])

            queues = order_queue_obj.browse(order_queue_ids)
            self.process_order_queue_and_post_message(queues)
        return

    def process_order_queue_and_post_message(self, queues):
        """
        This method is used to post a message if the queue is process more than 3 times otherwise
        it calls the child method to process the order queue line.
        :param queues: Records of order queue.
        """
        ir_model_obj = self.env["ir.model"]
        common_log_book_obj = self.env["common.log.book.ept"]
        start = time.time()
        order_queue_process_cron_time = queues.fixably_instance_id.get_fixably_cron_execution_time(
            "fixably_ept.process_fixably_order_queue")

        for queue in queues:
            order_queue_line_ids = queue.order_queue_line_ids
            # queue.queue_process_count += 1
            # if queue.queue_process_count > 3:
            #     queue.is_action_require = True
            #     note = "<p>Need to process this order queue manually.There are 3 attempts been made by " \
            #            "automated action to process this queue,<br/>- Ignore, if this queue is already processed.</p>"
            #     queue.message_post(body=note)
            #     if queue.fixably_instance_id.is_fixably_create_schedule:
            #         model_id = ir_model_obj.search([("model", "=", "fixably.order.queue.ept")]).id
            #         common_log_book_obj.create_crash_queue_schedule_activity(queue, model_id, note)
            #     return True

            self._cr.commit()
            order_queue_line_ids.process_order_queue_line()
            if time.time() - start > order_queue_process_cron_time - 60:
                return True
        return True

    def process_order_queue_line(self):
        """
        This method is used to processes order queue lines.
        """
        fixably_order_obj = self.env["fixably.order.queue.ept"]
        common_log_book_obj = self.env["common.log.book.ept"]
        model_id = common_log_book_obj.log_lines.get_model_id("sale.order")

        queue_id = self.order_queue_id if len(self.order_queue_id) == 1 else False

        if queue_id:
            fixably_instance = queue_id.fixably_instance_id
            if fixably_instance.active:
                if queue_id.common_log_book_id:
                    log_book_id = queue_id.common_log_book_id
                else:
                    log_book_id = common_log_book_obj.fixably_create_common_log_book("import", fixably_instance,
                                                                                     model_id)

                self.env.cr.execute(
                    """update fixably_order_queue_ept set is_process_queue = False where is_process_queue = True""")
                self._cr.commit()
                for order_queue_line in self:
                    fixably_order_obj.fixably_sync_orders(order_queue_line, fixably_instance, log_book_id)
                    queue_id.is_process_queue = True
                    self._cr.commit()
                queue_id.common_log_book_id = log_book_id
                if queue_id.common_log_book_id and not queue_id.common_log_book_id.log_lines:
                    queue_id.common_log_book_id.unlink()
        return True

    def generate_simple_notification(self, message):
        """
        This method is used to display simple notification while the opration wizard
        """
        bus_bus_obj = self.env["bus.bus"]
        # bus_bus_obj.sendone(self.env.user.partner_id, 'simple_notification',
        #                     {"title": "Fixably Connector",
        #                      "message": message, "sticky": False, "warning": True})

        bus_bus_obj.sendone(
            (self._cr.dbname, 'res.partner', self.env.user.partner_id.id),
            {'type': 'simple_notification', 'title': _('Fixably Connector'),
             'message': message, 'sticky': False,
             'warning': True})
