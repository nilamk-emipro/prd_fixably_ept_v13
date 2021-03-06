# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import json
import logging
import pytz

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, time, timedelta
from dateutil import parser

utc = pytz.utc

_logger = logging.getLogger("Fixably Order Queue")


class FixablyOrderQueue(models.Model):
    _name = "fixably.order.queue.ept"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Fixably Order Queue"

    name = fields.Char(size=120)
    fixably_instance_id = fields.Many2one("fixably.instance.ept", string="Instance")
    state = fields.Selection([("draft", "Draft"), ("partially_completed", "Partially Completed"),
                              ("completed", "Completed"), ("failed", "Failed")], default="draft",
                             compute="_compute_queue_state", store=True, tracking=True)
    order_queue_line_ids = fields.One2many("fixably.order.queue.line.ept",
                                           "order_queue_id",
                                           string="Order Queue Lines")
    common_log_book_id = fields.Many2one("common.log.book.ept",
                                         help="""Related Log book which has all logs for current queue.""")
    common_log_lines_ids = fields.One2many(related="common_log_book_id.log_lines")

    is_process_queue = fields.Boolean("Is Processing Queue", default=False)
    running_status = fields.Char(default="Running...")
    is_action_require = fields.Boolean(default=False)
    queue_process_count = fields.Integer(string="Queue Process Times",
                                         help="it is used know queue how many time processed")
    order_queue_line_total_record = fields.Integer(string='Total Records',
                                                   compute='_compute_order_queue_line_record')
    order_queue_line_draft_record = fields.Integer(string='Draft Records',
                                                   compute='_compute_order_queue_line_record')
    order_queue_line_fail_record = fields.Integer(string='Fail Records',
                                                  compute='_compute_order_queue_line_record')
    order_queue_line_done_record = fields.Integer(string='Done Records',
                                                  compute='_compute_order_queue_line_record')
    order_queue_line_cancel_record = fields.Integer(string='Cancel Records',
                                                    compute='_compute_order_queue_line_record')

    @api.depends('order_queue_line_ids.state')
    def _compute_queue_state(self):
        """
        Computes state from different states of queue lines.
        """
        for record in self:
            if record.order_queue_line_total_record == record.order_queue_line_done_record + \
                    record.order_queue_line_cancel_record:
                record.state = "completed"
            elif record.order_queue_line_draft_record == record.order_queue_line_total_record:
                record.state = "draft"
            elif record.order_queue_line_total_record == record.order_queue_line_fail_record:
                record.state = "failed"
            else:
                record.state = "partially_completed"

    @api.depends('order_queue_line_ids.state')
    def _compute_order_queue_line_record(self):
        """This is used for the count of total records of order queue lines
            and display the count records in the form view order data queue.
        """
        for order_queue in self:
            queue_lines = order_queue.order_queue_line_ids
            order_queue.order_queue_line_total_record = len(queue_lines)
            order_queue.order_queue_line_draft_record = len(queue_lines.filtered(lambda x: x.state == "draft"))
            order_queue.order_queue_line_done_record = len(queue_lines.filtered(lambda x: x.state == "done"))
            order_queue.order_queue_line_fail_record = len(queue_lines.filtered(lambda x: x.state == "failed"))
            order_queue.order_queue_line_cancel_record = len(queue_lines.filtered(lambda x: x.state == "cancel"))

    @api.model
    def create(self, vals):
        """This method used to create a sequence for order queue
        @return: order_id
        """
        sequence_id = self.env.ref("fixably_ept.seq_order_queue_data").ids
        if sequence_id:
            record_name = self.env["ir.sequence"].browse(sequence_id).next_by_id()
        else:
            record_name = "/"
        vals.update({"name": record_name or ""})
        order_id = super(FixablyOrderQueue, self).create(vals)
        return order_id

    def prepare_val_order_creation(self, instance, orders):
        """
        this method use to prepare vals for order queue creation.
        @return: order_val
        """
        order_queue_line_obj = self.env['fixably.order.queue.line.ept']
        order_val = []
        order_line_val = []
        for val in orders['items']:
            line_details = order_queue_line_obj.prepare_val_for_order_queue_line(val['href'], instance)
            order_line_val.append((0, 0, line_details))
        order_val.append({
            "fixably_instance_id": instance.id,
            "order_queue_line_ids": order_line_val
        })
        return order_val

    def fixably_create_order_queue(self, instance, from_date, to_date):
        """
        This method use for the create order queue
        @return: order_queue_ids
        """
        offset = 0
        order_queue_ids = []
        order_url = 'orders?q=createdAt:[' + str(from_date) + ',' + str(to_date) + ']'

        # status_ids = instance.fixably_order_status_ids.mapped("status_id")
        # status_ids = tuple(map(int, status_ids))
        # if status_ids:
        #     order_url = order_url + '&q=status.id:' + str(status_ids)

        orders = instance.connect_with_fixably(ref=order_url)
        if orders.status_code != 200:
            raise UserError(_("Some Error in Connection"))
        else:
            orders = json.loads(orders.content.decode())
            total_queue = orders['totalItems'] / orders['limit']
            _logger.info(total_queue)
            for index in range(int(total_queue) + 1):
                _logger.info(index)
                if total_queue > 1:
                    order = instance.connect_with_fixably(ref=order_url + "&offset=" + str(offset))
                    order = json.loads(order.content.decode())
                else:
                    order = orders
                if offset <= orders['totalItems']:
                    offset += len(order['items'])
                    order_val = self.prepare_val_order_creation(instance, order)
                    new_created_order = self.create(order_val)
                    order_queue_ids.append(new_created_order.id)
                    self._cr.commit()
                    message = "order Queue Created", new_created_order.name
                    instance.last_order_import_date = datetime.now()
                    self.env['fixably.order.queue.line.ept'].generate_simple_notification(message)
        return order_queue_ids

    def create_log_line_for_order_queue_line(self, model_id, message, order_queue_line, log_book_id,
                                             order_line_details):
        """
        This method use for Creates log line as per queue line.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]

        if order_queue_line:
            common_log_line_obj.fixably_create_order_log_line(message, model_id,
                                                              order_queue_line,
                                                              log_book_id, order_line_details['id'])
            order_queue_line.write({"state": "failed", "last_process_date": datetime.now()})

        return True

    def create_customer(self, customer_details):
        """
        This method use for create customer record.
        @return: customer_id
        """
        vals = {
            "name": customer_details['firstName'] + ' ' + customer_details['lastName'],
            "email": customer_details['email'],
            "type": "contact",
        }
        customer_id = self.env['res.partner'].create(vals)
        return customer_id

    def prepare_customer_and_addresses(self, partner, order_response):
        """
        Searches for existing customer in Odoo and creates in odoo, if not found.
        """
        invoice_address = order_response.get("billingAddress") and \
                          self.create_or_update_address(
                              order_response.get("billingAddress"), partner, "invoice") or partner

        delivery_address = order_response.get("shippingAddress") and \
                           self.create_or_update_address(
                               order_response.get("shippingAddress"), partner, "delivery") or partner

        return invoice_address, delivery_address

    @api.model
    def create_or_update_address(self, customer_data, parent_partner, partner_type="contact"):
        """
        Creates or updates existing partner from Shopify customer's data.
        """
        partner_obj = self.env["res.partner"]

        first_name = customer_data.get("first_name")
        last_name = customer_data.get("last_name")

        if not first_name and not last_name:
            return False

        company_name = customer_data.get("company")
        partner_vals = self.prepare_partner_vals(customer_data)
        address_key_list = ["name", "street", "street2", "city", "zip", "phone", "state_id", "country_id"]

        if company_name:
            address_key_list.append("company_name")
            partner_vals.update({"company_name": company_name})

        partner_vals.update({"type": partner_type, "parent_id": parent_partner.id})
        partner = partner_obj.create(partner_vals)

        company_name and partner.write({"company_name": company_name})
        return partner

    def prepare_partner_vals(self, vals):
        """
        This method used to prepare a partner vals.
        @return: partner_vals
        """
        partner_obj = self.env["res.partner"]

        first_name = vals.get("first_name")
        last_name = vals.get("last_name")
        name = "%s %s" % (first_name, last_name)

        zipcode = vals.get("zip")
        state_code = vals.get("province_code")

        country_code = vals.get("country_code")
        country = partner_obj.get_country(country_code)

        state = partner_obj.create_or_update_state_ept(country_code, state_code, zipcode, country)

        partner_vals = {
            "email": vals.get("email") or False,
            "name": name,
            "phone": vals.get("phone"),
            "street": vals.get("address1"),
            "street2": vals.get("address2"),
            "city": vals.get("city"),
            "zip": zipcode,
            "state_id": state and state.id or False,
            "country_id": country and country.id or False,
            "is_company": False
        }
        update_partner_vals = partner_obj.remove_special_chars_from_partner_vals(partner_vals)
        return update_partner_vals

    def search_customer(self, model_id, instance, order_queue_line, log_book_id, queue_line_details):
        """
        This method use for search customer is exists or not in odoo
        as well call create customer method for new customer create
        @return : sale_order , pos_order , customer_id
                sale_order and pos_order take True or False value, from that consider to
                next go for the making sale order or pos order
        """
        odoo_customer_obj = self.env["res.partner"]
        customer_res = queue_line_details['customer']
        sale_order = False
        POS_order = False
        customer_id = False
        delivery_address = False
        invoice_address = False
        if customer_res:
            customer_details = instance.connect_with_fixably(queue_line_details['customer']['href'], withURL=True)
            customer_details = json.loads(customer_details.content.decode())
            customer_id = odoo_customer_obj.search([('email', '=', customer_details['email']), ('active', '=', True)],
                                                   limit=1)
            if customer_id:
                if odoo_customer_obj.search([('id', '=', customer_id.id),
                                             ('credit_limit', '!=', None),
                                             ('property_supplier_payment_term_id', '!=', None)], limit=1):
                    sale_order = True
                else:
                    POS_order = True
                invoice_address, delivery_address = self.prepare_customer_and_addresses(customer_id, queue_line_details)
            else:
                customer_id = self.create_customer(customer_details)
                POS_order = True

        else:
            self.create_log_line_for_order_queue_line(model_id,
                                                      "Customer Details Not Available in the response",
                                                      order_queue_line, log_book_id, queue_line_details)
        return sale_order, POS_order, customer_id, delivery_address, invoice_address

    def search_product(self, details):
        """
        This method use for the product is available in fixably or odoo
        @return: odoo_product
        """
        odoo_product_obj = self.env["product.product"]
        fixably_product_obj = self.env["fixably.product.ept"]
        odoo_product = False
        fixably_product = fixably_product_obj.search([('fixably_product_id', '=', details['id'])],
                                                     limit=1)
        if fixably_product:
            odoo_product = odoo_product_obj.search([("default_code", "=", details['code'])], limit=1)
        return odoo_product

    def prepare_vals_for_order_line(self, instance, sale_order, product, order_line_details):
        """
        This method is used to prepare a vals to create a sale order and pos order line.
        @return: line_vals
        """
        uom_id = product and product.uom_id and product.uom_id.id or False
        if sale_order:
            line_vals = {
                "product_id": product and product.ids[0] or False,
                "company_id": instance.fixably_company_id.id,
                "product_uom": uom_id,
                "name": product['name'],
                "price_unit": order_line_details['price'],
                "product_uom_qty": order_line_details['quantity'],
                "discount": order_line_details['discount'],
                "fixably_line_id": order_line_details['id']
            }

        else:
            line_vals = {
                "product_id": product and product.ids[0] or False,
                # "full_product_name": product['name'],
                "price_unit": order_line_details['price'],
                "qty": order_line_details['quantity'],
                'price_subtotal': 0,
                'price_subtotal_incl': 0,
                "fixably_line_id": order_line_details['id']
            }
        return line_vals

    def fixably_sync_orders(self, order_queue_line, instance, log_book_id):
        """
        This method is used to sync order from queue line to odoo.
        @return: Order
        """
        order = False
        session_id = False
        log_count = 0
        common_log_line_obj = self.env["common.log.lines.ept"]
        model_id = common_log_line_obj.get_model_id("sale.order")
        details = json.loads(order_queue_line['synced_order_data'])

        order_exists = self.check_order_exists_or_not(instance, details)
        if not order_exists:
            sale_order, POS_order, customer_id, delivery_address, invoice_address = self.search_customer(model_id,
                                                                                                         instance,
                                                                                                         order_queue_line,
                                                                                                         log_book_id,
                                                                                                         details)
            if not customer_id:
                log_count += 1

            if sale_order or POS_order:
                if not details['lines']['items']:
                    self.create_log_line_for_order_queue_line(model_id,
                                                              "Order lines are not Available in the response of order %s" % (
                                                                  details['id']),
                                                              order_queue_line, log_book_id, details)
                    log_count += 1
                else:
                    lines = []
                    for order_line in details['lines']['items']:
                        if not order_line['product']:
                            self.create_log_line_for_order_queue_line(model_id,
                                                                      "Product is not Available in order line of order %s" % (
                                                                          details['id']),
                                                                      order_queue_line, log_book_id, details)
                            log_count += 1
                            break
                        else:
                            odoo_product = self.search_product(order_line['product'])
                            if odoo_product:
                                prepared_vals = self.prepare_vals_for_order_line(instance, sale_order,
                                                                                 odoo_product,
                                                                                 order_line)
                                lines.append(prepared_vals)
                            else:
                                self.create_log_line_for_order_queue_line(model_id,
                                                                          "Product is not Available in odoo with name %s" % (
                                                                              order_line['product']['name']),
                                                                          order_queue_line, log_book_id, details)
                                log_count += 1
                                break
                if POS_order:
                    if details['store']:
                        session_id = self.search_open_session_for_pos_order(details)
                        if not session_id:
                            self.create_log_line_for_order_queue_line(model_id,
                                                                      "Any open session not Available with store %s" % (
                                                                          details['store']['name']),
                                                                      order_queue_line, log_book_id, details)
                            log_count += 1
                    else:
                        self.create_log_line_for_order_queue_line(model_id,
                                                                  "Store not Available on response of order %s" % (
                                                                      details['id']),
                                                                  order_queue_line, log_book_id, details)
                        log_count += 1

            if log_count == 0:
                order_queue_line.write({"state": "done", "last_process_date": datetime.now()})
                order = self.create_order(instance, sale_order, POS_order, customer_id, delivery_address,
                                          invoice_address,
                                          details, lines, session_id)

        else:
            order_queue_line.write({"state": "done", "last_process_date": datetime.now()})
        return order

    def check_order_exists_or_not(self, instance, details):
        """
        This method use for check current order is exists or not on sale order
        or pos order
        @return: order
        """
        order = self.env['sale.order'].search(
            [('fixably_instance_id', '=', instance.id), ('fixably_order_id', '=', details['id'])])
        if not order:
            order = self.env['pos.order'].search(
                [('fixably_instance_id', '=', instance.id), ('fixably_order_id', '=', details['id'])])
        return order

    def create_order(self, instance, sale_order, POS_order, customer_id, delivery_address, invoice_address, details,
                     lines, session_id):
        """
        This method is use for the create a sale order and pos order.
        @return: order_id
        """
        sale_order_obj = self.env['sale.order']
        pos_order_obj = self.env['pos.order']
        # pos_order_line_obj = self.env['pos.order.line']
        if sale_order:
            order_vals = self.prepare_sale_order_vals(instance, customer_id, delivery_address, invoice_address, details)
            new_record = sale_order_obj.new(order_vals)
            # new_record._onchange_partner_id()
            order_id = sale_order_obj.create(order_vals)
            index = 0
            for line in lines:
                self.create_sale_order_line(instance, order_id, line, details['lines']['items'][index])
                index += 1
        if POS_order:
            order_vals = self.prepare_pos_order_vals(instance, customer_id, details, session_id)
            new_record = pos_order_obj.new(order_vals)
            new_record._onchange_partner_id()
            order_id = pos_order_obj.create(order_vals)
            index = 0
            for line in lines:
                self.create_pos_order_line(instance, order_id, line, details['lines']['items'][index])
                index += 1
            order_id.lines._onchange_amount_line_all()
            payment_vals = self.prepare_payment_val(lines)
            order_id['payment_ids'] = self.make_payment(payment_vals, order_id).ids
            order_id._onchange_amount_all()
        return order_id

    def create_pos_order_line(self, instance, order_id, line, response_order_line):
        """
        This method use for create the pos order line
        """
        pos_order_line_obj = self.env['pos.order.line']
        line.update({'order_id': order_id.id})
        new_line_record = pos_order_line_obj.new(line)
        new_line_record._onchange_product_id()
        line_id = pos_order_line_obj.create(line)
        line_id = self.fixably_set_tax_in_order_line(instance, line_id, response_order_line, 'POS')

    def create_sale_order_line(self, instance, order_id, line, response_order_line):
        """
        This method use for create the sale order line
        """
        sale_order_line_obj = self.env['sale.order.line']
        line.update({'order_id': order_id.id})
        line_id = sale_order_line_obj.create(line)
        line_id.product_id_change()
        line_id = self.fixably_set_tax_in_order_line(instance, line_id, response_order_line, 'Sale')
        line_id._onchange_discount()
        if response_order_line['serialNumber'] and response_order_line['originalSerialNumber']:
            val = [(0, 0, {
                'display_type': 'line_note',
                'name': 'Serial Number:' + response_order_line['serialNumber'] +
                        '\n' + 'Orignal Serial Number:' + response_order_line['originalSerialNumber'],
            })]
            order_id.update({'order_line': val})

    def fixably_set_tax_in_order_line(self, instance, line_id, order_line_vals, flag):
        """ This method is used to set tax in the sale order line base on tax configuration in the
            fixably setting in Odoo.
        """
        if instance.apply_tax == "create_fixably_tax":
            tax = order_line_vals.get("vat") or False
            if tax:
                tax_ids = self.fixably_get_tax_id_ept(instance, order_line_vals, tax)
            if flag == 'Sale':
                line_id["tax_id"] = tax_ids
            else:
                line_id["tax_ids"] = tax_ids
        return line_id

    @api.model
    def fixably_get_tax_id_ept(self, instance, order_line_vals, tax):
        """This method used to search tax in Odoo, If tax is not found in Odoo then it call child method to create a
            new tax in Odoo base on received tax response in order response.
            @return: tax_id
        """
        tax_id = []
        taxes = []
        company = instance.fixably_warehouse_id.company_id
        price = float(order_line_vals.get('price', 0.0))
        if tax != 0.0 and price != 0.0:
            name = "Fixably_%s_(%s %s)_%s" % ('tax', str(tax), "%", company.name)
            tax_id = self.env["account.tax"].search([("type_tax_use", "=", "sale"), ("amount", "=", tax),
                                                     ("name", "=", name), ("company_id", "=", company.id)], limit=1)
            if not tax_id:
                tax_id = self.sudo().fixably_create_account_tax(instance, tax, company, name)
            if tax_id:
                taxes.append(tax_id.id)
        if taxes:
            tax_id = [(6, 0, taxes)]
        return tax_id

    @api.model
    def fixably_create_account_tax(self, instance, value, company, name):
        """This method used to create tax in Odoo when importing orders from fixably to Odoo.
            @param : self, value, price_included, company, name
            @return: account_tax_id
        """
        account_tax_obj = self.env["account.tax"]

        account_tax_id = account_tax_obj.create({"name": name, "amount": float(value),
                                                 "type_tax_use": "sale",
                                                 "company_id": company.id})
        account_tax_id.mapped("invoice_repartition_line_ids").write(
            {"account_id": instance.debit_tax_account_id.id if instance.debit_tax_account_id else False})
        account_tax_id.mapped("refund_repartition_line_ids").write(
            {"account_id": instance.credit_tax_account_id.id if instance.credit_tax_account_id else False})

        return account_tax_id

    def prepare_payment_val(self, lines):
        """
        This method is use to prepare vals for payment line of pos order
        @return: payment_vals
        """
        payment_vals = {
            'amount': sum(float(line['qty']) * float(line['price_unit']) for line in lines)
        }
        return payment_vals

    def make_payment(self, vals, order_id):
        """
        This method is use to prepare vals for payment of pos order
        @return: payment
        """
        payment_method = self.env['pos.make.payment'].with_context(active_id=order_id.id)._default_payment_method()
        payment = self.env['pos.payment'].create({
            'pos_order_id': order_id.id,
            'amount': vals.get('amount'),
            'payment_method_id': payment_method.id,
            'payment_date': fields.Datetime.now()
        })
        order_id.action_pos_order_paid()
        return payment

    def prepare_sale_order_vals(self, instance, customer_id, delivery_address, invoice_address, details):
        """
        This method used to Prepare a sale order vals.
        @return: ordervals
        """
        # date_order = self.convert_order_date(order_response)
        team_id = self.search_team_from_instance(details)
        ordervals = {
            "company_id": instance.fixably_company_id.id if instance.fixably_company_id else False,
            "partner_id": customer_id.ids[0],
            "partner_invoice_id": delivery_address.ids[0],
            "partner_shipping_id": invoice_address.ids[0],
            "warehouse_id": instance.fixably_warehouse_id.id if instance.fixably_warehouse_id else False,
            "date_order": datetime.now(),
            "state": "draft",
            "pricelist_id": instance.fixably_pricelist_id.id if instance.fixably_pricelist_id else False,
            "team_id": team_id,
            "fixably_instance_id": instance.id,
            "fixably_order_id": details['id'],
            "fixably_customer_id": details["customer"]["id"]
        }
        if not instance.fixably_is_use_default_sequence:
            if instance.fixably_order_prefix:
                name = "%s_%s" % (instance.fixably_order_prefix, details.get("id"))
            else:
                name = details.get("id")
            ordervals.update({"name": name})
        return ordervals

    def prepare_pos_order_vals(self, instance, customer_id, details, session_id):
        """
        This method used to Prepare a pos order vals.
        @return: ordervals
        """
        # date_order = self.convert_order_date(order_response)
        ordervals = {
            "company_id": instance.fixably_company_id.id if instance.fixably_company_id else False,
            "partner_id": customer_id.ids[0],
            "session_id": session_id.ids[0],
            'amount_tax': 0,
            'amount_total': 0,
            'amount_paid': 0,
            'amount_return': 0,
            "fixably_instance_id": instance.id,
            "fixably_order_id": details['id'],
            "fixably_customer_id": details["customer"]["id"]
        }
        if not instance.fixably_is_use_default_sequence:
            if instance.fixably_order_prefix:
                name = "%s_%s" % (instance.fixably_order_prefix, details.get("id"))
            else:
                name = details.get("id")
            ordervals.update({"name": name})
        return ordervals

    def convert_order_date(self, order_response):
        """
        This method is used to convert the order date in UTC and formate("%Y-%m-%d %H:%M:%S").
        @return: date_order
        """
        if order_response["createdAt"]:
            order_date = order_response["createdAt"]
            date_order = parser.parse(order_date).astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
        else:
            date_order = time.strftime("%Y-%m-%d %H:%M:%S")
            date_order = str(date_order)

        return date_order

    def search_team_from_instance(self, details):
        """
        This method use for the team id from fixably store model
        @return: team_id
        """
        team_id = self.env['fixably.store.ept'].search(
            [('fixably_store_id', '=', details['store']['id'])]).mapped("fixably_team_id").ids
        return team_id

    def search_open_session_for_pos_order(self, details):
        """
        This method use for the search open pos session base on fixably pos store
        base on current order store
        @return: session_id
        """
        store_id = self.env['fixably.store.ept'].search(
            [('fixably_store_id', '=', details['store']['id'])]).mapped("fixably_pos_store_id").ids
        session_id = self.env['pos.session'].search([('config_id', '=', store_id),
                                                     ('state', '=', 'opened')], limit=1)
        return session_id

    def import_order_cron_action(self, ctx=False):
        """
        This method is used to import orders from the auto-import cron job.
        """
        if isinstance(ctx, dict):
            instance_id = ctx.get('fixably_instance_id')
            instance = self.env['fixably.instance.ept'].browse(instance_id)
            from_date = instance.last_order_import_date
            to_date = datetime.now()
            if not from_date:
                from_date = to_date - timedelta(3)
            self.fixably_create_order_queue(instance, from_date, to_date)
        return True
