# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_intervalTypes = {
    'days': lambda interval: relativedelta(days=interval),
    'hours': lambda interval: relativedelta(hours=interval),
    'weeks': lambda interval: relativedelta(days=7 * interval),
    'months': lambda interval: relativedelta(months=interval),
    'minutes': lambda interval: relativedelta(minutes=interval),
}


class fixablyCronConfigurationEpt(models.TransientModel):
    """
    Common model for manage cron configuration
    """
    _name = "fixably.cron.configuration.ept"
    _description = "Fixably Cron Configuration"

    def _get_fixably_instance(self):
        return self.env.context.get('fixably_instance_id', False)

    fixably_instance_id = fields.Many2one('fixably.instance.ept', 'Fixably Instance',
                                          help="Select fixably Instance that you want to configure.",
                                          default=_get_fixably_instance, readonly=True)

    # Auto cron for Export invoice
    fixably_invoice_auto_export = fields.Boolean('Export Invoice', default=False,
                                                 help="Check if you want to automatically Export Invoices from Odoo"
                                                      " to Fixably.")
    fixably_invoice_export_interval_number = fields.Integer('Interval Number for Export invoice',
                                                            help="Repeat every x.")
    fixably_invoice_export_interval_type = fields.Selection([('minutes', 'Minutes'), ('hours', 'Hours'),
                                                             ('days', 'Days'), ('weeks', 'Weeks'),
                                                             ('months', 'Months')], 'Interval Unit for Export Invoice')
    fixably_invoice_export_next_execution = fields.Datetime('Next Execution for Export Invoice ',
                                                            help='Next Execution for Export Invoice')
    fixably_invoice_export_user_id = fields.Many2one('res.users', string="User for Export invoice",
                                                     help='User for Export invoice',
                                                     default=lambda self: self.env.user)

    # Auto cron for Import Order
    fixably_order_auto_import = fields.Boolean('Import Order', default=False,
                                               help="Check if you want to automatically Import Orders from fixably to"
                                                    " Odoo.")
    fixably_import_order_interval_number = fields.Integer('Interval Number for Import Order', help="Repeat every x.")
    fixably_import_order_interval_type = fields.Selection([('minutes', 'Minutes'), ('hours', 'Hours'),
                                                           ('days', 'Days'), ('weeks', 'Weeks'),
                                                           ('months', 'Months')], 'Interval Unit for Import Order')
    fixably_import_order_next_execution = fields.Datetime('Next Execution for Import Order',
                                                          help='Next Execution for Import Order')
    fixably_import_order_user_id = fields.Many2one('res.users', string="User for Import Order",
                                                   help='User for Import Order',
                                                   default=lambda self: self.env.user)

    @api.constrains("fixably_invoice_export_interval_number","fixably_import_order_interval_number")
    def check_interval_time(self):
        """
        It does not let set the cron execution time to Zero.
        """
        for record in self:
            is_zero = False
            if record.fixably_invoice_auto_export and record.fixably_invoice_export_interval_number <= 0:
                is_zero = True
            if record.fixably_order_auto_import and record.fixably_import_order_interval_number <= 0:
                is_zero = True
            if is_zero:
                raise ValidationError(_("Cron Execution Time can't be set to 0(Zero). "))

    @api.onchange("fixably_instance_id")
    def onchange_fixably_instance_id(self):
        """
        Set cron field value while open the wizard for cron configuration from the instance form view.
        """
        instance = self.fixably_instance_id
        self.update_export_invoice_cron_field(instance)
        self.update_import_order_cron_field(instance)

    def update_export_invoice_cron_field(self, instance):
        """
        Set export stock cron fields value while open the wizard for cron configuration from the instance form view.
        """
        try:
            export_invoice_cron_exist = instance and self.env.ref(
                'fixably_ept.ir_cron_fixably_auto_export_invoice_instance_%d' % instance.id)
        except:
            export_invoice_cron_exist = False
        if export_invoice_cron_exist:
            self.fixably_invoice_auto_export = export_invoice_cron_exist.active or False
            self.fixably_invoice_export_interval_number = export_invoice_cron_exist.interval_number or False
            self.fixably_invoice_export_interval_type = export_invoice_cron_exist.interval_type or False
            self.fixably_invoice_export_next_execution = export_invoice_cron_exist.nextcall or False
            self.fixably_invoice_export_user_id = export_invoice_cron_exist.user_id.id or False

    def update_import_order_cron_field(self, instance):
        """
        Set import order cron fields value while open the wizard for cron configuration from the instance form view.
        """
        try:
            import_order_cron_exist = instance and self.env.ref(
                'fixably_ept.ir_cron_fixably_auto_import_order_instance_%d' % instance.id)
        except:
            import_order_cron_exist = False
        if import_order_cron_exist:
            self.fixably_order_auto_import = import_order_cron_exist.active or False
            self.fixably_import_order_interval_number = import_order_cron_exist.interval_number or False
            self.fixably_import_order_interval_type = import_order_cron_exist.interval_type or False
            self.fixably_import_order_next_execution = import_order_cron_exist.nextcall or False
            self.fixably_import_order_user_id = import_order_cron_exist.user_id.id or False

    def save(self):
        """
        This method is used to save cron job fields value.
        @return: action
        """
        instance = self.fixably_instance_id
        if instance:
            self.setup_fixably_export_invoice_cron(instance)
            self.setup_fixably_import_order_cron(instance)

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def setup_fixably_export_invoice_cron(self, instance):
        """
        This method is used to setup the invoice export cron.
        """
        try:
            cron_exist = self.env.ref(
                'fixably_ept.ir_cron_fixably_auto_export_invoice_instance_%d' % instance.id)
        except:
            cron_exist = False
        if self.fixably_invoice_auto_export:
            nextcall = datetime.now() + _intervalTypes[self.fixably_invoice_export_interval_type](
                self.fixably_invoice_export_interval_number)
            vals = self.prepare_val_for_cron(self.fixably_invoice_export_interval_number,
                                             self.fixably_invoice_export_interval_type,
                                             self.fixably_invoice_export_user_id)
            vals.update({'nextcall': self.fixably_invoice_export_next_execution or nextcall.strftime('%Y-%m-%d '
                                                                                                     '%H:%M:%S'),
                         'code': "model.auto_export_invoice_to_fixably(ctx={'fixably_instance_id':%d})" % instance.id,
                         })

            if cron_exist:
                vals.update({'name': cron_exist.name})
                cron_exist.write(vals)
            else:
                core_cron = self.check_core_fixably_cron("fixably_ept.ir_cron_fixably_auto_export_invoice")

                name = instance.name + ' : ' + core_cron.name
                vals.update({'name': name})
                new_cron = core_cron.copy(default=vals)
                name = 'ir_cron_fixably_auto_export_invoice_instance_%d' % (instance.id)
                self.create_ir_module_data(name, new_cron)
        else:
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_fixably_import_order_cron(self, instance):
        """
        Cron for auto Import Orders
        """
        try:
            cron_exist = self.env.ref(
                'fixably_ept.ir_cron_fixably_auto_import_order_instance_%d' % instance.id)
        except:
            cron_exist = False
        if self.fixably_order_auto_import:
            nextcall = datetime.now() + _intervalTypes[self.fixably_import_order_interval_type](
                self.fixably_import_order_interval_number)
            vals = self.prepare_val_for_cron(self.fixably_import_order_interval_number,
                                             self.fixably_import_order_interval_type,
                                             self.fixably_import_order_user_id)
            vals.update({'nextcall': self.fixably_import_order_next_execution or nextcall.strftime('%Y-%m-%d %H:%M:%S'),
                         'code': "model.import_order_cron_action(ctx={'fixably_instance_id':%d})" % instance.id,
                         })
            if cron_exist:
                vals.update({'name': cron_exist.name})
                cron_exist.write(vals)
            else:
                core_cron = self.check_core_fixably_cron("fixably_ept.process_fixably_order_queue")

                name = instance.name + ' : ' + core_cron.name
                vals.update({'name': name})
                new_cron = core_cron.copy(default=vals)
                name = 'ir_cron_fixably_auto_import_order_instance_%d' % (instance.id)
                self.create_ir_module_data(name, new_cron)
        else:
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def prepare_val_for_cron(self, interval_number, interval_type, user_id):
        """
        This method is used to prepare a vals for the cron configuration.
        @return: vals
        """
        vals = {'active': True,
                'interval_number': interval_number,
                'interval_type': interval_type,
                'user_id': user_id.id if user_id else False}
        return vals

    def create_ir_module_data(self, name, new_cron):
        """
        This method is used to create a record of ir model data
        """
        self.env['ir.model.data'].create({'module': 'fixably_ept',
                                          'name': name,
                                          'model': 'ir.cron',
                                          'res_id': new_cron.id,
                                          'noupdate': True})

    def check_core_fixably_cron(self, name):
        """
        This method will check for the core cron and if doesn't exist, then raise error.
        @return: core_cron
        """
        try:
            core_cron = self.env.ref(name)
        except:
            core_cron = False

        if not core_cron:
            raise UserError(
                _('Core settings of fixably are deleted, please upgrade fixably module to back this settings.'))
        return core_cron
