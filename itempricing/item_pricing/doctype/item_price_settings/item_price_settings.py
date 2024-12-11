# Copyright (c) 2023, George Mukundi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ItemPriceSettings(Document):
	pass
		# frappe.enqueue(set_the_price, queue='short', self=self)
      
def set_the_price(self):
	frappe.publish_realtime('msgprint', 'Starting background job...')
	conditions = ""
	if self.item_group:
		itemgroup = self.item_group
		conditions += """ AND `tabItem`.item_group = {0}""".format(itemgroup)
  
	if self.base_price_list:
		base_price_list = self.base_price_list
		conditions += """ AND `tabItem Price`.price_list = {0}""".format(base_price_list)
	else:
		if self.price_list:
			price_list = self.price_list
			conditions += """ AND `tabItem Price`.price_list = {0}""".format(price_list)
	if self.supplier:
		supplier = self.supplier
		conditions += """ AND `tabItem`.default_supplier = {0}""".format(supplier)


	items_data = frappe.db.sql(
		"""
		SELECT
			`tabItem Price`.name AS price_name,
			`tabItem Price`.price_list AS price_list_name,
			`tabItem`.name AS item_code,
			`tabItem`.item_name,
			`tabItem`.item_group,
			`tabItem`.default_supplier
		FROM
			`tabItem Price` 
			LEFT JOIN `tabItem`
				ON `tabItem Price`.item_code = `tabItem`.name
		WHERE
			`tabItem`.disabled = 0
				{0}
		ORDER BY
			name asc
			""".format(
       			conditions or ""
		),
		as_dict=1,
	)
	# check items
	prices_data = []
	for d in items_data:
		finalprice = 0
		if self.change_type == "Percentage Rate":
			if self.price_type == "Price Increase":
				finalprice = ((self.rate + 100) / 100) * d.price_list_rate
			else:
				finalprice = ((100 - self.rate) / 100) * d.price_list_rate
		else:
			if self.price_type == "Price Increase":
				finalprice = self.rate + d.price_list_rate
			else:
				finalprice = d.price_list_rate - self.rate
    
		prices_data.append(frappe._dict({
			'item_code': d.item_code,
			'item_group': d.item_group,
			'price_list': d.price_list_name,
			'item_price': d.price_name,
			'initial_price': d.price_list_rate,
			'default_supplier': d.default_supplier,
			'actual_price': finalprice,
		}))
	if prices_data:
		self.set('items', prices_data)
		self.status = "Saved"
		self.save()
		frappe.publish_realtime('msgprint', 'Background job has ended.')
			
