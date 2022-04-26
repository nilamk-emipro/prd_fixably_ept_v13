# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import logging

from datetime import datetime, timedelta
from odoo import models, fields

_logger = logging.getLogger(__name__)


class CommonLogBookEpt(models.Model):
    """Inherit the common log book here to handel the log book in the connector"""
    _inherit = "common.log.book.ept"

    fixably_instance_id = fields.Many2one("fixably.instance.ept", "Fixably Instance")

    def create_crash_queue_schedule_activity(self, queue_id, model_id, note):
        """
        This method is used to create a schedule activity for the queue crash.
        Base on the fixably configuration when any queue crash will create a schedule activity.
        """
        mail_activity_obj = self.env['mail.activity']
        activity_type_id = queue_id and queue_id.fixably_instance_id.fixably_activity_type_id.id
        date_deadline = datetime.strftime(
            datetime.now() + timedelta(days=int(queue_id.fixably_instance_id.fixably_date_deadline)), "%Y-%m-%d")

        if queue_id:
            for user_id in queue_id.fixably_instance_id.fixably_user_ids:
                mail_activity = mail_activity_obj.search(
                    [('res_model_id', '=', model_id), ('user_id', '=', user_id.id), ('res_id', '=', queue_id.id),
                     ('activity_type_id', '=', activity_type_id)])
                if not mail_activity:
                    vals = self.prepare_vals_for_schedule_activity(activity_type_id, note, queue_id, user_id, model_id,
                                                                   date_deadline)
                    try:
                        mail_activity_obj.create(vals)
                    except Exception as error:
                        _logger.info("Unable to create schedule activity, Please give proper "
                                     "access right of this user :%s  ", user_id.name)
                        _logger.info(error)
        return True

    def prepare_vals_for_schedule_activity(self, activity_type_id, note, queue_id, user_id, model_id, date_deadline):
        """
        This method used to prepare a vals for the schedule activity.
        @return : values
        """
        values = {'activity_type_id': activity_type_id,
                  'note': note,
                  'res_id': queue_id.id,
                  'user_id': user_id.id or self._uid,
                  'res_model_id': model_id,
                  'date_deadline': date_deadline
                  }
        return values

    def fixably_create_common_log_book(self, process_type, instance, model_id):
        """
        this method use for the create log book record.
        @param : process_type
                 instance
                 model_id
        @return: log_book_id
        """
        log_book_id = self.create({"type": process_type,
                                   "module": "fixably_ept",
                                   "fixably_instance_id": instance.id if instance else False,
                                   "model_id": model_id,
                                   "active": True})
        return log_book_id
