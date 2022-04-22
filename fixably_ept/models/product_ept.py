# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from datetime import datetime
import json


class FixablyProductEpt(models.Model):
    _name = "fixably.product.ept"
    _description = 'Fixably Product'

    fixably_product_id = fields.Char(string="Id", help="Product Id")
    name = fields.Char(string="Name", help="Product Name")
    code = fields.Char(string="Code", help="Product Code")
    description = fields.Char(string="Description", help="Product Description")
    version = fields.Char(string="Version", help="Product version")
    type_string = fields.Char(string="Type String", help="Type String")
    category_string = fields.Char(string="Category String", help="Category String")
    stock_price = fields.Char(string="Stock Price", help="Stock Price")
    product_id = fields.Many2one('product.product', string="Product")

    def fixably_sync_products(self, product_queue_line, instance, log_book_id):
        """
        This method is used to sync products from queue line to fixably.
        @return: product
        """
        product = False
        common_log_line_obj = self.env["common.log.lines.ept"]
        model_id = common_log_line_obj.get_model_id("fixably.product.ept")
        details = json.loads(product_queue_line['synced_product_data'])

        fixably_product, odoo_product = self.fixably_search_odoo_product(product_queue_line, details)

        if fixably_product:
            product = self.create_or_update_product(product_queue_line, fixably_product, odoo_product, details)
        else:
            if odoo_product:
                is_importable = self.is_product_importable(model_id, product_queue_line, log_book_id, details)
                if is_importable:
                    product = self.create_or_update_product(product_queue_line, fixably_product, odoo_product, details)
            else:
                odoo_product = self.is_odoo_product_importable(instance, details)
                if not odoo_product:
                    self.create_log_line_for_queue_line(model_id,
                                                        "Product Not found in Odoo with SKU %s" % (details['code']),
                                                        product_queue_line, log_book_id, details)
                else:
                    product = self.create_or_update_product(product_queue_line, fixably_product, odoo_product, details)
        if product:
            product_queue_line.write({"state": "done", "last_process_date": datetime.now()})
            instance.fixably_pricelist_id.set_product_price_ept(product.product_id.id,
                                                                details["stockPrice"])
        return product

    def fixably_search_odoo_product(self, product_queue_line, product_line_details):
        """
        This method use for Searches fixably/Odoo product
        @return: fixably_product , odoo_product
        """
        odoo_product_obj = self.env["product.product"]
        fixably_product_obj = self.env["fixably.product.ept"]
        fixably_product = False
        if not product_queue_line.product_queue_id.skip_existing_product:
            fixably_product = fixably_product_obj.search([('fixably_product_id', '=', product_queue_line.product_id)],
                                                     limit=1)
        odoo_product = odoo_product_obj.search([("default_code", "=", product_line_details['code'])], limit=1)

        return fixably_product, odoo_product

    def create_log_line_for_queue_line(self, model_id, message, product_queue_line, log_book_id, product_line_details):
        """
        This method use for Creates log line as per queue line.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]

        if product_queue_line:
            common_log_line_obj.fixably_create_product_log_line(message, model_id,
                                                                product_queue_line,
                                                                log_book_id, product_line_details['code'])
            product_queue_line.write({"state": "failed", "last_process_date": datetime.now()})

        return True

    def create_odoo_product(self, product_line_details):
        """
        This method use for prepare vals and create product in odoo
        @return: created_product
        """
        odoo_product_obj = self.env['product.product']
        vals = {
            "name": product_line_details['name'],
            "default_code": product_line_details['code']
        }
        odoo_created_product = odoo_product_obj.create(vals)
        return odoo_created_product

    def is_odoo_product_importable(self, instance, product_line_details):
        """
        This method will check if the product can be imported or not.
        @return: odoo_product_id
        """
        if instance.fixably_auto_create_product_if_not_found:
            odoo_product_id = self.create_odoo_product(product_line_details)
            return odoo_product_id

    def is_product_importable(self, model_id, product_queue_line, log_book_id, product_line_details):
        """
        This method will check if the product can be imported or not.
        """
        message = ""
        if self.env['fixably.product.ept'].search([('code', '=', product_line_details['code'])]):
            message = "Duplicate SKU found in Product %s and ID: %s." % (
                product_line_details['name'], product_queue_line.product_id)
        if message:
            self.create_log_line_for_queue_line(model_id, message, product_queue_line, log_book_id,
                                                product_line_details)
            return False
        return True

    def create_or_update_product(self, product_queue_line, fixably_product, odoo_product, product_line_details):
        """
        This method used to create new or update existing fixably product.
        @return: fixably_product
        """
        vals = {
            "fixably_product_id": product_line_details['id'],
            "version": product_line_details['version'],
            "name": product_line_details['name'],
            "description": product_line_details['description'],
            "code": product_line_details['code'],
            "type_string": product_line_details['typeString'],
            "category_string": product_line_details['categoryString'],
            "stock_price": product_line_details['stockPrice']
        }
        if fixably_product:
            if not product_queue_line.product_queue_id.skip_existing_product:
                fixably_product.write(vals)
        else:
            if odoo_product:
                vals.update({'product_id': odoo_product.id})
            fixably_product = self.create(vals)

        return fixably_product
